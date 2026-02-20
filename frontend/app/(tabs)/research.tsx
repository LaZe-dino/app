import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity,
  TextInput, KeyboardAvoidingView, Platform, Keyboard, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, FONT_SIZES, RADIUS } from '../../src/theme';
import { api } from '../../src/api';
import GlassCard from '../../src/components/GlassCard';
import SignalBadge from '../../src/components/SignalBadge';
import LoadingScreen from '../../src/components/LoadingScreen';

const SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'JPM', 'V', 'UNH', 'SPY', 'QQQ'];

export default function ResearchScreen() {
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

  if (loading) return <LoadingScreen message="Loading reports..." />;

  const sentColor = (s: string) =>
    s === 'bullish' || s === 'very_bullish' ? COLORS.green.text :
    s === 'bearish' || s === 'very_bearish' ? COLORS.red.text :
    COLORS.accent.amber;

  const report = latestResult?.report;
  const signal = latestResult?.signal;
  const tech = report?.technical_data;
  const sent = report?.sentiment_data;
  const rec = report?.swarm_recommendation;

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.accent.blue} />}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={styles.title}>Research</Text>

          {/* Input */}
          <GlassCard style={styles.inputCard}>
            <View style={styles.inputRow}>
              <TextInput
                testID="stock-symbol-input"
                style={styles.input}
                placeholder="Symbol (e.g. AAPL)"
                placeholderTextColor={COLORS.text.muted}
                value={symbol}
                onChangeText={setSymbol}
                autoCapitalize="characters"
                returnKeyType="go"
                onSubmitEditing={runAnalysis}
              />
              <TouchableOpacity
                testID="analyze-btn"
                style={[styles.analyzeBtn, analyzing && styles.analyzeBtnOff]}
                onPress={runAnalysis}
                disabled={analyzing}
              >
                {analyzing ? (
                  <ActivityIndicator size="small" color="#000" />
                ) : (
                  <Ionicons name="arrow-forward" size={18} color="#000" />
                )}
              </TouchableOpacity>
            </View>
            <View style={styles.chips}>
              {SYMBOLS.slice(0, 6).map(sym => (
                <TouchableOpacity
                  key={sym}
                  testID={`quick-symbol-${sym}`}
                  style={[styles.chip, symbol.toUpperCase() === sym && styles.chipActive]}
                  onPress={() => setSymbol(sym)}
                >
                  <Text style={[styles.chipText, symbol.toUpperCase() === sym && styles.chipTextActive]}>{sym}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </GlassCard>

          {/* Analyzing */}
          {analyzing && (
            <GlassCard variant="elevated" style={styles.analyzingCard}>
              <View style={styles.analyzingRow}>
                <ActivityIndicator size="small" color={COLORS.accent.blue} />
                <View>
                  <Text style={styles.analyzingTitle}>Swarm analyzing {symbol.toUpperCase()}...</Text>
                  <Text style={styles.analyzingMeta}>Scout → Analyst → NewsHound → Strategist</Text>
                </View>
              </View>
            </GlassCard>
          )}

          {/* Result */}
          {report && !latestResult.error && (
            <>
              <GlassCard variant="elevated" style={styles.resultCard}>
                <View style={styles.resultTop}>
                  <View>
                    <Text style={styles.resultSymbol}>{report.symbol}</Text>
                    <Text style={[styles.resultSentiment, { color: sentColor(report.sentiment) }]}>
                      {report.sentiment?.toUpperCase()}
                    </Text>
                  </View>
                  {signal && <SignalBadge action={signal.action} confidence={signal.confidence} />}
                </View>
                <Text style={styles.resultSummary}>{report.summary}</Text>

                {rec && (
                  <View style={styles.recGrid}>
                    {[
                      { label: 'Target', value: `$${rec.price_target?.toFixed?.(2) || '—'}`, color: COLORS.accent.blue },
                      { label: 'Stop Loss', value: `$${rec.stop_loss?.toFixed?.(2) || '—'}`, color: COLORS.red.text },
                      { label: 'R/R', value: `${rec.risk_reward_ratio?.toFixed?.(1) || '—'}x`, color: COLORS.text.primary },
                      { label: 'Horizon', value: rec.time_horizon || '—', color: COLORS.text.primary },
                    ].map((item, i) => (
                      <View key={i} style={styles.recItem}>
                        <Text style={styles.recLabel}>{item.label}</Text>
                        <Text style={[styles.recValue, { color: item.color }]}>{item.value}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </GlassCard>

              {/* Technical */}
              {tech && (
                <GlassCard style={styles.dataCard}>
                  <Text style={styles.dataTitle}>Technical Analysis</Text>
                  <View style={styles.dataGrid}>
                    {[
                      { k: 'RSI', v: tech.rsi, c: (tech.rsi ?? 50) > 70 ? COLORS.red.text : (tech.rsi ?? 50) < 30 ? COLORS.green.text : COLORS.text.primary },
                      { k: 'SMA 20', v: `$${tech.sma_20 ?? '—'}` },
                      { k: 'SMA 50', v: `$${tech.sma_50 ?? '—'}` },
                      { k: 'MACD', v: tech.macd?.histogram?.toFixed?.(4) ?? '—' },
                      { k: 'Boll ↑', v: `$${tech.bollinger?.upper ?? '—'}` },
                      { k: 'Boll ↓', v: `$${tech.bollinger?.lower ?? '—'}` },
                    ].map((d, i) => (
                      <View key={i} style={styles.dataCell}>
                        <Text style={styles.dataCellLabel}>{d.k}</Text>
                        <Text style={[styles.dataCellValue, d.c ? { color: d.c } : null]}>{d.v}</Text>
                      </View>
                    ))}
                  </View>
                  {tech.signals && (
                    <View style={styles.sigList}>
                      {tech.signals.map((s: any, i: number) => (
                        <View key={i} style={styles.sigRow}>
                          <Text style={styles.sigIndicator}>{s.indicator}</Text>
                          <Text style={[styles.sigValue, {
                            color: ['BULLISH', 'OVERSOLD', 'GOLDEN_CROSS', 'BELOW_LOWER'].includes(s.signal) ?
                              COLORS.green.text : ['BEARISH', 'OVERBOUGHT', 'DEATH_CROSS', 'ABOVE_UPPER'].includes(s.signal) ?
                              COLORS.red.text : COLORS.text.secondary
                          }]}>{s.signal}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                </GlassCard>
              )}

              {/* Sentiment */}
              {sent && (
                <GlassCard style={styles.dataCard}>
                  <Text style={styles.dataTitle}>News Sentiment</Text>
                  <View style={styles.sentRow}>
                    <Text style={[styles.sentScore, { color: sentColor(sent.sentiment_label) }]}>
                      {sent.sentiment_score > 0 ? '+' : ''}{sent.sentiment_score?.toFixed?.(3)}
                    </Text>
                    <View style={[styles.sentPill, { backgroundColor: `${sentColor(sent.sentiment_label)}18` }]}>
                      <Text style={[styles.sentPillText, { color: sentColor(sent.sentiment_label) }]}>
                        {sent.sentiment_label?.toUpperCase()}
                      </Text>
                    </View>
                    <Text style={styles.sentCount}>{sent.articles_analyzed} articles</Text>
                  </View>
                  {sent.top_headlines?.map((h: string, i: number) => (
                    <View key={i} style={styles.headlineRow}>
                      <View style={styles.headlineBullet} />
                      <Text style={styles.headlineText} numberOfLines={2}>{h}</Text>
                    </View>
                  ))}
                </GlassCard>
              )}

              {/* Factors & Risks */}
              {report.key_findings?.length > 0 && (
                <GlassCard style={styles.dataCard}>
                  <Text style={styles.dataTitle}>Key Factors</Text>
                  {report.key_findings.map((f: string, i: number) => (
                    <View key={i} style={styles.factorRow}>
                      <Ionicons name="checkmark-circle" size={14} color={COLORS.green.primary} />
                      <Text style={styles.factorText}>{f}</Text>
                    </View>
                  ))}
                </GlassCard>
              )}
            </>
          )}

          {latestResult?.error && (
            <GlassCard><Text style={styles.errorText}>{latestResult.error}</Text></GlassCard>
          )}

          {/* Past Reports */}
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Reports</Text>
            <Text style={styles.sectionCount}>{reports.length}</Text>
          </View>
          {reports.length === 0 ? (
            <GlassCard variant="subtle">
              <Text style={styles.emptyText}>No reports yet</Text>
            </GlassCard>
          ) : (
            reports.slice(0, 10).map((r: any, i: number) => (
              <GlassCard key={r.id || i} style={styles.reportCard}>
                <View style={styles.reportTop}>
                  <Text style={styles.reportSymbol}>{r.symbol}</Text>
                  <View style={[styles.sentPill, { backgroundColor: `${sentColor(r.sentiment)}18` }]}>
                    <Text style={[styles.sentPillText, { color: sentColor(r.sentiment) }]}>
                      {r.sentiment?.toUpperCase()}
                    </Text>
                  </View>
                </View>
                <Text style={styles.reportSummary} numberOfLines={2}>{r.summary}</Text>
                <View style={styles.reportFooter}>
                  <Text style={styles.reportRec}>{r.recommendation}</Text>
                  <Text style={styles.reportTime}>
                    {r.timestamp ? new Date(r.timestamp).toLocaleDateString() : ''}
                  </Text>
                </View>
              </GlassCard>
            ))
          )}
          <View style={{ height: 40 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg.primary },
  scroll: { flex: 1 },
  content: { paddingHorizontal: SPACING.lg, paddingTop: SPACING.sm },
  title: { fontSize: FONT_SIZES.xxxl, fontWeight: '800', color: COLORS.text.primary, letterSpacing: -0.5, marginBottom: SPACING.xl },

  inputCard: { marginBottom: SPACING.lg },
  inputRow: { flexDirection: 'row', gap: SPACING.sm },
  input: { flex: 1, backgroundColor: COLORS.bg.tertiary, borderRadius: RADIUS.md, paddingHorizontal: SPACING.lg, paddingVertical: SPACING.md, color: COLORS.text.primary, fontSize: FONT_SIZES.base, borderWidth: StyleSheet.hairlineWidth, borderColor: COLORS.glass.border },
  analyzeBtn: { width: 48, height: 48, borderRadius: RADIUS.md, backgroundColor: COLORS.accent.blue, justifyContent: 'center', alignItems: 'center' },
  analyzeBtnOff: { opacity: 0.5 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACING.sm, marginTop: SPACING.md },
  chip: { paddingHorizontal: SPACING.md, paddingVertical: 6, borderRadius: RADIUS.full, backgroundColor: COLORS.bg.tertiary, borderWidth: StyleSheet.hairlineWidth, borderColor: COLORS.glass.border },
  chipActive: { backgroundColor: COLORS.accent.blue, borderColor: COLORS.accent.blue },
  chipText: { fontSize: FONT_SIZES.xs, color: COLORS.text.secondary, fontWeight: '600' },
  chipTextActive: { color: '#000' },

  analyzingCard: { marginBottom: SPACING.lg },
  analyzingRow: { flexDirection: 'row', alignItems: 'center', gap: SPACING.md },
  analyzingTitle: { fontSize: FONT_SIZES.sm, fontWeight: '600', color: COLORS.accent.blue },
  analyzingMeta: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginTop: 2 },

  resultCard: { marginBottom: SPACING.md },
  resultTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACING.md },
  resultSymbol: { fontSize: FONT_SIZES.xxl, fontWeight: '800', color: COLORS.text.primary },
  resultSentiment: { fontSize: FONT_SIZES.sm, fontWeight: '700', marginTop: 2 },
  resultSummary: { fontSize: FONT_SIZES.sm, color: COLORS.text.secondary, lineHeight: 22, marginBottom: SPACING.lg },
  recGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACING.sm },
  recItem: { width: '47%' as any, backgroundColor: COLORS.bg.tertiary, padding: SPACING.md, borderRadius: RADIUS.md },
  recLabel: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginBottom: 3 },
  recValue: { fontSize: FONT_SIZES.lg, fontWeight: '700' },

  dataCard: { marginBottom: SPACING.md },
  dataTitle: { fontSize: FONT_SIZES.base, fontWeight: '700', color: COLORS.text.primary, marginBottom: SPACING.md },
  dataGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: SPACING.sm },
  dataCell: { width: '30%' as any, backgroundColor: COLORS.bg.tertiary, padding: SPACING.sm + 2, borderRadius: RADIUS.sm },
  dataCellLabel: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted, marginBottom: 2 },
  dataCellValue: { fontSize: FONT_SIZES.sm, fontWeight: '700', color: COLORS.text.primary },
  sigList: { marginTop: SPACING.md },
  sigRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: COLORS.glass.border },
  sigIndicator: { fontSize: FONT_SIZES.sm, color: COLORS.text.secondary, fontWeight: '500' },
  sigValue: { fontSize: FONT_SIZES.sm, fontWeight: '700' },

  sentRow: { flexDirection: 'row', alignItems: 'center', gap: SPACING.md, marginBottom: SPACING.md },
  sentScore: { fontSize: FONT_SIZES.xxl, fontWeight: '800' },
  sentPill: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: RADIUS.full },
  sentPillText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  sentCount: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted },
  headlineRow: { flexDirection: 'row', alignItems: 'flex-start', gap: SPACING.sm, marginBottom: SPACING.sm },
  headlineBullet: { width: 4, height: 4, borderRadius: 2, backgroundColor: COLORS.text.muted, marginTop: 7 },
  headlineText: { flex: 1, fontSize: FONT_SIZES.sm, color: COLORS.text.secondary, lineHeight: 20 },

  factorRow: { flexDirection: 'row', alignItems: 'flex-start', gap: SPACING.sm, marginBottom: SPACING.sm },
  factorText: { flex: 1, fontSize: FONT_SIZES.sm, color: COLORS.text.secondary, lineHeight: 20 },

  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: SPACING.md, marginTop: SPACING.lg },
  sectionTitle: { fontSize: FONT_SIZES.lg, fontWeight: '700', color: COLORS.text.primary },
  sectionCount: { fontSize: FONT_SIZES.sm, color: COLORS.text.muted },

  reportCard: { marginBottom: SPACING.sm },
  reportTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: SPACING.sm },
  reportSymbol: { fontSize: FONT_SIZES.xl, fontWeight: '800', color: COLORS.text.primary },
  reportSummary: { fontSize: FONT_SIZES.sm, color: COLORS.text.secondary, lineHeight: 20 },
  reportFooter: { flexDirection: 'row', justifyContent: 'space-between', marginTop: SPACING.sm },
  reportRec: { fontSize: FONT_SIZES.xs, color: COLORS.accent.blue, fontWeight: '700' },
  reportTime: { fontSize: FONT_SIZES.xs, color: COLORS.text.muted },

  errorText: { color: COLORS.red.text, fontSize: FONT_SIZES.sm, textAlign: 'center' },
  emptyText: { color: COLORS.text.muted, fontSize: FONT_SIZES.sm, textAlign: 'center' },
});
