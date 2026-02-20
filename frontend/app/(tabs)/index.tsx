import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl,
  TouchableOpacity, ActivityIndicator, useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import Svg, { Polyline } from 'react-native-svg';
import { useTheme } from '../../src/contexts/ThemeContext';
import { ThemeColors, SPACING, FONT_SIZES, RADIUS } from '../../src/theme';
import { api, marketWS } from '../../src/api';
import FluidChart, { type TimeRange } from '../../src/components/FluidChart';

function Sparkline({ data, width = 56, height = 24, color }: {
  data: number[]; width?: number; height?: number; color: string;
}) {
  if (!data || data.length < 2) return <View style={{ width, height }} />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - 2 - ((v - min) / range) * (height - 4);
    return `${x},${y}`;
  }).join(' ');
  return (
    <Svg width={width} height={height}>
      <Polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function formatCurrency(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCompact(n: number): string {
  if (!n) return '—';
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(0);
}

export default function InvestingScreen() {
  const { colors, toggle, isDark } = useTheme();
  const router = useRouter();
  const { width: screenW } = useWindowDimensions();
  const chartW = screenW - SPACING.lg * 2;
  const [portfolio, setPortfolio] = useState<any>(null);
  const [holdings, setHoldings] = useState<any[]>([]);
  const [realQuotes, setRealQuotes] = useState<Record<string, any>>({});
  const [chartData, setChartData] = useState<any[]>([]);
  const [selectedRange, setSelectedRange] = useState<TimeRange>('1M');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [chartLoading, setChartLoading] = useState(false);

  const fetchPortfolio = useCallback(async () => {
    try {
      const result = await api.getPortfolio();
      setPortfolio(result);
      setHoldings(result.holdings || []);
      const symbols = (result.holdings || []).map((h: any) => h.symbol);
      if (symbols.length > 0) {
        try {
          const quotes = await api.getBatchQuotes(symbols);
          setRealQuotes(quotes);
        } catch { /* use fallback prices */ }
      }
    } catch (e) {
      console.error('Portfolio fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const fetchChart = useCallback(async (range: string) => {
    setChartLoading(true);
    try {
      const mainSymbol = holdings[0]?.symbol || 'SPY';
      const result = await api.getStockChart(mainSymbol, range);
      setChartData(result.data || []);
    } catch {
      setChartData([]);
    } finally {
      setChartLoading(false);
    }
  }, [holdings]);

  useEffect(() => { fetchPortfolio(); }, [fetchPortfolio]);
  useEffect(() => { if (holdings.length) fetchChart(selectedRange); }, [holdings.length, selectedRange]);

  useEffect(() => {
    const unsub = marketWS.subscribe((msg) => {
      if (msg.type === 'market_update' && msg.data) {
        setRealQuotes(prev => {
          const updated = { ...prev };
          for (const [sym, d] of Object.entries(msg.data as Record<string, any>)) {
            if (updated[sym]) updated[sym] = { ...updated[sym], price: d.price };
          }
          return updated;
        });
      }
    });
    return unsub;
  }, []);

  const onRefresh = () => { setRefreshing(true); fetchPortfolio(); };

  const getPrice = (symbol: string, fallback: number) =>
    realQuotes[symbol]?.price || fallback;

  const totalValue = useMemo(() => {
    if (!holdings.length) return portfolio?.total_value || 0;
    return holdings.reduce((sum, h) => sum + getPrice(h.symbol, h.current_price) * h.shares, 0);
  }, [holdings, realQuotes, portfolio]);

  const totalCost = portfolio?.total_cost || 0;
  const hftPnl = portfolio?.hft_pnl || 0;
  const botPnl = portfolio?.bot_pnl || 0;
  const totalPnl = totalValue - totalCost;
  const totalPnlPct = totalCost ? ((totalPnl / totalCost) * 100) : 0;
  const isUp = totalPnl >= 0;
  const pnlColor = isUp ? colors.green.text : colors.red.text;

  const fluidChartData = useMemo(() => {
    if (chartData.length < 2) return [];
    return chartData.map((d: any) => ({ time: d.time, value: d.price }));
  }, [chartData]);

  const s = useMemo(() => createStyles(colors), [colors]);

  if (loading) {
    return (
      <SafeAreaView style={[s.safe, { justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator size="small" color={colors.green.primary} />
        <Text style={[s.loadingText, { marginTop: 12 }]}>Loading your portfolio...</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.green.primary} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={s.header}>
          <Text style={s.headerTitle}>Investing</Text>
          <TouchableOpacity onPress={toggle} style={s.themeBtn}>
            <Ionicons name={isDark ? 'sunny-outline' : 'moon-outline'} size={22} color={colors.text.primary} />
          </TouchableOpacity>
        </View>

        {/* Portfolio Value */}
        <Text style={s.heroAmount}>${formatCurrency(totalValue)}</Text>
        <View style={s.heroPnl}>
          <Ionicons name={isUp ? 'arrow-up' : 'arrow-down'} size={14} color={pnlColor} />
          <Text style={[s.heroPnlText, { color: pnlColor }]}>
            ${formatCurrency(Math.abs(totalPnl))}
          </Text>
          <Text style={[s.heroPnlPct, { color: pnlColor }]}>
            ({isUp ? '+' : ''}{totalPnlPct.toFixed(2)}%)
          </Text>
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
              height={200}
              showGrid={false}
              showLabels={false}
              showCrosshair={true}
              showPriceHeader={false}
              showRangeSelector={true}
              activeRange={selectedRange}
              onRangeChange={(r) => setSelectedRange(r)}
              animated
              padding={{ top: 8, right: 4, bottom: 8, left: 4 }}
            />
          ) : (
            <View style={s.chartPlaceholder}>
              <Text style={s.chartPlaceholderText}>No chart data</Text>
            </View>
          )}
        </View>

        {/* Divider */}
        <View style={s.divider} />

        {/* Buying Power */}
        <View style={s.buyingPowerRow}>
          <Text style={s.buyingPowerLabel}>Buying Power</Text>
          <Text style={s.buyingPowerValue}>$0.00</Text>
        </View>

        {/* HFT & Bot Earnings */}
        {(hftPnl !== 0 || botPnl !== 0) && (
          <>
            <View style={s.divider} />
            <View style={s.earningsSection}>
              {hftPnl !== 0 && (
                <View style={s.earningsRow}>
                  <View style={s.earningsLeft}>
                    <Ionicons name="pulse" size={16} color={colors.accent.cyan} />
                    <Text style={s.earningsLabel}>HFT Engine</Text>
                  </View>
                  <Text style={[s.earningsValue, { color: hftPnl >= 0 ? colors.green.text : colors.red.text }]}>
                    {hftPnl >= 0 ? '+' : ''}${formatCurrency(Math.abs(hftPnl))}
                  </Text>
                </View>
              )}
              {botPnl !== 0 && (
                <View style={s.earningsRow}>
                  <View style={s.earningsLeft}>
                    <Ionicons name="git-compare" size={16} color={colors.accent.purple} />
                    <Text style={s.earningsLabel}>Arb Bot</Text>
                  </View>
                  <Text style={[s.earningsValue, { color: botPnl >= 0 ? colors.green.text : colors.red.text }]}>
                    {botPnl >= 0 ? '+' : ''}${formatCurrency(Math.abs(botPnl))}
                  </Text>
                </View>
              )}
            </View>
          </>
        )}

        <View style={s.divider} />

        {/* Stocks Section */}
        <Text style={s.sectionTitle}>Stocks</Text>
        {holdings.map((h: any) => {
          const realPrice = getPrice(h.symbol, h.current_price);
          const pnl = (realPrice - h.avg_cost) / h.avg_cost * 100;
          const stockUp = pnl >= 0;
          const quote = realQuotes[h.symbol];
          const sparkPrices = quote?.sparkline || [];

          return (
            <TouchableOpacity
              key={h.symbol}
              style={s.stockRow}
              onPress={() => router.push(`/stock/${h.symbol}` as any)}
              activeOpacity={0.6}
            >
              <View style={s.stockLeft}>
                <Text style={s.stockSymbol}>{h.symbol}</Text>
                <Text style={s.stockShares}>{h.shares} shares</Text>
              </View>
              <View style={s.stockMid}>
                <Sparkline
                  data={sparkPrices.length > 2 ? sparkPrices : [h.avg_cost, realPrice]}
                  width={56}
                  height={24}
                  color={stockUp ? colors.green.primary : colors.red.primary}
                />
              </View>
              <View style={s.stockRight}>
                <Text style={s.stockPrice}>${realPrice.toFixed(2)}</Text>
                <View style={[s.pnlBadge, { backgroundColor: stockUp ? colors.green.soft : colors.red.soft }]}>
                  <Text style={[s.pnlBadgeText, { color: stockUp ? colors.green.text : colors.red.text }]}>
                    {stockUp ? '+' : ''}{pnl.toFixed(2)}%
                  </Text>
                </View>
              </View>
            </TouchableOpacity>
          );
        })}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const createStyles = (t: ThemeColors) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: t.bg.primary },
  scroll: { flex: 1 },
  content: { paddingHorizontal: SPACING.lg },
  loadingText: { color: t.text.tertiary, fontSize: FONT_SIZES.sm },

  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingTop: SPACING.sm, marginBottom: SPACING.md },
  headerTitle: { fontSize: FONT_SIZES.xxxl, fontWeight: '800', color: t.text.primary, letterSpacing: -0.5 },
  themeBtn: { width: 40, height: 40, borderRadius: 20, justifyContent: 'center', alignItems: 'center' },

  heroAmount: { fontSize: FONT_SIZES.hero, fontWeight: '800', color: t.text.primary, letterSpacing: -1.5 },
  heroPnl: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4, marginBottom: SPACING.lg },
  heroPnlText: { fontSize: FONT_SIZES.base, fontWeight: '600' },
  heroPnlPct: { fontSize: FONT_SIZES.sm, fontWeight: '500' },

  chartContainer: { marginBottom: SPACING.md, alignItems: 'center', overflow: 'hidden' },
  chartPlaceholder: { height: 180, justifyContent: 'center', alignItems: 'center' },
  chartPlaceholderText: { color: t.text.muted, fontSize: FONT_SIZES.sm },

  divider: { height: 0.5, backgroundColor: t.border, marginVertical: SPACING.md },

  buyingPowerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: SPACING.sm },
  buyingPowerLabel: { fontSize: FONT_SIZES.base, fontWeight: '600', color: t.text.primary },
  buyingPowerValue: { fontSize: FONT_SIZES.base, fontWeight: '600', color: t.text.primary },

  earningsSection: { gap: SPACING.sm },
  earningsRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 6 },
  earningsLeft: { flexDirection: 'row', alignItems: 'center', gap: SPACING.sm },
  earningsLabel: { fontSize: FONT_SIZES.base, fontWeight: '600', color: t.text.secondary },
  earningsValue: { fontSize: FONT_SIZES.base, fontWeight: '700' },

  sectionTitle: { fontSize: FONT_SIZES.lg, fontWeight: '700', color: t.text.primary, marginBottom: SPACING.md, marginTop: SPACING.sm },

  stockRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 14, borderBottomWidth: 0.5, borderBottomColor: t.border },
  stockLeft: { flex: 1 },
  stockSymbol: { fontSize: FONT_SIZES.base, fontWeight: '700', color: t.text.primary },
  stockShares: { fontSize: FONT_SIZES.xs, color: t.text.tertiary, marginTop: 2 },
  stockMid: { width: 70, alignItems: 'center', marginHorizontal: SPACING.sm },
  stockRight: { alignItems: 'flex-end', minWidth: 80 },
  stockPrice: { fontSize: FONT_SIZES.base, fontWeight: '600', color: t.text.primary },
  pnlBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, marginTop: 3 },
  pnlBadgeText: { fontSize: FONT_SIZES.xs, fontWeight: '700' },
});
