import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, FONT_SIZES, RADIUS } from '../../src/theme';
import { api, hftWS } from '../../src/api';
import GlassCard from '../../src/components/GlassCard';

function MetricBox({ label, value, unit, color }: { label: string; value: string | number; unit?: string; color?: string }) {
  return (
    <View style={metricStyles.box}>
      <Text style={metricStyles.label}>{label}</Text>
      <Text style={[metricStyles.value, color ? { color } : undefined]}>
        {value}{unit ? <Text style={metricStyles.unit}>{unit}</Text> : null}
      </Text>
    </View>
  );
}

const metricStyles = StyleSheet.create({
  box: { flex: 1, alignItems: 'center', paddingVertical: SPACING.sm },
  label: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, fontWeight: '600', letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 4 },
  value: { fontSize: FONT_SIZES.xl, fontWeight: '800', color: COLORS.text.primary, fontVariant: ['tabular-nums'] },
  unit: { fontSize: FONT_SIZES.xs, fontWeight: '500', color: COLORS.text.tertiary },
});

export default function HFTScreen() {
  const [dashboard, setDashboard] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const result = await api.getHFTDashboard();
      setDashboard(result);
    } catch (e) {
      console.error('HFT dashboard fetch error:', e);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const unsub = hftWS.subscribe((msg) => {
      if (msg.type === 'hft_dashboard' || msg.system_health) {
        setDashboard(msg);
        setWsConnected(true);
      }
    });
    return unsub;
  }, []);

  const onRefresh = () => { setRefreshing(true); fetchData(); };

  const health = dashboard?.system_health || {};
  const ttt = dashboard?.tick_to_trade || {};
  const network = dashboard?.network || {};
  const fpga = dashboard?.fpga || {};
  const strategies = dashboard?.strategies || {};
  const mm = strategies.market_making || {};
  const arb = strategies.arbitrage || {};
  const risk = dashboard?.risk || {};
  const positions = dashboard?.positions?.summary || {};
  const execution = dashboard?.execution || {};
  const venues = execution.venues || {};
  const mmTable = dashboard?.market_making_table || [];
  const latency = dashboard?.latency_breakdown || {};

  const isHalted = health.status === 'HALTED';

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.accent.cyan} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.headerTitle}>HFT Engine</Text>
            <Text style={styles.headerSub}>Co-Location NY5 · Sub-Microsecond Pipeline</Text>
          </View>
          <View style={[styles.statusPill, isHalted ? styles.statusHalted : styles.statusActive]}>
            <View style={[styles.statusDot, isHalted ? styles.dotHalted : styles.dotActive]} />
            <Text style={[styles.statusLabel, isHalted ? styles.labelHalted : styles.labelActive]}>
              {isHalted ? 'HALTED' : 'ACTIVE'}
            </Text>
          </View>
        </View>

        {/* Tick-to-Trade Hero */}
        <GlassCard variant="elevated" style={styles.heroCard}>
          <Text style={styles.heroLabel}>TICK-TO-TRADE LATENCY</Text>
          <View style={styles.heroRow}>
            <View style={styles.heroMain}>
              <Text style={styles.heroValue}>{ttt.p50_us || '—'}</Text>
              <Text style={styles.heroUnit}>µs p50</Text>
            </View>
            <View style={styles.heroDivider} />
            <MetricBox label="p95" value={ttt.p95_us || '—'} unit="µs" />
            <MetricBox label="p99" value={ttt.p99_us || '—'} unit="µs" />
            <MetricBox label="p99.9" value={ttt.p999_us || '—'} unit="µs" />
          </View>
        </GlassCard>

        {/* System Throughput */}
        <View style={styles.metricsRow}>
          <GlassCard style={styles.metricCard}>
            <MetricBox label="Events/s" value={Math.round(health.events_per_second || 0)} color={COLORS.accent.cyan} />
          </GlassCard>
          <GlassCard style={styles.metricCard}>
            <MetricBox label="Orders/s" value={Math.round(health.orders_per_second || 0)} color={COLORS.accent.blue} />
          </GlassCard>
          <GlassCard style={styles.metricCard}>
            <MetricBox label="Msgs/s" value={Math.round(network.messages_per_second || 0)} color={COLORS.accent.purple} />
          </GlassCard>
        </View>

        {/* FPGA Pipeline */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>FPGA Acceleration</Text>
          <GlassCard>
            <View style={styles.fpgaHeader}>
              <View style={styles.fpgaChipIcon}>
                <Ionicons name="hardware-chip" size={24} color={COLORS.accent.purple} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.fpgaTitle}>{fpga.enabled ? '250MHz 8-Stage Pipeline' : 'Disabled'}</Text>
                <Text style={styles.fpgaMeta}>{fpga.ticks_processed?.toLocaleString() || 0} ticks · {fpga.signals_generated || 0} signals · {fpga.avg_pipeline_ns || 0}ns avg</Text>
              </View>
            </View>
            {fpga.pipeline_stages && (
              <View style={styles.pipelineRow}>
                {fpga.pipeline_stages.map((stage: any, i: number) => (
                  <View key={i} style={styles.pipelineStage}>
                    <View style={[styles.pipelineBar, { height: Math.max(4, Math.min(32, stage.target_ns * 3)) }]} />
                    <Text style={styles.pipelineName}>{stage.name.replace('_', '\n')}</Text>
                    <Text style={styles.pipelineNs}>{stage.target_ns}ns</Text>
                  </View>
                ))}
              </View>
            )}
            {fpga.arbitrage_opportunities > 0 && (
              <View style={styles.arbBanner}>
                <Ionicons name="flash" size={14} color={COLORS.accent.amber} />
                <Text style={styles.arbText}>{fpga.arbitrage_opportunities} arbitrage opportunities detected</Text>
              </View>
            )}
          </GlassCard>
        </View>

        {/* Strategies */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Strategy Performance</Text>
          <View style={styles.stratRow}>
            <GlassCard style={styles.stratCard}>
              <View style={styles.stratHeader}>
                <Ionicons name="swap-horizontal" size={18} color={COLORS.accent.blue} />
                <Text style={styles.stratLabel}>Market Making</Text>
              </View>
              <Text style={[styles.stratPnl, { color: (mm.total_pnl || 0) >= 0 ? COLORS.green.text : COLORS.red.text }]}>
                ${(mm.total_pnl || 0).toFixed(2)}
              </Text>
              <Text style={styles.stratMeta}>{mm.total_trades || 0} trades · {mm.active_quotes || 0} quotes</Text>
            </GlassCard>
            <GlassCard style={styles.stratCard}>
              <View style={styles.stratHeader}>
                <Ionicons name="git-compare" size={18} color={COLORS.accent.amber} />
                <Text style={styles.stratLabel}>Arbitrage</Text>
              </View>
              <Text style={[styles.stratPnl, { color: COLORS.green.text }]}>
                ${(arb.theoretical_profit || 0).toFixed(2)}
              </Text>
              <Text style={styles.stratMeta}>{arb.opportunities || 0} opps · {arb.hit_rate || 0}% rate</Text>
            </GlassCard>
          </View>
        </View>

        {/* Market Making Table */}
        {mmTable.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Market Making Book</Text>
            <GlassCard>
              <View style={styles.tableHeader}>
                <Text style={[styles.th, { flex: 1.2 }]}>Stock</Text>
                <Text style={[styles.th, { flex: 1 }]}>Buy</Text>
                <Text style={[styles.th, { flex: 1 }]}>Sell</Text>
                <Text style={[styles.th, { flex: 0.7 }]}>Spread</Text>
                <Text style={[styles.th, { flex: 0.7 }]}>Trades</Text>
                <Text style={[styles.th, { flex: 1 }]}>Profit</Text>
              </View>
              {mmTable.slice(0, 12).map((row: any, i: number) => (
                <View key={i} style={[styles.tableRow, i % 2 === 0 && styles.tableRowAlt]}>
                  <Text style={[styles.td, styles.tdSymbol, { flex: 1.2 }]}>{row.stock}</Text>
                  <Text style={[styles.td, { flex: 1 }]}>${row.buy_price?.toFixed(2)}</Text>
                  <Text style={[styles.td, { flex: 1 }]}>${row.sell_price?.toFixed(2)}</Text>
                  <Text style={[styles.td, { flex: 0.7 }]}>${row.spread?.toFixed(2)}</Text>
                  <Text style={[styles.td, { flex: 0.7 }]}>{(row.trades_executed || 0).toLocaleString()}</Text>
                  <Text style={[styles.td, styles.tdProfit, { flex: 1, color: (row.profit || 0) >= 0 ? COLORS.green.text : COLORS.red.text }]}>
                    ${(row.profit || 0).toFixed(2)}
                  </Text>
                </View>
              ))}
            </GlassCard>
          </View>
        )}

        {/* Risk Engine */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Risk Engine</Text>
          <GlassCard>
            <View style={styles.riskRow}>
              <MetricBox label="Checks" value={(risk.checks_run || 0).toLocaleString()} />
              <MetricBox label="Pass Rate" value={`${risk.pass_rate || 0}%`} color={risk.pass_rate > 95 ? COLORS.green.text : COLORS.accent.amber} />
              <MetricBox label="Check µs" value={risk.avg_check_latency_us || 0} color={COLORS.accent.cyan} />
              <MetricBox label="Daily P&L" value={`$${(risk.daily_pnl || 0).toFixed(0)}`} color={(risk.daily_pnl || 0) >= 0 ? COLORS.green.text : COLORS.red.text} />
            </View>
            {risk.circuit_breaker && (
              <View style={styles.circuitBreaker}>
                <Ionicons name="warning" size={16} color={COLORS.red.primary} />
                <Text style={styles.cbText}>CIRCUIT BREAKER ACTIVE — Trading halted</Text>
              </View>
            )}
          </GlassCard>
        </View>

        {/* Venue Performance */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Exchange Venues</Text>
          <GlassCard>
            {Object.entries(venues).map(([name, v]: [string, any], i: number) => (
              <View key={name} style={[styles.venueRow, i > 0 && styles.venueBorder]}>
                <View style={styles.venueName}>
                  <Text style={styles.venueLabel}>{name}</Text>
                  <Text style={styles.venueLatency}>{v.wire_latency_us}µs wire</Text>
                </View>
                <View style={styles.venueStats}>
                  <Text style={styles.venueStat}>{v.orders_sent || 0} sent</Text>
                  <Text style={[styles.venueStat, { color: COLORS.green.text }]}>{v.orders_filled || 0} filled</Text>
                  <Text style={styles.venueFee}>${(v.total_fees || 0).toFixed(2)} fees</Text>
                </View>
              </View>
            ))}
          </GlassCard>
        </View>

        {/* Position Summary */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Positions</Text>
          <GlassCard>
            <View style={styles.riskRow}>
              <MetricBox label="Active" value={positions.active_positions || 0} />
              <MetricBox label="Realized" value={`$${(positions.total_realized_pnl || 0).toFixed(0)}`} color={(positions.total_realized_pnl || 0) >= 0 ? COLORS.green.text : COLORS.red.text} />
              <MetricBox label="Unrealized" value={`$${(positions.total_unrealized_pnl || 0).toFixed(0)}`} color={(positions.total_unrealized_pnl || 0) >= 0 ? COLORS.green.text : COLORS.red.text} />
              <MetricBox label="Fills" value={(positions.fills_processed || 0).toLocaleString()} />
            </View>
          </GlassCard>
        </View>

        {/* Latency Breakdown */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Latency Breakdown</Text>
          <GlassCard>
            {Object.entries(latency).map(([stage, data]: [string, any], i: number) => {
              const avgUs = data?.avg_us || 0;
              const barWidth = Math.min(avgUs / 50 * 100, 100);
              return (
                <View key={stage} style={[styles.latencyRow, i > 0 && styles.latencyBorder]}>
                  <Text style={styles.latencyStage}>{stage.replace(/_/g, ' ')}</Text>
                  <View style={styles.latencyBarBg}>
                    <View style={[styles.latencyBar, { width: `${barWidth}%` }]} />
                  </View>
                  <Text style={styles.latencyValue}>{avgUs}µs</Text>
                </View>
              );
            })}
          </GlassCard>
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg.primary },
  scroll: { flex: 1 },
  content: { paddingHorizontal: SPACING.lg },

  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', paddingTop: SPACING.sm, marginBottom: SPACING.xl },
  headerTitle: { fontSize: FONT_SIZES.xxxl, fontWeight: '800', color: COLORS.text.primary, letterSpacing: -0.5 },
  headerSub: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 2, letterSpacing: 0.3 },

  statusPill: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 5, borderRadius: RADIUS.full, gap: 5 },
  statusActive: { backgroundColor: COLORS.green.soft },
  statusHalted: { backgroundColor: COLORS.red.soft },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  dotActive: { backgroundColor: COLORS.green.primary },
  dotHalted: { backgroundColor: COLORS.red.primary },
  statusLabel: { fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  labelActive: { color: COLORS.green.text },
  labelHalted: { color: COLORS.red.text },

  heroCard: { marginBottom: SPACING.xl },
  heroLabel: { fontSize: FONT_SIZES.xs, color: COLORS.accent.cyan, fontWeight: '700', letterSpacing: 1.5, marginBottom: SPACING.md },
  heroRow: { flexDirection: 'row', alignItems: 'center' },
  heroMain: { alignItems: 'center', paddingRight: SPACING.lg },
  heroValue: { fontSize: FONT_SIZES.hero, fontWeight: '800', color: COLORS.accent.cyan, fontVariant: ['tabular-nums'] },
  heroUnit: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 2 },
  heroDivider: { width: 1, height: 48, backgroundColor: COLORS.glass.border, marginHorizontal: SPACING.md },

  metricsRow: { flexDirection: 'row', gap: SPACING.sm, marginBottom: SPACING.xl },
  metricCard: { flex: 1 },

  section: { marginBottom: SPACING.xl },
  sectionTitle: { fontSize: FONT_SIZES.lg, fontWeight: '700', color: COLORS.text.primary, marginBottom: SPACING.md },

  fpgaHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACING.md, marginBottom: SPACING.md },
  fpgaChipIcon: { width: 44, height: 44, borderRadius: 22, backgroundColor: COLORS.accent.purpleSoft, justifyContent: 'center', alignItems: 'center' },
  fpgaTitle: { fontSize: FONT_SIZES.base, fontWeight: '700', color: COLORS.text.primary },
  fpgaMeta: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 2 },

  pipelineRow: { flexDirection: 'row', justifyContent: 'space-between', paddingTop: SPACING.md, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: COLORS.glass.border },
  pipelineStage: { alignItems: 'center', flex: 1 },
  pipelineBar: { width: 20, backgroundColor: COLORS.accent.purple, borderRadius: 4, marginBottom: 4 },
  pipelineName: { fontSize: 7, color: COLORS.text.muted, textAlign: 'center', lineHeight: 10 },
  pipelineNs: { fontSize: 8, color: COLORS.accent.purple, fontWeight: '700', marginTop: 1 },

  arbBanner: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: SPACING.md, paddingTop: SPACING.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: COLORS.glass.border },
  arbText: { fontSize: FONT_SIZES.xs, color: COLORS.accent.amber, fontWeight: '600' },

  stratRow: { flexDirection: 'row', gap: SPACING.sm },
  stratCard: { flex: 1 },
  stratHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: SPACING.sm },
  stratLabel: { fontSize: FONT_SIZES.sm, color: COLORS.text.secondary, fontWeight: '600' },
  stratPnl: { fontSize: FONT_SIZES.xxl, fontWeight: '800', fontVariant: ['tabular-nums'] },
  stratMeta: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 4 },

  tableHeader: { flexDirection: 'row', paddingBottom: SPACING.sm, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: COLORS.glass.border },
  th: { fontSize: 9, color: COLORS.accent.purple, fontWeight: '700', letterSpacing: 0.5, textTransform: 'uppercase' },
  tableRow: { flexDirection: 'row', paddingVertical: SPACING.sm },
  tableRowAlt: { backgroundColor: 'rgba(255,255,255,0.02)' },
  td: { fontSize: FONT_SIZES.xs, color: COLORS.text.secondary, fontVariant: ['tabular-nums'] },
  tdSymbol: { fontWeight: '700', color: COLORS.text.primary },
  tdProfit: { fontWeight: '700' },

  riskRow: { flexDirection: 'row' },
  circuitBreaker: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: SPACING.md, paddingTop: SPACING.sm, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: COLORS.glass.border },
  cbText: { fontSize: FONT_SIZES.xs, color: COLORS.red.text, fontWeight: '700' },

  venueRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: SPACING.sm },
  venueBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: COLORS.glass.border },
  venueName: {},
  venueLabel: { fontSize: FONT_SIZES.sm, color: COLORS.text.primary, fontWeight: '700' },
  venueLatency: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 1 },
  venueStats: { flexDirection: 'row', gap: SPACING.md, alignItems: 'center' },
  venueStat: { fontSize: FONT_SIZES.xs, color: COLORS.text.secondary },
  venueFee: { fontSize: FONT_SIZES.xs, color: COLORS.accent.amber },

  latencyRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: SPACING.sm },
  latencyBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: COLORS.glass.border },
  latencyStage: { flex: 1.5, fontSize: FONT_SIZES.xs, color: COLORS.text.secondary, textTransform: 'capitalize' },
  latencyBarBg: { flex: 2, height: 6, backgroundColor: COLORS.bg.tertiary, borderRadius: 3, overflow: 'hidden' },
  latencyBar: { height: '100%', backgroundColor: COLORS.accent.cyan, borderRadius: 3 },
  latencyValue: { flex: 0.8, fontSize: FONT_SIZES.xs, color: COLORS.accent.cyan, fontWeight: '700', textAlign: 'right', fontVariant: ['tabular-nums'] },
});
