import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, FONT_SIZES, RADIUS } from '../../src/theme';
import { api, swarmWS } from '../../src/api';
import GlassCard from '../../src/components/GlassCard';
import LoadingScreen from '../../src/components/LoadingScreen';

const ICON: Record<string, string> = {
  scout: 'eye-outline',
  analyst: 'analytics-outline',
  news_hound: 'newspaper-outline',
  strategist: 'bulb-outline',
};
const CLR: Record<string, string> = {
  scout: COLORS.accent.amber,
  analyst: COLORS.accent.blue,
  news_hound: COLORS.accent.purple,
  strategist: COLORS.green.primary,
};
const STATUS_CLR: Record<string, string> = {
  active: COLORS.green.primary,
  processing: COLORS.accent.blue,
  idle: COLORS.text.muted,
  error: COLORS.red.primary,
};
const EVT_CLR: Record<string, string> = {
  price_spike: COLORS.accent.amber,
  volume_anomaly: COLORS.accent.amber,
  technical_signal: COLORS.accent.blue,
  sentiment_shift: COLORS.accent.purple,
  news_alert: COLORS.accent.purple,
  trade_recommendation: COLORS.green.primary,
  agent_status: COLORS.text.muted,
  swarm_cycle_complete: COLORS.green.primary,
};

