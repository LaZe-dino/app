import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl,
  TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import Svg, { Polyline } from 'react-native-svg';
import { useTheme } from '../../src/contexts/ThemeContext';
import { ThemeColors, SPACING, FONT_SIZES, RADIUS } from '../../src/theme';
import { api } from '../../src/api';

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

export default function PortfolioScreen() {
  const { colors } = useTheme();
  const router = useRouter();
  const [portfolio, setPortfolio] = useState<any>(null);
  const [risk, setRisk] = useState<any>(null);
  const [realQuotes, setRealQuotes] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [portfolioRes, riskRes] = await Promise.all([
        api.getPortfolio(),
        api.getRisk(),
      ]);
      setPortfolio(portfolioRes);
      setRisk(riskRes);
      const symbols = (portfolioRes.holdings || []).map((h: any) => h.symbol);
      if (symbols.length > 0) {
        try {
          const quotes = await api.getBatchQuotes(symbols);
          setRealQuotes(quotes);
        } catch { /* use fallback */ }
      }
    } catch (e) {
      console.error('Portfolio fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);
  const onRefresh = () => { setRefreshing(true); fetchData(); };

  const s = useMemo(() => createStyles(colors), [colors]);

  const holdings = portfolio?.holdings || [];
  const getPrice = (sym: string, fallback: number) => realQuotes[sym]?.price || fallback;

  const totalValue = useMemo(() => {
    if (!holdings.length) return portfolio?.total_value || 0;
    return holdings.reduce((sum: number, h: any) => sum + getPrice(h.symbol, h.current_price) * h.shares, 0);
  }, [holdings, realQuotes, portfolio]);

  const totalCost = portfolio?.total_cost || 0;
  const totalPnl = totalValue - totalCost;
  const totalPnlPct = totalCost ? ((totalPnl / totalCost) * 100) : 0;
  const isUp = totalPnl >= 0;

  if (loading) {
    return (
      <SafeAreaView style={[s.safe, { justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator size="small" color={colors.green.primary} />
        <Text style={{ color: colors.text.tertiary, fontSize: FONT_SIZES.sm, marginTop: 12 }}>
          Loading portfolio...
        </Text>
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
          <Text style={s.totalValue}>${formatCurrency(totalValue)}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 }}>
            <Ionicons name={isUp ? 'arrow-up' : 'arrow-down'} size={12} color={isUp ? colors.green.text : colors.red.text} />
            <Text style={{ fontSize: FONT_SIZES.sm, fontWeight: '600', color: isUp ? colors.green.text : colors.red.text }}>
              ${formatCurrency(Math.abs(totalPnl))} ({isUp ? '+' : ''}{totalPnlPct.toFixed(2)}%)
            </Text>
          </View>
          <Text style={s.totalLabel}>Total Portfolio Value</Text>
        </View>

        {/* P&L Breakdown */}
        {(portfolio?.hft_pnl || portfolio?.bot_pnl) ? (
          <View style={{ marginBottom: SPACING.xl }}>
            <Text style={s.sectionTitle}>P&L Breakdown</Text>
            <View style={{ backgroundColor: colors.card, borderRadius: RADIUS.md, padding: SPACING.md, borderWidth: 0.5, borderColor: colors.border }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 }}>
                <Text style={{ fontSize: FONT_SIZES.sm, color: colors.text.secondary }}>Stock Holdings</Text>
                <Text style={{ fontSize: FONT_SIZES.sm, fontWeight: '700', color: (totalPnl - (portfolio?.hft_pnl || 0) - (portfolio?.bot_pnl || 0)) >= 0 ? colors.green.text : colors.red.text }}>
                  ${formatCurrency(portfolio?.stock_value || totalValue)}
                </Text>
              </View>
              {portfolio?.hft_pnl !== 0 && (
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 }}>
                  <Text style={{ fontSize: FONT_SIZES.sm, color: colors.text.secondary }}>HFT Engine P&L</Text>
                  <Text style={{ fontSize: FONT_SIZES.sm, fontWeight: '700', color: portfolio.hft_pnl >= 0 ? colors.green.text : colors.red.text }}>
                    {portfolio.hft_pnl >= 0 ? '+' : ''}${formatCurrency(Math.abs(portfolio.hft_pnl))}
                  </Text>
                </View>
              )}
              {portfolio?.bot_pnl !== 0 && (
                <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                  <Text style={{ fontSize: FONT_SIZES.sm, color: colors.text.secondary }}>Arb Bot P&L</Text>
                  <Text style={{ fontSize: FONT_SIZES.sm, fontWeight: '700', color: portfolio.bot_pnl >= 0 ? colors.green.text : colors.red.text }}>
                    {portfolio.bot_pnl >= 0 ? '+' : ''}${formatCurrency(Math.abs(portfolio.bot_pnl))}
                  </Text>
                </View>
              )}
            </View>
          </View>
        ) : null}

        {/* Stocks List */}
        <Text style={s.sectionTitle}>Stocks</Text>
        {holdings.map((h: any) => {
          const realPrice = getPrice(h.symbol, h.current_price);
          const pnlPct = ((realPrice - h.avg_cost) / h.avg_cost) * 100;
          const stockUp = pnlPct >= 0;
          const sparkPrices = realQuotes[h.symbol]?.sparkline || [h.avg_cost, realPrice];

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
                  data={sparkPrices}
                  width={56}
                  height={24}
                  color={stockUp ? colors.green.primary : colors.red.primary}
                />
              </View>
              <View style={s.stockRight}>
                <View style={[s.pnlBadge, { backgroundColor: stockUp ? colors.green.soft : colors.red.soft }]}>
                  <Text style={[s.pnlBadgeText, { color: stockUp ? colors.green.text : colors.red.text }]}>
                    {stockUp ? '+' : ''}{pnlPct.toFixed(2)}%
                  </Text>
                </View>
              </View>
            </TouchableOpacity>
          );
        })}

        {/* Risk Section */}
        {risk && (
          <>
            <View style={s.divider} />
            <Text style={s.sectionTitle}>Risk Metrics</Text>
            <View style={s.riskGrid}>
              {[
                { label: 'Sharpe Ratio', value: risk.sharpe_ratio?.toFixed(2) || '—' },
                { label: 'Beta', value: risk.beta?.toFixed(2) || '—' },
                { label: 'VaR (95%)', value: `$${(risk.var_95 || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`, color: colors.red.text },
                { label: 'Volatility', value: `${risk.volatility || 0}%` },
                { label: 'Max Drawdown', value: `${risk.max_drawdown || 0}%`, color: colors.red.text },
              ].map((m, i) => (
                <View key={i} style={s.riskItem}>
                  <Text style={s.riskLabel}>{m.label}</Text>
                  <Text style={[s.riskValue, m.color ? { color: m.color } : undefined]}>{m.value}</Text>
                </View>
              ))}
            </View>
          </>
        )}

        {/* Allocation */}
        {risk?.sector_allocation?.length > 0 && (
          <>
            <View style={s.divider} />
            <Text style={s.sectionTitle}>Allocation</Text>
            {risk.sector_allocation.map((sec: any, i: number) => {
              const barColors = [colors.green.primary, colors.accent.blue, colors.accent.purple, colors.accent.amber, colors.accent.cyan];
              return (
                <View key={i} style={s.allocRow}>
                  <Text style={s.allocName}>{sec.sector}</Text>
                  <View style={s.allocBarBg}>
                    <View style={[s.allocBar, { width: `${sec.pct}%`, backgroundColor: barColors[i % barColors.length] }]} />
                  </View>
                  <Text style={s.allocPct}>{sec.pct}%</Text>
                </View>
              );
            })}
          </>
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

  header: { alignItems: 'flex-end', paddingTop: SPACING.sm, marginBottom: SPACING.xl },
  totalValue: { fontSize: FONT_SIZES.xxxl, fontWeight: '800', color: t.text.primary },
  totalLabel: { fontSize: FONT_SIZES.sm, color: t.text.tertiary, marginTop: 2 },

  sectionTitle: { fontSize: FONT_SIZES.lg, fontWeight: '700', color: t.text.primary, marginBottom: SPACING.md },

  stockRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 14, borderBottomWidth: 0.5, borderBottomColor: t.border },
  stockLeft: { flex: 1 },
  stockSymbol: { fontSize: FONT_SIZES.base, fontWeight: '700', color: t.text.primary },
  stockShares: { fontSize: FONT_SIZES.xs, color: t.text.tertiary, marginTop: 2 },
  stockMid: { width: 70, alignItems: 'center', marginHorizontal: SPACING.sm },
  stockRight: { alignItems: 'flex-end' },
  pnlBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 4 },
  pnlBadgeText: { fontSize: FONT_SIZES.sm, fontWeight: '700' },

  divider: { height: 0.5, backgroundColor: t.border, marginVertical: SPACING.xl },

  riskGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACING.md },
  riskItem: { width: '47%' as any, backgroundColor: t.card, borderRadius: RADIUS.md, padding: SPACING.md, borderWidth: 0.5, borderColor: t.border },
  riskLabel: { fontSize: FONT_SIZES.xs, color: t.text.tertiary, marginBottom: 4 },
  riskValue: { fontSize: FONT_SIZES.xxl, fontWeight: '800', color: t.text.primary },

  allocRow: { flexDirection: 'row', alignItems: 'center', gap: SPACING.sm, marginBottom: SPACING.md },
  allocName: { width: 100, fontSize: FONT_SIZES.sm, color: t.text.secondary },
  allocBarBg: { flex: 1, height: 6, backgroundColor: t.bg.tertiary, borderRadius: 3, overflow: 'hidden' },
  allocBar: { height: '100%', borderRadius: 3 },
  allocPct: { width: 40, fontSize: FONT_SIZES.sm, color: t.text.secondary, textAlign: 'right', fontWeight: '600' },
});
