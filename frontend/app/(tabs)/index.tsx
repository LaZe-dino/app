import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, FONT_SIZES, RADIUS } from '../../src/theme';
import { api, marketWS, swarmWS } from '../../src/api';
import GlassCard from '../../src/components/GlassCard';
import SignalBadge from '../../src/components/SignalBadge';
import LoadingScreen from '../../src/components/LoadingScreen';

export default function DashboardScreen() {
  const [data, setData] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [livePrices, setLivePrices] = useState<Record<string, any>>({});
  const [swarmEvents, setSwarmEvents] = useState<any[]>([]);
  const [wsConnected, setWsConnected] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const result = await api.getDashboard();
      setData(result);
    } catch (e) {
      console.error('Dashboard fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const unsubMarket = marketWS.subscribe((msg) => {
      if (msg.type === 'market_update') {
        setLivePrices(msg.data);
        setWsConnected(true);
      }
    });
    const unsubSwarm = swarmWS.subscribe((msg) => {
      if (msg.type === 'swarm_status') {
        setSwarmEvents((msg.data?.event_history || []).slice(-5));
      } else if (msg.event_type) {
        setSwarmEvents(prev => [...prev.slice(-9), msg]);
      }
    });
    return () => { unsubMarket(); unsubSwarm(); };
  }, []);

  const onRefresh = () => { setRefreshing(true); fetchData(); };

  if (loading) return <LoadingScreen message="Loading your portfolio..." />;

  const portfolio = data?.portfolio || {};
  const signals = data?.top_signals || [];
  const indices = data?.market_indices || [];
  const agents = data?.agents || {};
  const isUp = portfolio.total_pnl >= 0;
  const pnlColor = isUp ? COLORS.green.text : COLORS.red.text;

  const getLivePrice = (symbol: string) => livePrices[symbol]?.price;

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.accent.blue} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Investing</Text>
          <View style={styles.headerRight}>
            <View style={[styles.livePill, wsConnected && styles.livePillOn]}>
              <View style={[styles.liveDot, wsConnected && styles.liveDotOn]} />
              <Text style={[styles.liveLabel, wsConnected && styles.liveLabelOn]}>
                {wsConnected ? 'LIVE' : 'OFFLINE'}
              </Text>
            </View>
          </View>
        </View>

        {/* Portfolio Hero — Robinhood-style big number */}
        <View style={styles.hero}>
          <Text style={styles.heroAmount}>
            ${(portfolio.total_value || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </Text>
          <View style={styles.heroPnl}>
            <Ionicons
              name={isUp ? 'arrow-up' : 'arrow-down'}
              size={14}
              color={pnlColor}
            />
            <Text style={[styles.heroPnlText, { color: pnlColor }]}>
              ${Math.abs(portfolio.total_pnl || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </Text>
            <Text style={[styles.heroPnlPct, { color: pnlColor }]}>
              ({isUp ? '+' : ''}{portfolio.total_pnl_pct || 0}%)
            </Text>
            <Text style={styles.heroPnlPeriod}>Today</Text>
          </View>
        </View>

        {/* Market Indices */}
        <View style={styles.indicesRow}>
          {indices.map((idx: any, i: number) => {
            const live = getLivePrice(idx.symbol);
            const price = live || idx.price;
            const up = idx.change >= 0;
            return (
              <GlassCard key={i} style={styles.indexCard}>
                <Text style={styles.indexName}>{idx.name}</Text>
                <Text style={styles.indexPrice}>${price?.toFixed(2)}</Text>
                <View style={styles.indexChangeRow}>
                  <Ionicons
                    name={up ? 'arrow-up' : 'arrow-down'}
                    size={10}
                    color={up ? COLORS.green.text : COLORS.red.text}
                  />
                  <Text style={[styles.indexChange, { color: up ? COLORS.green.text : COLORS.red.text }]}>
                    {up ? '+' : ''}{idx.change?.toFixed(2)}
                  </Text>
                </View>
              </GlassCard>
            );
          })}
        </View>

        {/* Swarm Activity */}
        {swarmEvents.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Activity</Text>
            <GlassCard variant="subtle">
              {swarmEvents.slice(-4).reverse().map((evt: any, i: number) => (
                <View key={i} style={[styles.activityRow, i > 0 && styles.activityBorder]}>
                  <View style={styles.activityDot}>
                    <View style={[styles.activityDotInner, {
                      backgroundColor:
                        evt.event_type === 'trade_recommendation' ? COLORS.green.primary :
                        evt.event_type === 'price_spike' ? COLORS.accent.amber :
                        COLORS.accent.blue,
                    }]} />
                  </View>
                  <View style={styles.activityContent}>
                    <Text style={styles.activityType}>
                      {evt.event_type?.replace(/_/g, ' ')}{evt.symbol ? ` · ${evt.symbol}` : ''}
                    </Text>
                    <Text style={styles.activityMeta}>
                      {evt.source_agent}{evt.target_agent ? ` → ${evt.target_agent}` : ''}
                    </Text>
                  </View>
                  <Text style={styles.activityTime}>
                    {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                  </Text>
                </View>
              ))}
            </GlassCard>
          </View>
        )}

        {/* Top Signals */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>AI Signals</Text>
          {signals.length === 0 ? (
            <GlassCard variant="subtle">
              <Text style={styles.emptyText}>No signals yet</Text>
              <Text style={styles.emptySubtext}>Run analysis on the Research tab to generate signals</Text>
            </GlassCard>
          ) : (
            signals.map((sig: any, i: number) => (
              <GlassCard key={sig.id || i} style={styles.signalCard}>
                <View style={styles.signalTop}>
                  <View>
                    <Text style={styles.signalSymbol}>{sig.symbol}</Text>
                    <Text style={styles.signalPrice}>
                      ${(getLivePrice(sig.symbol) || sig.current_price)?.toFixed(2)}
                    </Text>
                  </View>
                  <SignalBadge action={sig.action} confidence={sig.confidence} />
                </View>
                <Text style={styles.signalReasoning} numberOfLines={2}>{sig.reasoning}</Text>
              </GlassCard>
            ))
          )}
        </View>

        {/* Agent Swarm */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Agent Swarm</Text>
          <GlassCard>
            <View style={styles.agentRow}>
              {[
                { name: 'Scout', icon: 'eye-outline', color: COLORS.accent.amber },
                { name: 'Analyst', icon: 'analytics-outline', color: COLORS.accent.blue },
                { name: 'News', icon: 'newspaper-outline', color: COLORS.accent.purple },
                { name: 'Strategist', icon: 'bulb-outline', color: COLORS.green.primary },
              ].map((ag, i) => (
                <View key={i} style={styles.agentItem}>
                  <View style={[styles.agentIcon, { backgroundColor: `${ag.color}14` }]}>
                    <Ionicons name={ag.icon as any} size={20} color={ag.color} />
                  </View>
                  <Text style={styles.agentLabel}>{ag.name}</Text>
                  <View style={[styles.agentPulse, { backgroundColor: COLORS.green.primary }]} />
                </View>
              ))}
            </View>
            <View style={styles.agentMeta}>
              <Text style={styles.agentMetaText}>
                {agents.total || 4} agents · {data?.reports_count || 0} reports
              </Text>
            </View>
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

  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingTop: SPACING.sm, marginBottom: SPACING.xl },
  headerTitle: { fontSize: FONT_SIZES.xxxl, fontWeight: '800', color: COLORS.text.primary, letterSpacing: -0.5 },
  headerRight: { flexDirection: 'row', gap: SPACING.sm },
  livePill: { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(255,71,87,0.10)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: RADIUS.full, gap: 5 },
  livePillOn: { backgroundColor: COLORS.green.soft },
  liveDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: COLORS.red.primary },
  liveDotOn: { backgroundColor: COLORS.green.primary },
  liveLabel: { fontSize: 9, fontWeight: '800', color: COLORS.red.text, letterSpacing: 1 },
  liveLabelOn: { color: COLORS.green.text },

  hero: { marginBottom: SPACING.xl },
  heroAmount: { fontSize: FONT_SIZES.hero, fontWeight: '800', color: COLORS.text.primary, letterSpacing: -1.5 },
  heroPnl: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 6 },
  heroPnlText: { fontSize: FONT_SIZES.base, fontWeight: '600' },
  heroPnlPct: { fontSize: FONT_SIZES.sm, fontWeight: '500' },
  heroPnlPeriod: { fontSize: FONT_SIZES.sm, color: COLORS.text.muted, marginLeft: 4 },

  indicesRow: { flexDirection: 'row', gap: SPACING.md, marginBottom: SPACING.xl },
  indexCard: { flex: 1 },
  indexName: { fontSize: FONT_SIZES.xs, color: COLORS.text.tertiary, marginBottom: 6 },
  indexPrice: { fontSize: FONT_SIZES.xl, fontWeight: '700', color: COLORS.text.primary, letterSpacing: -0.5 },
  indexChangeRow: { flexDirection: 'row', alignItems: 'center', gap: 3, marginTop: 4 },
  indexChange: { fontSize: FONT_SIZES.xs, fontWeight: '600' },

  section: { marginBottom: SPACING.xl },
  sectionTitle: { fontSize: FONT_SIZES.lg, fontWeight: '700', color: COLORS.text.primary, marginBottom: SPACING.md },

  activityRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: SPACING.sm + 2 },
  activityBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: COLORS.glass.border },
  activityDot: { width: 24, height: 24, borderRadius: 12, backgroundColor: COLORS.bg.tertiary, justifyContent: 'center', alignItems: 'center', marginRight: SPACING.md },
  activityDotInner: { width: 8, height: 8, borderRadius: 4 },
  activityContent: { flex: 1 },
  activityType: { fontSize: FONT_SIZES.sm, color: COLORS.text.primary, fontWeight: '500', textTransform: 'capitalize' },
  activityMeta: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 1 },
  activityTime: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted },

  signalCard: { marginBottom: SPACING.sm },
  signalTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  signalSymbol: { fontSize: FONT_SIZES.xl, fontWeight: '800', color: COLORS.text.primary },
  signalPrice: { fontSize: FONT_SIZES.sm, color: COLORS.text.tertiary, marginTop: 2 },
  signalReasoning: { fontSize: FONT_SIZES.sm, color: COLORS.text.secondary, lineHeight: 20, marginTop: SPACING.md },

  agentRow: { flexDirection: 'row', justifyContent: 'space-around' },
  agentItem: { alignItems: 'center', gap: SPACING.sm },
  agentIcon: { width: 48, height: 48, borderRadius: 24, justifyContent: 'center', alignItems: 'center' },
  agentLabel: { fontSize: FONT_SIZES.xs, color: COLORS.text.secondary, fontWeight: '600' },
  agentPulse: { width: 5, height: 5, borderRadius: 3 },
  agentMeta: { marginTop: SPACING.lg, alignItems: 'center' },
  agentMetaText: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted },

  emptyText: { fontSize: FONT_SIZES.base, color: COLORS.text.secondary, fontWeight: '600', textAlign: 'center' },
  emptySubtext: { fontSize: FONT_SIZES.sm, color: COLORS.text.muted, textAlign: 'center', marginTop: 4 },
});
