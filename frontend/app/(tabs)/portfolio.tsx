import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LineChart } from 'react-native-gifted-charts';
import { COLORS, SPACING, FONT_SIZES, RADIUS } from '../../src/theme';
import { api } from '../../src/api';
import GlassCard from '../../src/components/GlassCard';
import LoadingScreen from '../../src/components/LoadingScreen';

export default function PortfolioScreen() {
  const [data, setData] = useState<any>(null);
  const [risk, setRisk] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [portfolio, riskData] = await Promise.all([api.getPortfolio(), api.getRisk()]);
      setData(portfolio);
      setRisk(riskData);
    } catch (e) {
      console.error('Portfolio fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);
  const onRefresh = () => { setRefreshing(true); fetchData(); };

  if (loading) return <LoadingScreen message="Loading portfolio..." />;

  const isUp = (data?.total_pnl || 0) >= 0;
  const pnlColor = isUp ? COLORS.green.text : COLORS.red.text;
  const chartColor = isUp ? COLORS.green.primary : COLORS.red.primary;
  const chartData = (data?.history || []).map((h: any) => ({ value: h.value }));

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.accent.blue} />}
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.title}>Portfolio</Text>

        {/* Hero Value — Robinhood-style */}
        <View style={styles.hero}>
          <Text style={styles.heroAmount}>
            ${(data?.total_value || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </Text>
          <View style={styles.heroPnl}>
            <Ionicons name={isUp ? 'arrow-up' : 'arrow-down'} size={14} color={pnlColor} />
            <Text style={[styles.heroPnlText, { color: pnlColor }]}>
              ${Math.abs(data?.total_pnl || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </Text>
            <Text style={[styles.heroPnlPct, { color: pnlColor }]}>
              ({isUp ? '+' : ''}{data?.total_pnl_pct || 0}%)
            </Text>
          </View>
        </View>

        {/* Chart */}
        {chartData.length > 0 && (
          <View style={styles.chartWrap}>
            <LineChart
              data={chartData}
              width={320}
              height={160}
              spacing={10}
              color={chartColor}
              thickness={2.5}
              hideDataPoints
              hideYAxisText
              hideAxesAndRules
              curved
              areaChart
              startFillColor={chartColor}
              startOpacity={0.2}
              endFillColor={COLORS.bg.primary}
              endOpacity={0}
              initialSpacing={0}
              adjustToWidth
            />
          </View>
        )}

        {/* Risk Metrics */}
        {risk && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Risk</Text>
            <View style={styles.metricsRow}>
              {[
                { label: 'Sharpe', value: risk.sharpe_ratio },
                { label: 'Beta', value: risk.beta },
                { label: 'VaR 95%', value: `$${(risk.var_95 || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`, color: COLORS.red.text },
                { label: 'Volatility', value: `${risk.volatility}%` },
              ].map((m, i) => (
                <GlassCard key={i} style={styles.metricCard}>
                  <Text style={styles.metricLabel}>{m.label}</Text>
                  <Text style={[styles.metricValue, m.color ? { color: m.color } : null]}>{m.value}</Text>
                </GlassCard>
              ))}
            </View>

            {risk.alerts?.length > 0 && risk.alerts.map((a: any, i: number) => (
              <View key={i} style={styles.alertRow}>
                <Ionicons
                  name={a.level === 'warning' ? 'alert-circle' : 'information-circle'}
                  size={16}
                  color={a.level === 'warning' ? COLORS.accent.amber : COLORS.accent.blue}
                />
                <Text style={styles.alertText}>{a.message}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Holdings */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Holdings</Text>
            <Text style={styles.sectionCount}>{(data?.holdings || []).length}</Text>
          </View>
          {(data?.holdings || []).map((h: any, i: number) => {
            const hUp = h.pnl >= 0;
            return (
              <GlassCard key={i} style={styles.holdingCard}>
                <View style={styles.holdingTop}>
                  <View>
                    <Text style={styles.holdingSymbol}>{h.symbol}</Text>
                    <Text style={styles.holdingName}>{h.name}</Text>
                  </View>
                  <View style={styles.holdingRight}>
                    <Text style={styles.holdingValue}>
                      ${h.market_value?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </Text>
                    <View style={styles.holdingPnlRow}>
                      <Ionicons name={hUp ? 'arrow-up' : 'arrow-down'} size={10} color={hUp ? COLORS.green.text : COLORS.red.text} />
                      <Text style={[styles.holdingPnl, { color: hUp ? COLORS.green.text : COLORS.red.text }]}>
                        {hUp ? '+' : ''}{h.pnl_pct?.toFixed(1)}%
                      </Text>
                    </View>
                  </View>
                </View>
                <View style={styles.holdingMeta}>
                  <Text style={styles.holdingDetail}>{h.shares} shares</Text>
                  <Text style={styles.holdingDetail}>Avg ${h.avg_cost?.toFixed(2)}</Text>
                  <Text style={styles.holdingDetail}>Now ${h.current_price?.toFixed(2)}</Text>
                </View>
              </GlassCard>
            );
          })}
        </View>

        {/* Sector Allocation */}
        {risk?.sector_allocation?.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Allocation</Text>
            <GlassCard>
              {risk.sector_allocation.map((s: any, i: number) => {
                const colors = [COLORS.accent.blue, COLORS.accent.purple, COLORS.green.primary, COLORS.accent.amber, COLORS.accent.cyan];
                return (
                  <View key={i} style={styles.sectorRow}>
                    <Text style={styles.sectorName}>{s.sector}</Text>
                    <View style={styles.sectorBarWrap}>
                      <View style={[styles.sectorBar, { width: `${s.pct}%`, backgroundColor: colors[i % colors.length] }]} />
                    </View>
                    <Text style={styles.sectorPct}>{s.pct}%</Text>
                  </View>
                );
              })}
            </GlassCard>
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg.primary },
  scroll: { flex: 1 },
  content: { paddingHorizontal: SPACING.lg, paddingTop: SPACING.sm },
  title: { fontSize: FONT_SIZES.xxxl, fontWeight: '800', color: COLORS.text.primary, letterSpacing: -0.5, marginBottom: SPACING.xl },

  hero: { marginBottom: SPACING.lg },
  heroAmount: { fontSize: FONT_SIZES.hero, fontWeight: '800', color: COLORS.text.primary, letterSpacing: -1.5 },
  heroPnl: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 6 },
  heroPnlText: { fontSize: FONT_SIZES.base, fontWeight: '600' },
  heroPnlPct: { fontSize: FONT_SIZES.sm },

  chartWrap: { alignItems: 'center', overflow: 'hidden', marginBottom: SPACING.xl },

  section: { marginBottom: SPACING.xl },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: SPACING.md },
  sectionTitle: { fontSize: FONT_SIZES.lg, fontWeight: '700', color: COLORS.text.primary, marginBottom: SPACING.md },
  sectionCount: { fontSize: FONT_SIZES.sm, color: COLORS.text.muted },

  metricsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACING.sm, marginBottom: SPACING.md },
  metricCard: { width: '47%' as any },
  metricLabel: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginBottom: 4 },
  metricValue: { fontSize: FONT_SIZES.xxl, fontWeight: '800', color: COLORS.text.primary, letterSpacing: -0.5 },

  alertRow: { flexDirection: 'row', alignItems: 'center', gap: SPACING.sm, paddingVertical: SPACING.sm, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: COLORS.glass.border },
  alertText: { flex: 1, fontSize: FONT_SIZES.sm, color: COLORS.text.secondary },

  holdingCard: { marginBottom: SPACING.sm },
  holdingTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  holdingSymbol: { fontSize: FONT_SIZES.xl, fontWeight: '800', color: COLORS.text.primary },
  holdingName: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 2 },
  holdingRight: { alignItems: 'flex-end' },
  holdingValue: { fontSize: FONT_SIZES.base, fontWeight: '700', color: COLORS.text.primary },
  holdingPnlRow: { flexDirection: 'row', alignItems: 'center', gap: 2, marginTop: 3 },
  holdingPnl: { fontSize: FONT_SIZES.sm, fontWeight: '600' },
  holdingMeta: { flexDirection: 'row', gap: SPACING.lg, marginTop: SPACING.md },
  holdingDetail: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted },

  sectorRow: { flexDirection: 'row', alignItems: 'center', gap: SPACING.sm, marginBottom: SPACING.md },
  sectorName: { width: 100, fontSize: FONT_SIZES.sm, color: COLORS.text.secondary },
  sectorBarWrap: { flex: 1, height: 5, backgroundColor: COLORS.glass.fill, borderRadius: 3, overflow: 'hidden' },
  sectorBar: { height: '100%', borderRadius: 3 },
  sectorPct: { width: 40, fontSize: FONT_SIZES.sm, color: COLORS.text.secondary, textAlign: 'right' },
});
