import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, FONT_SIZES, RADIUS } from '../../src/theme';
import { api } from '../../src/api';
import GlassCard from '../../src/components/GlassCard';
import SignalBadge from '../../src/components/SignalBadge';
import LoadingScreen from '../../src/components/LoadingScreen';

export default function SignalsScreen() {
  const [signals, setSignals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<string>('ALL');

  const fetchSignals = useCallback(async () => {
    try {
      const result = await api.getTradeSignals();
      setSignals(result.signals || []);
    } catch (e) {
      console.error('Signals fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchSignals(); }, [fetchSignals]);
  const onRefresh = () => { setRefreshing(true); fetchSignals(); };

  if (loading) return <LoadingScreen message="Loading signals..." />;

  const filtered = filter === 'ALL' ? signals : signals.filter(s => s.action === filter);
  const filters = ['ALL', 'BUY', 'SELL', 'HOLD'];

  const filterColors: Record<string, string> = {
    ALL: COLORS.accent.blue,
    BUY: COLORS.green.primary,
    SELL: COLORS.red.primary,
    HOLD: COLORS.accent.amber,
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.headerWrap}>
        <Text style={styles.title}>Signals</Text>
        <Text style={styles.count}>{signals.length} total</Text>
      </View>

      <View style={styles.filters}>
        {filters.map(f => {
          const active = filter === f;
          return (
            <TouchableOpacity
              key={f}
              testID={`filter-${f.toLowerCase()}-btn`}
              style={[styles.filterBtn, active && { backgroundColor: filterColors[f] }]}
              onPress={() => setFilter(f)}
            >
              <Text style={[styles.filterText, active && styles.filterTextActive]}>{f}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.accent.blue} />}
        showsVerticalScrollIndicator={false}
      >
        {filtered.length === 0 ? (
          <GlassCard variant="subtle">
            <View style={styles.emptyWrap}>
              <Ionicons name="flash-off-outline" size={36} color={COLORS.text.muted} />
              <Text style={styles.emptyText}>No {filter !== 'ALL' ? filter : ''} signals</Text>
              <Text style={styles.emptySubtext}>Analyze stocks on the Research tab</Text>
            </View>
          </GlassCard>
        ) : (
          filtered.map((sig: any, i: number) => {
            const targetDiff = sig.price_target && sig.current_price
              ? ((sig.price_target - sig.current_price) / sig.current_price * 100).toFixed(1)
              : null;
            const isUpside = Number(targetDiff) >= 0;

            return (
              <GlassCard key={sig.id || i} style={styles.signalCard}>
                <View style={styles.signalTop}>
                  <View>
                    <Text style={styles.signalSymbol}>{sig.symbol}</Text>
                    <Text style={styles.signalAgent}>{sig.agent_type || 'swarm'}</Text>
                  </View>
                  <SignalBadge action={sig.action} confidence={sig.confidence} />
                </View>

                <View style={styles.priceRow}>
                  <View style={styles.priceCol}>
                    <Text style={styles.priceLabel}>Current</Text>
                    <Text style={styles.priceValue}>${sig.current_price?.toFixed(2)}</Text>
                  </View>
                  <View style={styles.priceCol}>
                    <Text style={styles.priceLabel}>Target</Text>
                    <Text style={[styles.priceValue, { color: COLORS.accent.blue }]}>
                      ${sig.price_target?.toFixed(2)}
                    </Text>
                  </View>
                  {targetDiff && (
                    <View style={styles.priceCol}>
                      <Text style={styles.priceLabel}>Upside</Text>
                      <Text style={[styles.priceValue, { color: isUpside ? COLORS.green.text : COLORS.red.text }]}>
                        {isUpside ? '+' : ''}{targetDiff}%
                      </Text>
                    </View>
                  )}
                </View>

                <Text style={styles.reasoning} numberOfLines={2}>{sig.reasoning}</Text>

                <View style={styles.footer}>
                  <Text style={styles.timestamp}>
                    {sig.timestamp ? new Date(sig.timestamp).toLocaleString() : ''}
                  </Text>
                  <View style={styles.confBar}>
                    <View style={[styles.confFill, { width: `${sig.confidence * 100}%` }]} />
                  </View>
                </View>
              </GlassCard>
            );
          })
        )}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg.primary },
  headerWrap: { paddingHorizontal: SPACING.lg, paddingTop: SPACING.sm, paddingBottom: SPACING.md },
  title: { fontSize: FONT_SIZES.xxxl, fontWeight: '800', color: COLORS.text.primary, letterSpacing: -0.5 },
  count: { fontSize: FONT_SIZES.sm, color: COLORS.text.muted, marginTop: 2 },
  filters: { flexDirection: 'row', paddingHorizontal: SPACING.lg, gap: SPACING.sm, marginBottom: SPACING.lg },
  filterBtn: { paddingHorizontal: SPACING.lg, paddingVertical: SPACING.sm + 2, borderRadius: RADIUS.full, backgroundColor: COLORS.glass.fill, borderWidth: StyleSheet.hairlineWidth, borderColor: COLORS.glass.border },
  filterTextActive: { color: '#000' },
  filterText: { fontSize: FONT_SIZES.sm, color: COLORS.text.secondary, fontWeight: '600' },
  scroll: { flex: 1 },
  content: { paddingHorizontal: SPACING.lg },
  signalCard: { marginBottom: SPACING.md },
  signalTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACING.md },
  signalSymbol: { fontSize: FONT_SIZES.xxl, fontWeight: '800', color: COLORS.text.primary },
  signalAgent: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 2 },
  priceRow: { flexDirection: 'row', gap: SPACING.xl, marginBottom: SPACING.md },
  priceCol: { gap: 3 },
  priceLabel: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted },
  priceValue: { fontSize: FONT_SIZES.base, fontWeight: '700', color: COLORS.text.primary },
  reasoning: { fontSize: FONT_SIZES.sm, color: COLORS.text.secondary, lineHeight: 20, marginBottom: SPACING.md },
  footer: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  timestamp: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted },
  confBar: { width: 80, height: 3, backgroundColor: COLORS.glass.fill, borderRadius: 2, overflow: 'hidden' },
  confFill: { height: '100%', backgroundColor: COLORS.accent.blue, borderRadius: 2 },
  emptyWrap: { alignItems: 'center', paddingVertical: SPACING.xxl, gap: SPACING.md },
  emptyText: { fontSize: FONT_SIZES.base, color: COLORS.text.secondary, fontWeight: '600' },
  emptySubtext: { fontSize: FONT_SIZES.sm, color: COLORS.text.muted },
});
