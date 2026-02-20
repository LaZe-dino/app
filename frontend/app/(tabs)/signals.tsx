import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useTheme } from '../../src/contexts/ThemeContext';
import { ThemeColors, SPACING, FONT_SIZES, RADIUS } from '../../src/theme';
import { api } from '../../src/api';
import GlassCard from '../../src/components/GlassCard';
import SignalBadge from '../../src/components/SignalBadge';
import LoadingScreen from '../../src/components/LoadingScreen';

export default function SignalsScreen() {
  const { colors } = useTheme();
  const router = useRouter();
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

  const s = useMemo(() => createStyles(colors), [colors]);

  if (loading) return <LoadingScreen message="Loading signals..." />;

  const filtered = filter === 'ALL' ? signals : signals.filter(sig => sig.action === filter);
  const filters = ['ALL', 'BUY', 'SELL', 'HOLD'];
  const filterColors: Record<string, string> = {
    ALL: colors.accent.blue, BUY: colors.green.primary, SELL: colors.red.primary, HOLD: colors.accent.amber,
  };

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.headerWrap}>
        <Text style={s.title}>Signals</Text>
        <Text style={s.count}>{signals.length} total</Text>
      </View>

      <View style={s.filters}>
        {filters.map(f => {
          const active = filter === f;
          return (
            <TouchableOpacity
              key={f}
              style={[s.filterBtn, active && { backgroundColor: filterColors[f] }]}
              onPress={() => setFilter(f)}
            >
              <Text style={[s.filterText, active && s.filterTextActive]}>{f}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.green.primary} />}
        showsVerticalScrollIndicator={false}
      >
        {filtered.length === 0 ? (
          <GlassCard variant="subtle">
            <View style={s.emptyWrap}>
              <Ionicons name="flash-off-outline" size={36} color={colors.text.muted} />
              <Text style={s.emptyText}>No {filter !== 'ALL' ? filter : ''} signals</Text>
            </View>
          </GlassCard>
        ) : (
          filtered.map((sig: any, i: number) => {
            const targetDiff = sig.price_target && sig.current_price
              ? ((sig.price_target - sig.current_price) / sig.current_price * 100).toFixed(1) : null;
            const isUpside = Number(targetDiff) >= 0;

            return (
              <TouchableOpacity
                key={sig.id || i}
                onPress={() => router.push(`/stock/${sig.symbol}` as any)}
                activeOpacity={0.7}
              >
                <GlassCard style={s.signalCard}>
                  <View style={s.signalTop}>
                    <View>
                      <Text style={s.signalSymbol}>{sig.symbol}</Text>
                      <Text style={s.signalAgent}>{sig.agent_type || 'swarm'}</Text>
                    </View>
                    <SignalBadge action={sig.action} confidence={sig.confidence} />
                  </View>
                  <View style={s.priceRow}>
                    <View style={s.priceCol}>
                      <Text style={s.priceLabel}>Current</Text>
                      <Text style={s.priceValue}>${sig.current_price?.toFixed(2)}</Text>
                    </View>
                    <View style={s.priceCol}>
                      <Text style={s.priceLabel}>Target</Text>
                      <Text style={[s.priceValue, { color: colors.accent.blue }]}>
                        ${sig.price_target?.toFixed(2)}
                      </Text>
                    </View>
                    {targetDiff && (
                      <View style={s.priceCol}>
                        <Text style={s.priceLabel}>Upside</Text>
                        <Text style={[s.priceValue, { color: isUpside ? colors.green.text : colors.red.text }]}>
                          {isUpside ? '+' : ''}{targetDiff}%
                        </Text>
                      </View>
                    )}
                  </View>
                  <Text style={s.reasoning} numberOfLines={2}>{sig.reasoning}</Text>
                </GlassCard>
              </TouchableOpacity>
            );
          })
        )}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const createStyles = (t: ThemeColors) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: t.bg.primary },
  headerWrap: { paddingHorizontal: SPACING.lg, paddingTop: SPACING.sm, paddingBottom: SPACING.md },
  title: { fontSize: FONT_SIZES.xxxl, fontWeight: '800', color: t.text.primary, letterSpacing: -0.5 },
  count: { fontSize: FONT_SIZES.sm, color: t.text.muted, marginTop: 2 },
  filters: { flexDirection: 'row', paddingHorizontal: SPACING.lg, gap: SPACING.sm, marginBottom: SPACING.lg },
  filterBtn: { paddingHorizontal: SPACING.lg, paddingVertical: SPACING.sm + 2, borderRadius: RADIUS.full, backgroundColor: t.glass.fill, borderWidth: 0.5, borderColor: t.border },
  filterTextActive: { color: '#FFFFFF' },
  filterText: { fontSize: FONT_SIZES.sm, color: t.text.secondary, fontWeight: '600' },
  scroll: { flex: 1 },
  content: { paddingHorizontal: SPACING.lg },
  signalCard: { marginBottom: SPACING.md },
  signalTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACING.md },
  signalSymbol: { fontSize: FONT_SIZES.xxl, fontWeight: '800', color: t.text.primary },
  signalAgent: { fontSize: FONT_SIZES.xs, color: t.text.muted, marginTop: 2 },
  priceRow: { flexDirection: 'row', gap: SPACING.xl, marginBottom: SPACING.md },
  priceCol: { gap: 3 },
  priceLabel: { fontSize: FONT_SIZES.xs, color: t.text.muted },
  priceValue: { fontSize: FONT_SIZES.base, fontWeight: '700', color: t.text.primary },
  reasoning: { fontSize: FONT_SIZES.sm, color: t.text.secondary, lineHeight: 20 },
  emptyWrap: { alignItems: 'center', paddingVertical: SPACING.xxl, gap: SPACING.md },
  emptyText: { fontSize: FONT_SIZES.base, color: t.text.secondary, fontWeight: '600' },
});
