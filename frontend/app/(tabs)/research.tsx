import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity,
  TextInput, KeyboardAvoidingView, Platform, Keyboard, ActivityIndicator,
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

const SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'JPM', 'V', 'UNH', 'SPY', 'QQQ'];

export default function ResearchScreen() {
  const { colors } = useTheme();
  const router = useRouter();
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [symbol, setSymbol] = useState('');
  const [latestResult, setLatestResult] = useState<any>(null);

  const fetchReports = useCallback(async () => {
    try {
      const result = await api.getReports();
      setReports(result.reports || []);
    } catch (e) {
      console.error('Reports fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchReports(); }, [fetchReports]);
  const onRefresh = () => { setRefreshing(true); fetchReports(); };

  const runAnalysis = async () => {
    const sym = symbol.toUpperCase().trim();
    if (!sym) return;
    Keyboard.dismiss();
    setAnalyzing(true);
    setLatestResult(null);
    try {
      const result = await api.analyzeStock(sym);
      setLatestResult(result);
      fetchReports();
    } catch (e: any) {
      setLatestResult({ error: e.message || 'Analysis failed' });
    } finally {
      setAnalyzing(false);
    }
  };

  const s = useMemo(() => createStyles(colors), [colors]);

  if (loading) return <LoadingScreen message="Loading reports..." />;

  const sentColor = (sent: string) =>
    sent === 'bullish' || sent === 'very_bullish' ? colors.green.text :
    sent === 'bearish' || sent === 'very_bearish' ? colors.red.text :
    colors.accent.amber;

  const report = latestResult?.report;
  const signal = latestResult?.signal;
  const rec = report?.swarm_recommendation;

  return (
    <SafeAreaView style={s.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView
          style={s.scroll}
          contentContainerStyle={s.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.green.primary} />}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={s.title}>Research</Text>

          {/* Input */}
          <GlassCard style={s.inputCard}>
            <View style={s.inputRow}>
              <TextInput
                style={s.input}
                placeholder="Symbol (e.g. AAPL)"
                placeholderTextColor={colors.text.muted}
                value={symbol}
                onChangeText={setSymbol}
                autoCapitalize="characters"
                returnKeyType="go"
                onSubmitEditing={runAnalysis}
              />
              <TouchableOpacity
                style={[s.analyzeBtn, analyzing && s.analyzeBtnOff]}
                onPress={runAnalysis}
                disabled={analyzing}
              >
                {analyzing ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <Ionicons name="arrow-forward" size={18} color="#FFF" />
                )}
              </TouchableOpacity>
            </View>
            <View style={s.chips}>
              {SYMBOLS.slice(0, 6).map(sym => (
                <TouchableOpacity
                  key={sym}
                  style={[s.chip, symbol.toUpperCase() === sym && { backgroundColor: colors.green.primary, borderColor: colors.green.primary }]}
                  onPress={() => setSymbol(sym)}
                >
                  <Text style={[s.chipText, symbol.toUpperCase() === sym && { color: '#FFF' }]}>{sym}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </GlassCard>

          {analyzing && (
            <GlassCard variant="elevated" style={s.analyzingCard}>
              <View style={s.analyzingRow}>
                <ActivityIndicator size="small" color={colors.green.primary} />
                <View>
                  <Text style={[s.analyzingTitle, { color: colors.green.primary }]}>
                    Swarm analyzing {symbol.toUpperCase()}...
                  </Text>
                  <Text style={s.analyzingMeta}>Scout → Analyst → NewsHound → Strategist</Text>
                </View>
              </View>
            </GlassCard>
          )}

          {report && !latestResult.error && (
            <TouchableOpacity onPress={() => router.push(`/stock/${report.symbol}` as any)} activeOpacity={0.7}>
              <GlassCard variant="elevated" style={s.resultCard}>
                <View style={s.resultTop}>
                  <View>
                    <Text style={s.resultSymbol}>{report.symbol}</Text>
                    <Text style={[s.resultSentiment, { color: sentColor(report.sentiment) }]}>
                      {report.sentiment?.toUpperCase()}
                    </Text>
                  </View>
                  {signal && <SignalBadge action={signal.action} confidence={signal.confidence} />}
                </View>
                <Text style={s.resultSummary}>{report.summary}</Text>
                {rec && (
                  <View style={s.recGrid}>
                    {[
                      { label: 'Target', value: `$${rec.price_target?.toFixed?.(2) || '—'}`, color: colors.accent.blue },
                      { label: 'Stop Loss', value: `$${rec.stop_loss?.toFixed?.(2) || '—'}`, color: colors.red.text },
                      { label: 'R/R', value: `${rec.risk_reward_ratio?.toFixed?.(1) || '—'}x` },
                      { label: 'Horizon', value: rec.time_horizon || '—' },
                    ].map((item, i) => (
                      <View key={i} style={s.recItem}>
                        <Text style={s.recLabel}>{item.label}</Text>
                        <Text style={[s.recValue, item.color ? { color: item.color } : undefined]}>{item.value}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </GlassCard>
            </TouchableOpacity>
          )}

          {latestResult?.error && (
            <GlassCard><Text style={s.errorText}>{latestResult.error}</Text></GlassCard>
          )}

          {/* Past Reports */}
          <View style={s.sectionHeader}>
            <Text style={s.sectionTitle}>Reports</Text>
            <Text style={s.sectionCount}>{reports.length}</Text>
          </View>
          {reports.length === 0 ? (
            <GlassCard variant="subtle">
              <Text style={s.emptyText}>No reports yet</Text>
            </GlassCard>
          ) : (
            reports.slice(0, 10).map((r: any, i: number) => (
              <TouchableOpacity
                key={r.id || i}
                onPress={() => router.push(`/stock/${r.symbol}` as any)}
                activeOpacity={0.7}
              >
                <GlassCard style={s.reportCard}>
                  <View style={s.reportTop}>
                    <Text style={s.reportSymbol}>{r.symbol}</Text>
                    <View style={[s.sentPill, { backgroundColor: `${sentColor(r.sentiment)}18` }]}>
                      <Text style={[s.sentPillText, { color: sentColor(r.sentiment) }]}>
                        {r.sentiment?.toUpperCase()}
                      </Text>
                    </View>
                  </View>
                  <Text style={s.reportSummary} numberOfLines={2}>{r.summary}</Text>
                  <View style={s.reportFooter}>
                    <Text style={s.reportRec}>{r.recommendation}</Text>
                    <Text style={s.reportTime}>
                      {(r.created_at || r.timestamp) ? new Date(r.created_at || r.timestamp).toLocaleDateString() : ''}
                    </Text>
                  </View>
                </GlassCard>
              </TouchableOpacity>
            ))
          )}
          <View style={{ height: 40 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const createStyles = (t: ThemeColors) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: t.bg.primary },
  scroll: { flex: 1 },
  content: { paddingHorizontal: SPACING.lg, paddingTop: SPACING.sm },
  title: { fontSize: FONT_SIZES.xxxl, fontWeight: '800', color: t.text.primary, letterSpacing: -0.5, marginBottom: SPACING.xl },

  inputCard: { marginBottom: SPACING.lg },
  inputRow: { flexDirection: 'row', gap: SPACING.sm },
  input: { flex: 1, backgroundColor: t.bg.tertiary, borderRadius: RADIUS.md, paddingHorizontal: SPACING.lg, paddingVertical: SPACING.md, color: t.text.primary, fontSize: FONT_SIZES.base, borderWidth: 0.5, borderColor: t.border },
  analyzeBtn: { width: 48, height: 48, borderRadius: RADIUS.md, backgroundColor: t.green.primary, justifyContent: 'center', alignItems: 'center' },
  analyzeBtnOff: { opacity: 0.5 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACING.sm, marginTop: SPACING.md },
  chip: { paddingHorizontal: SPACING.md, paddingVertical: 6, borderRadius: RADIUS.full, backgroundColor: t.bg.tertiary, borderWidth: 0.5, borderColor: t.border },
  chipText: { fontSize: FONT_SIZES.xs, color: t.text.secondary, fontWeight: '600' },

  analyzingCard: { marginBottom: SPACING.lg },
  analyzingRow: { flexDirection: 'row', alignItems: 'center', gap: SPACING.md },
  analyzingTitle: { fontSize: FONT_SIZES.sm, fontWeight: '600' },
  analyzingMeta: { fontSize: FONT_SIZES.xs, color: t.text.muted, marginTop: 2 },

  resultCard: { marginBottom: SPACING.md },
  resultTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACING.md },
  resultSymbol: { fontSize: FONT_SIZES.xxl, fontWeight: '800', color: t.text.primary },
  resultSentiment: { fontSize: FONT_SIZES.sm, fontWeight: '700', marginTop: 2 },
  resultSummary: { fontSize: FONT_SIZES.sm, color: t.text.secondary, lineHeight: 22, marginBottom: SPACING.lg },
  recGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACING.sm },
  recItem: { width: '47%' as any, backgroundColor: t.bg.tertiary, padding: SPACING.md, borderRadius: RADIUS.md },
  recLabel: { fontSize: FONT_SIZES.xs, color: t.text.muted, marginBottom: 3 },
  recValue: { fontSize: FONT_SIZES.lg, fontWeight: '700', color: t.text.primary },

  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: SPACING.md, marginTop: SPACING.lg },
  sectionTitle: { fontSize: FONT_SIZES.lg, fontWeight: '700', color: t.text.primary },
  sectionCount: { fontSize: FONT_SIZES.sm, color: t.text.muted },

  reportCard: { marginBottom: SPACING.sm },
  reportTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACING.sm },
  reportSymbol: { fontSize: FONT_SIZES.xl, fontWeight: '800', color: t.text.primary },
  sentPill: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: RADIUS.full },
  sentPillText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  reportSummary: { fontSize: FONT_SIZES.sm, color: t.text.secondary, lineHeight: 20 },
  reportFooter: { flexDirection: 'row', justifyContent: 'space-between', marginTop: SPACING.sm },
  reportRec: { fontSize: FONT_SIZES.xs, color: t.green.primary, fontWeight: '700' },
  reportTime: { fontSize: FONT_SIZES.xs, color: t.text.muted },

  errorText: { color: t.red.text, fontSize: FONT_SIZES.sm, textAlign: 'center' },
  emptyText: { color: t.text.muted, fontSize: FONT_SIZES.sm, textAlign: 'center' },
});