export default function AgentsScreen() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [events, setEvents] = useState<any[]>([]);
  const [live, setLive] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const result = await api.getAgentsStatus();
      setData(result);
    } catch (e) {
      console.error('Agents fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const unsub = swarmWS.subscribe((msg) => {
      if (msg.type === 'swarm_status') {
        setData(msg.data);
        setLive(true);
        if (msg.data?.event_history) setEvents(msg.data.event_history.slice(-20));
      } else if (msg.event_type) {
        setEvents(prev => [...prev.slice(-19), msg]);
      }
    });
    return () => unsub();
  }, []);

  const onRefresh = () => { setRefreshing(true); fetchData(); };

  if (loading) return <LoadingScreen message="Connecting to swarm..." />;

  const agents = data?.agents || [];
  const summary = data?.summary || {};
  const rag = data?.rag_symbols || [];

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.accent.blue} />}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.headerRow}>
          <Text style={styles.title}>Agents</Text>
          <View style={[styles.livePill, live && styles.livePillOn]}>
            <View style={[styles.liveDot, live && styles.liveDotOn]} />
            <Text style={[styles.liveText, live && styles.liveTextOn]}>{live ? 'LIVE' : 'REST'}</Text>
          </View>
        </View>

        {/* Stats */}
        <View style={styles.statsRow}>
          {[
            { label: 'Total', value: summary.total || 0, color: COLORS.text.primary },
            { label: 'Active', value: summary.active || 0, color: COLORS.green.primary },
            { label: 'Working', value: summary.processing || 0, color: COLORS.accent.blue },
            { label: 'Idle', value: summary.idle || 0, color: COLORS.text.muted },
          ].map((s, i) => (
            <GlassCard key={i} style={styles.statCard}>
              <Text style={[styles.statValue, { color: s.color }]}>{s.value}</Text>
              <Text style={styles.statLabel}>{s.label}</Text>
            </GlassCard>
          ))}
        </View>

        {/* Architecture */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Architecture</Text>
          <GlassCard>
            <View style={styles.archRow}>
              {(['scout', 'analyst', 'news_hound', 'strategist'] as const).map((type, i) => (
                <View key={type} style={styles.archNode}>
                  <View style={[styles.archIcon, { backgroundColor: `${CLR[type]}14` }]}>
                    <Ionicons name={ICON[type] as any} size={20} color={CLR[type]} />
                  </View>
                  <Text style={styles.archLabel}>
                    {type === 'news_hound' ? 'News' : type.charAt(0).toUpperCase() + type.slice(1)}
                  </Text>
                  {i < 3 && <Ionicons name="chevron-forward" size={12} color={COLORS.text.muted} style={styles.archArrow} />}
                </View>
              ))}
            </View>
          </GlassCard>
        </View>

        {/* RAG */}
        {rag.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>RAG Context</Text>
            <View style={styles.ragRow}>
              {rag.map((s: string) => (
                <View key={s} style={styles.ragChip}>
                  <Text style={styles.ragChipText}>{s}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Event Stream */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Event Stream</Text>
            <Text style={styles.sectionCount}>{events.length}</Text>
          </View>
          {events.length === 0 ? (
            <GlassCard variant="subtle">
              <Text style={styles.emptyText}>Waiting for swarm events...</Text>
            </GlassCard>
          ) : (
            <GlassCard>
              {events.slice(-10).reverse().map((evt: any, i: number) => {
                const c = EVT_CLR[evt.event_type] || COLORS.text.muted;
                return (
                  <View key={i} style={[styles.evtRow, i > 0 && styles.evtBorder]}>
                    <View style={[styles.evtDot, { backgroundColor: `${c}20` }]}>
                      <View style={[styles.evtDotInner, { backgroundColor: c }]} />
                    </View>
                    <View style={styles.evtContent}>
                      <Text style={styles.evtType}>
                        {evt.event_type?.replace(/_/g, ' ')}{evt.symbol ? ` · ${evt.symbol}` : ''}
                      </Text>
                      <Text style={styles.evtMeta}>
                        {evt.source_agent}{evt.target_agent ? ` → ${evt.target_agent}` : ''}
                      </Text>
                    </View>
                    <Text style={styles.evtTime}>
                      {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
                    </Text>
                  </View>
                );
              })}
            </GlassCard>
          )}
        </View>

        {/* Agent Cards */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Active Agents</Text>
          {agents.map((agent: any, i: number) => {
            const tc = CLR[agent.type] || COLORS.text.secondary;
            const sc = STATUS_CLR[agent.status] || COLORS.text.muted;
            return (
              <GlassCard key={i} style={styles.agentCard}>
                <View style={styles.agentTop}>
                  <View style={styles.agentLeft}>
                    <View style={[styles.agentIcon, { backgroundColor: `${tc}14` }]}>
                      <Ionicons name={(ICON[agent.type] || 'cube-outline') as any} size={18} color={tc} />
                    </View>
                    <View>
                      <Text style={styles.agentName}>{agent.name}</Text>
                      <Text style={[styles.agentType, { color: tc }]}>{agent.type?.replace(/_/g, ' ')}</Text>
                    </View>
                  </View>
                  <View style={[styles.statusPill, { backgroundColor: `${sc}18` }]}>
                    <View style={[styles.statusDot, { backgroundColor: sc }]} />
                    <Text style={[styles.statusLabel, { color: sc }]}>{agent.status}</Text>
                  </View>
                </View>

                {agent.current_task && (
                  <View style={styles.taskRow}>
                    <Text style={styles.taskText}>{agent.current_task}</Text>
                  </View>
                )}

                <View style={styles.agentMeta}>
                  <View>
                    <Text style={styles.metaValue}>{agent.tasks_completed || 0}</Text>
                    <Text style={styles.metaLabel}>Cycles</Text>
                  </View>
                  <View>
                    <Text style={styles.metaValue}>
                      {agent.last_active ? new Date(agent.last_active).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
                    </Text>
                    <Text style={styles.metaLabel}>Last Active</Text>
                  </View>
                </View>
              </GlassCard>
            );
          })}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg.primary },
  scroll: { flex: 1 },
  content: { paddingHorizontal: SPACING.lg, paddingTop: SPACING.sm },

  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACING.xl },
  title: { fontSize: FONT_SIZES.xxxl, fontWeight: '800', color: COLORS.text.primary, letterSpacing: -0.5 },
  livePill: { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(255,71,87,0.10)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: RADIUS.full, gap: 5 },
  livePillOn: { backgroundColor: COLORS.green.soft },
  liveDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: COLORS.red.primary },
  liveDotOn: { backgroundColor: COLORS.green.primary },
  liveText: { fontSize: 9, fontWeight: '800', color: COLORS.red.text, letterSpacing: 1 },
  liveTextOn: { color: COLORS.green.text },

  statsRow: { flexDirection: 'row', gap: SPACING.sm, marginBottom: SPACING.xl },
  statCard: { flex: 1, alignItems: 'center' },
  statValue: { fontSize: FONT_SIZES.xxl, fontWeight: '800', letterSpacing: -0.5 },
  statLabel: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 3 },

  section: { marginBottom: SPACING.xl },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: SPACING.md },
  sectionTitle: { fontSize: FONT_SIZES.lg, fontWeight: '700', color: COLORS.text.primary, marginBottom: SPACING.md },
  sectionCount: { fontSize: FONT_SIZES.sm, color: COLORS.text.muted },

  archRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  archNode: { alignItems: 'center', position: 'relative' },
  archIcon: { width: 48, height: 48, borderRadius: 24, justifyContent: 'center', alignItems: 'center', marginBottom: SPACING.sm },
  archLabel: { fontSize: FONT_SIZES.xs, color: COLORS.text.secondary, fontWeight: '600' },
  archArrow: { position: 'absolute', right: -18, top: 17 },

  ragRow: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACING.sm },
  ragChip: { backgroundColor: COLORS.accent.blueSoft, paddingHorizontal: SPACING.md, paddingVertical: 5, borderRadius: RADIUS.full },
  ragChipText: { fontSize: FONT_SIZES.xs, color: COLORS.accent.blue, fontWeight: '700' },

  evtRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: SPACING.sm + 2 },
  evtBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: COLORS.glass.border },
  evtDot: { width: 24, height: 24, borderRadius: 12, justifyContent: 'center', alignItems: 'center', marginRight: SPACING.md },
  evtDotInner: { width: 8, height: 8, borderRadius: 4 },
  evtContent: { flex: 1 },
  evtType: { fontSize: FONT_SIZES.sm, color: COLORS.text.primary, fontWeight: '500', textTransform: 'capitalize' },
  evtMeta: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 1 },
  evtTime: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted },

  agentCard: { marginBottom: SPACING.sm },
  agentTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  agentLeft: { flexDirection: 'row', alignItems: 'center', gap: SPACING.md },
  agentIcon: { width: 40, height: 40, borderRadius: 20, justifyContent: 'center', alignItems: 'center' },
  agentName: { fontSize: FONT_SIZES.base, fontWeight: '700', color: COLORS.text.primary },
  agentType: { fontSize: FONT_SIZES.xs, fontWeight: '500', marginTop: 1, textTransform: 'uppercase' },
  statusPill: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 4, borderRadius: RADIUS.full, gap: 5 },
  statusDot: { width: 5, height: 5, borderRadius: 3 },
  statusLabel: { fontSize: FONT_SIZES.xs, fontWeight: '700', textTransform: 'uppercase' },
  taskRow: { marginTop: SPACING.md, backgroundColor: COLORS.bg.tertiary, padding: SPACING.md, borderRadius: RADIUS.md },
  taskText: { fontSize: FONT_SIZES.sm, color: COLORS.text.secondary },
  agentMeta: { flexDirection: 'row', gap: SPACING.xxl, marginTop: SPACING.md },
  metaValue: { fontSize: FONT_SIZES.base, fontWeight: '700', color: COLORS.text.primary },
  metaLabel: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 2 },

  emptyText: { color: COLORS.text.muted, fontSize: FONT_SIZES.sm, textAlign: 'center' },
});
