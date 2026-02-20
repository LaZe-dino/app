import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, useWindowDimensions, TextInput, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useTheme } from '../../src/contexts/ThemeContext';
import { ThemeColors, SPACING, FONT_SIZES, RADIUS } from '../../src/theme';
import { api } from '../../src/api';
import FluidChart, { type TimeRange } from '../../src/components/FluidChart';

function formatCurrency(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCompact(n: number | null | undefined): string {
  if (n == null || n === 0) return '—';
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(2);
}

export default function StockDetailScreen() {
  const { symbol } = useLocalSearchParams<{ symbol: string }>();
  const router = useRouter();
  const { colors } = useTheme();
  const { width: screenW } = useWindowDimensions();
  const chartW = screenW - SPACING.lg * 2;

  const [quote, setQuote] = useState<any>(null);
  const [chartData, setChartData] = useState<any[]>([]);
  const [position, setPosition] = useState<any>(null);
  const [selectedRange, setSelectedRange] = useState<TimeRange>('1D');
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [crosshairActive, setCrosshairActive] = useState(false);
  const [crosshairPrice, setCrosshairPrice] = useState<number | null>(null);
  const [showTradeForm, setShowTradeForm] = useState(false);
  const [tradeQty, setTradeQty] = useState('');
  const [tradeLimitPrice, setTradeLimitPrice] = useState('');
  const [brokerConnected, setBrokerConnected] = useState(false);
  const [placingOrder, setPlacingOrder] = useState(false);

  const fetchData = useCallback(async () => {
    if (!symbol) return;
    try {
      const [quoteRes, portfolioRes] = await Promise.all([
        api.getStockQuote(symbol),
        api.getPortfolio(),
      ]);
      setQuote(quoteRes);
      const holding = (portfolioRes.holdings || []).find((h: any) => h.symbol === symbol.toUpperCase());
      setPosition(holding || null);
    } catch (e) {
      console.error('Stock fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  const fetchChart = useCallback(async (range: string) => {
    if (!symbol) return;
    setChartLoading(true);
    try {
      const result = await api.getStockChart(symbol, range);
      setChartData(result.data || []);
    } catch {
      setChartData([]);
    } finally {
      setChartLoading(false);
    }
  }, [symbol]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { fetchChart(selectedRange); }, [selectedRange, fetchChart]);
  useEffect(() => {
    api.getBrokerStatus().then((r: any) => setBrokerConnected(r?.connected === true)).catch(() => setBrokerConnected(false));
  }, [showTradeForm]);

  const placeOrder = useCallback(async (side: 'buy' | 'sell') => {
    const qty = parseInt(tradeQty, 10);
    const limitPrice = parseFloat(tradeLimitPrice) || livePrice;
    if (!qty || qty < 1) {
      Alert.alert('Invalid quantity', 'Enter a whole number of shares.');
      return;
    }
    if (!limitPrice || limitPrice <= 0) {
      Alert.alert('Invalid price', 'Enter a valid limit price.');
      return;
    }
    if (!symbol) return;
    setPlacingOrder(true);
    try {
      await api.placeBrokerOrder({
        symbol: symbol.toUpperCase(),
        side,
        qty,
        order_type: 'limit',
        limit_price: limitPrice,
      });
      Alert.alert('Order placed', `${side.toUpperCase()} ${qty} ${symbol} @ $${limitPrice.toFixed(2)}`);
      setShowTradeForm(false);
      setTradeQty('');
      fetchData();
    } catch (e: any) {
      Alert.alert('Order failed', e?.message || 'Could not place order.');
    } finally {
      setPlacingOrder(false);
    }
  }, [symbol, tradeQty, tradeLimitPrice, livePrice, fetchData]);

  const s = useMemo(() => createStyles(colors), [colors]);

  const livePrice = quote?.price || position?.current_price || 0;
  const price = crosshairActive && crosshairPrice != null ? crosshairPrice : livePrice;
  const change = crosshairActive ? (price - livePrice) : (quote?.change || 0);
  const changePct = crosshairActive ? (livePrice !== 0 ? (change / livePrice) * 100 : 0) : (quote?.change_pct || 0);
  const isUp = change >= 0;
  const lineColor = isUp ? colors.green.primary : colors.red.primary;

  const fluidChartData = useMemo(() => {
    if (chartData.length < 2) return [];
    return chartData.map((d: any) => ({
      time: d.time,
      value: d.price,
      volume: d.volume || undefined,
    }));
  }, [chartData]);

  const handleRangeChange = useCallback((range: TimeRange) => {
    setSelectedRange(range);
  }, []);

  const handleCrosshairChange = useCallback((pt: { value: number; change: number; changePct: number; time: string } | null) => {
    if (pt) {
      setCrosshairActive(true);
      setCrosshairPrice(pt.value);
    } else {
      setCrosshairActive(false);
      setCrosshairPrice(null);
    }
  }, []);

  if (loading) {
    return (
      <SafeAreaView style={[s.safe, { justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator size="small" color={colors.green.primary} />
      </SafeAreaView>
    );
  }

  const marketValue = position ? (price * position.shares) : 0;
  const totalReturn = position ? ((price - position.avg_cost) * position.shares) : 0;
  const totalReturnPct = position ? ((price - position.avg_cost) / position.avg_cost * 100) : 0;
  const todayReturn = position ? (change * position.shares) : 0;
  const todayReturnPct = changePct;
  const portfolioDiversity = position && price ? 100 : 0;

  const stats = [
    { label: 'Open', value: quote?.open ? `$${formatCurrency(quote.open)}` : '—' },
    { label: 'Volume', value: formatCompact(quote?.volume) },
    { label: 'High', value: quote?.high ? `$${formatCurrency(quote.high)}` : '—' },
    { label: 'Avg Vol', value: formatCompact(quote?.avg_volume) },
    { label: 'Low', value: quote?.low ? `$${formatCurrency(quote.low)}` : '—' },
    { label: 'Mkt Cap', value: formatCompact(quote?.market_cap) },
    { label: '52 Wk High', value: quote?.week_52_high ? `$${formatCurrency(quote.week_52_high)}` : '—' },
    { label: 'P/E Ratio', value: quote?.pe_ratio ? quote.pe_ratio.toFixed(2) : '—' },
    { label: '52 Wk Low', value: quote?.week_52_low ? `$${formatCurrency(quote.week_52_low)}` : '—' },
    { label: 'Div/Yield', value: quote?.dividend_yield ? `${(quote.dividend_yield * 100).toFixed(2)}%` : '—' },
  ];

  return (
    <SafeAreaView style={s.safe}>
      {/* Top Bar */}
      <View style={s.topBar}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="chevron-back" size={28} color={colors.green.primary} />
        </TouchableOpacity>
        <View style={s.topCenter}>
          <Text style={s.topPrice}>${formatCurrency(price)}</Text>
          <Text style={s.topTicker}>{symbol?.toUpperCase()}</Text>
        </View>
        <View style={s.backBtn} />
      </View>

      <ScrollView style={s.scroll} contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
        {/* Price Change */}
        <View style={s.changeRow}>
          <Ionicons name={isUp ? 'arrow-up' : 'arrow-down'} size={14} color={isUp ? colors.green.text : colors.red.text} />
          <Text style={[s.changeText, { color: isUp ? colors.green.text : colors.red.text }]}>
            ${formatCurrency(Math.abs(change))} ({isUp ? '+' : ''}{changePct.toFixed(2)}%)
          </Text>
          <Text style={s.changeLabel}>Today</Text>
        </View>

        {/* Chart */}
        <View style={s.chartContainer}>
          {chartLoading ? (
            <View style={s.chartPlaceholder}>
              <ActivityIndicator size="small" color={colors.text.muted} />
            </View>
          ) : fluidChartData.length > 1 ? (
            <FluidChart
              data={fluidChartData}
              width={chartW}
              height={240}
              showGrid={true}
              showLabels={true}
              showVolume={fluidChartData.some(d => d.volume)}
              showCrosshair={true}
              showPriceHeader={false}
              showRangeSelector={true}
              activeRange={selectedRange}
              onRangeChange={handleRangeChange}
              onCrosshairChange={handleCrosshairChange}
              animated
              padding={{ top: 16, right: 12, bottom: 32, left: 50 }}
            />
          ) : (
            <View style={s.chartPlaceholder}>
              <Text style={s.chartPlaceholderText}>No data available</Text>
            </View>
          )}
        </View>

        {/* Position */}
        {position && (
          <>
            <View style={s.divider} />
            <Text style={s.sectionTitle}>Your Position</Text>
            <View style={s.positionCard}>
              <View style={s.posRow}>
                <View style={s.posItem}>
                  <Text style={s.posLabel}>Shares</Text>
                  <Text style={s.posValue}>{position.shares}</Text>
                </View>
                <View style={s.posItem}>
                  <Text style={s.posLabel}>Market Value</Text>
                  <Text style={s.posValue}>${formatCurrency(marketValue)}</Text>
                </View>
              </View>
              <View style={s.posRow}>
                <View style={s.posItem}>
                  <Text style={s.posLabel}>Avg Cost</Text>
                  <Text style={s.posValue}>${formatCurrency(position.avg_cost)}</Text>
                </View>
                <View style={s.posItem}>
                  <Text style={s.posLabel}>Portfolio Diversity</Text>
                  <Text style={s.posValue}>{portfolioDiversity.toFixed(2)}%</Text>
                </View>
              </View>
              <View style={s.posDivider} />
              <View style={s.posRow}>
                <View style={s.posItem}>
                  <Text style={s.posLabel}>Today's Return</Text>
                  <Text style={[s.posValueColor, { color: todayReturn >= 0 ? colors.green.text : colors.red.text }]}>
                    {todayReturn >= 0 ? '+' : ''}${formatCurrency(Math.abs(todayReturn))} ({todayReturnPct >= 0 ? '+' : ''}{todayReturnPct.toFixed(2)}%)
                  </Text>
                </View>
              </View>
              <View style={s.posRow}>
                <View style={s.posItem}>
                  <Text style={s.posLabel}>Total Return</Text>
                  <Text style={[s.posValueColor, { color: totalReturn >= 0 ? colors.green.text : colors.red.text }]}>
                    {totalReturn >= 0 ? '+' : ''}${formatCurrency(Math.abs(totalReturn))} ({totalReturnPct >= 0 ? '+' : ''}{totalReturnPct.toFixed(2)}%)
                  </Text>
                </View>
              </View>
            </View>
          </>
        )}

        {/* Stats */}
        <View style={s.divider} />
        <Text style={s.sectionTitle}>Stats</Text>
        <View style={s.statsGrid}>
          {stats.map((stat, i) => (
            <View key={i} style={[s.statRow, i % 2 === 0 ? s.statLeft : s.statRight]}>
              <Text style={s.statLabel}>{stat.label}</Text>
              <Text style={s.statValue}>{stat.value}</Text>
            </View>
          ))}
        </View>

        {/* Today's Volume */}
        {quote?.volume != null && (
          <View style={s.volumeRow}>
            <Text style={s.volumeLabel}>Today's Volume</Text>
            <Text style={s.volumeValue}>{quote.volume.toLocaleString()}</Text>
          </View>
        )}

        {/* Trade Button */}
        <TouchableOpacity
          style={[s.tradeBtn, { backgroundColor: colors.green.primary }]}
          activeOpacity={0.8}
          onPress={() => {
            if (!brokerConnected) {
              Alert.alert(
                'Connect Alpaca first',
                'Go to the HFT tab → Wallet → connect your Alpaca account (API keys or OAuth), then you can place real orders here.',
              );
              return;
            }
            setTradeLimitPrice(String(livePrice > 0 ? livePrice.toFixed(2) : ''));
            setShowTradeForm(true);
          }}
        >
          <Text style={s.tradeBtnText}>Trade</Text>
        </TouchableOpacity>

        {showTradeForm && (
          <View style={[s.tradeForm, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[s.tradeFormTitle, { color: colors.text.primary }]}>Place order (Alpaca)</Text>
            <Text style={[s.tradeFormLabel, { color: colors.text.muted }]}>Quantity (shares)</Text>
            <TextInput
              style={[s.tradeInput, { backgroundColor: colors.bg.tertiary, color: colors.text.primary, borderColor: colors.border }]}
              placeholder="e.g. 10"
              placeholderTextColor={colors.text.muted}
              keyboardType="number-pad"
              value={tradeQty}
              onChangeText={setTradeQty}
            />
            <Text style={[s.tradeFormLabel, { color: colors.text.muted }]}>Limit price ($)</Text>
            <TextInput
              style={[s.tradeInput, { backgroundColor: colors.bg.tertiary, color: colors.text.primary, borderColor: colors.border }]}
              placeholder={livePrice > 0 ? livePrice.toFixed(2) : '0.00'}
              placeholderTextColor={colors.text.muted}
              keyboardType="decimal-pad"
              value={tradeLimitPrice}
              onChangeText={setTradeLimitPrice}
            />
            <View style={s.tradeFormRow}>
              <TouchableOpacity
                style={[s.tradeFormBtn, { backgroundColor: colors.green.primary }]}
                disabled={placingOrder}
                onPress={() => placeOrder('buy')}
              >
                <Text style={s.tradeFormBtnText}>Buy</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[s.tradeFormBtn, { backgroundColor: colors.red.primary }]}
                disabled={placingOrder}
                onPress={() => placeOrder('sell')}
              >
                <Text style={s.tradeFormBtnText}>Sell</Text>
              </TouchableOpacity>
            </View>
            <TouchableOpacity onPress={() => setShowTradeForm(false)} style={{ marginTop: 8 }}>
              <Text style={{ fontSize: 12, color: colors.text.muted }}>Cancel</Text>
            </TouchableOpacity>
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const createStyles = (t: ThemeColors) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: t.bg.primary },
  scroll: { flex: 1 },
  content: { paddingHorizontal: SPACING.lg },

  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: SPACING.sm, paddingVertical: SPACING.sm },
  backBtn: { width: 44, height: 44, justifyContent: 'center', alignItems: 'center' },
  topCenter: { alignItems: 'center' },
  topPrice: { fontSize: FONT_SIZES.xl, fontWeight: '800', color: t.text.primary },
  topTicker: { fontSize: FONT_SIZES.xs, color: t.text.tertiary, marginTop: 1 },

  changeRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: SPACING.lg },
  changeText: { fontSize: FONT_SIZES.base, fontWeight: '600' },
  changeLabel: { fontSize: FONT_SIZES.sm, color: t.text.muted, marginLeft: 4 },

  chartContainer: { marginBottom: SPACING.md, alignItems: 'center', overflow: 'hidden' },
  chartPlaceholder: { height: 200, justifyContent: 'center', alignItems: 'center' },
  chartPlaceholderText: { color: t.text.muted, fontSize: FONT_SIZES.sm },

  divider: { height: 0.5, backgroundColor: t.border, marginVertical: SPACING.lg },

  sectionTitle: { fontSize: FONT_SIZES.lg, fontWeight: '700', color: t.text.primary, marginBottom: SPACING.md },

  positionCard: { backgroundColor: t.card, borderRadius: RADIUS.md, padding: SPACING.lg, borderWidth: 0.5, borderColor: t.border },
  posRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: SPACING.md },
  posItem: { flex: 1 },
  posLabel: { fontSize: FONT_SIZES.xs, color: t.text.tertiary, marginBottom: 4 },
  posValue: { fontSize: FONT_SIZES.base, fontWeight: '700', color: t.text.primary },
  posValueColor: { fontSize: FONT_SIZES.base, fontWeight: '700' },
  posDivider: { height: 0.5, backgroundColor: t.border, marginVertical: SPACING.sm },

  statsGrid: { flexDirection: 'row', flexWrap: 'wrap' },
  statRow: { width: '50%', flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 10, borderBottomWidth: 0.5, borderBottomColor: t.border },
  statLeft: { paddingRight: SPACING.md },
  statRight: { paddingLeft: SPACING.md },
  statLabel: { fontSize: FONT_SIZES.sm, color: t.text.tertiary },
  statValue: { fontSize: FONT_SIZES.sm, fontWeight: '600', color: t.text.primary },

  volumeRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: SPACING.md, borderBottomWidth: 0.5, borderBottomColor: t.border },
  volumeLabel: { fontSize: FONT_SIZES.sm, fontWeight: '700', color: t.text.primary },
  volumeValue: { fontSize: FONT_SIZES.sm, fontWeight: '600', color: t.text.primary },

  tradeBtn: { marginTop: SPACING.xl, paddingVertical: 16, borderRadius: RADIUS.full, alignItems: 'center' },
  tradeBtnText: { fontSize: FONT_SIZES.lg, fontWeight: '700', color: '#FFFFFF' },
  tradeForm: { marginTop: SPACING.md, padding: SPACING.lg, borderRadius: RADIUS.md, borderWidth: 1 },
  tradeFormTitle: { fontSize: FONT_SIZES.base, fontWeight: '700', marginBottom: SPACING.sm },
  tradeFormLabel: { fontSize: FONT_SIZES.sm, marginBottom: 4, marginTop: 8 },
  tradeInput: { borderWidth: 1, borderRadius: RADIUS.md, paddingHorizontal: 12, paddingVertical: 10, fontSize: 16 },
  tradeFormRow: { flexDirection: 'row', gap: 12, marginTop: SPACING.md },
  tradeFormBtn: { flex: 1, paddingVertical: 12, borderRadius: RADIUS.md, alignItems: 'center' },
  tradeFormBtnText: { fontSize: FONT_SIZES.base, fontWeight: '700', color: '#FFFFFF' },
});
