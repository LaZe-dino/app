import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, ScrollView, RefreshControl,
  TouchableOpacity, useWindowDimensions, ActivityIndicator, TextInput,
  Alert, Linking, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../../src/contexts/ThemeContext';
import { SPACING, FONT_SIZES, RADIUS } from '../../src/theme';
import { api, hftWS } from '../../src/api';
import FluidChart from '../../src/components/FluidChart';

export default function HFTScreen() {
  const { width: screenW } = useWindowDimensions();
  const { colors, isDark } = useTheme();
  const [dashboard, setDashboard] = useState<any>(null);
  const [botStatus, setBotStatus] = useState<any>(null);
  const [botPnl, setBotPnl] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [depositAmt, setDepositAmt] = useState('');
  const [tradeBudget, setTradeBudget] = useState('');
  const [tab, setTab] = useState<'engine' | 'bot' | 'wallet'>('engine');
  const [brokerStatus, setBrokerStatus] = useState<any>(null);
  const [brokerKey, setBrokerKey] = useState('');
  const [brokerSecret, setBrokerSecret] = useState('');
  const [brokerPaper, setBrokerPaper] = useState(true);
  const [brokerUseBrokerApi, setBrokerUseBrokerApi] = useState(false);
  const [brokerConnecting, setBrokerConnecting] = useState(false);
  const [oauthOpening, setOauthOpening] = useState(false);
  const [oauthEnv, setOauthEnv] = useState<'paper' | 'live'>('paper');
  const pollRef = useRef<any>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [dash, bot, pnl, broker] = await Promise.all([
        api.getHFTDashboard().catch(() => null),
        api.getBotStatus().catch(() => null),
        api.getBotPnl().catch(() => null),
        api.getBrokerStatus().catch(() => null),
      ]);
      if (dash) setDashboard(dash);
      if (bot) setBotStatus(bot);
      if (pnl) setBotPnl(pnl);
      if (broker) setBrokerStatus(broker);
    } catch (e) {
      console.error('HFT fetch:', e);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    pollRef.current = setInterval(fetchAll, 3000);
    return () => clearInterval(pollRef.current);
  }, [fetchAll]);

  useEffect(() => {
    const unsub = hftWS.subscribe((msg: any) => {
      if (msg.type === 'hft_dashboard' || msg.system_health) setDashboard(msg);
    });
    return unsub;
  }, []);

  const toggleBot = async (budget?: number) => {
    try {
      if (botStatus?.running) {
        const r = await api.stopBot();
        setBotStatus(r);
      } else {
        const r = await api.startBot(budget);
        setBotStatus((prev: any) => ({ ...prev, ...r, running: true }));
      }
      setTimeout(fetchAll, 500);
    } catch (e: any) { Alert.alert('Error', e.message); }
  };

  const doDeposit = async () => {
    const amt = parseFloat(depositAmt);
    if (!amt || amt <= 0) return;
    try {
      await api.depositToWallet(amt);
      setDepositAmt('');
      fetchAll();
    } catch (e: any) { Alert.alert('Error', e.message); }
  };

  const doWithdraw = async () => {
    const amt = parseFloat(depositAmt);
    if (!amt || amt <= 0) return;
    try {
      await api.withdrawFromWallet(amt);
      setDepositAmt('');
      fetchAll();
    } catch (e: any) { Alert.alert('Error', e.message); }
  };

  const health = dashboard?.system_health || {};
  const ttt = dashboard?.tick_to_trade || {};
  const strategies = dashboard?.strategies || {};
  const mm = strategies.market_making || {};
  const arb = strategies.arbitrage || {};
  const mmTable = dashboard?.market_making_table || [];
  const risk = dashboard?.risk || {};
  const fpga = dashboard?.fpga || {};
  const latency = dashboard?.latency_breakdown || {};
  const wallet = botStatus?.wallet || botPnl?.wallet || {};

  // Build P&L chart from the pnl endpoint; fall back to building from recent_trades
  const pnlHistory = (() => {
    const apiHistory = botPnl?.history || [];
    if (apiHistory.length > 0) {
      return apiHistory.map((p: any) => ({
        time: new Date(p.timestamp * 1000).toISOString(),
        value: p.pnl,
      }));
    }
    // Fallback: reconstruct from recent trades so chart always matches the P&L number
    const trades = botStatus?.recent_trades || [];
    let running = 0;
    return trades.map((t: any) => {
      running += t.net_profit || 0;
      return { time: new Date(t.timestamp * 1000).toISOString(), value: running };
    });
  })();

  // The single source of truth for the P&L number: use the chart's final value
  const totalPnl = pnlHistory.length > 0 ? pnlHistory[pnlHistory.length - 1].value : (wallet.total_pnl || 0);

  const chartWidth = screenW - SPACING.lg * 2 - SPACING.md * 2;
  const isHalted = health.status === 'HALTED';
  const botRunning = botStatus?.running || false;

  const bg = colors.bg.primary;
  const card = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)';
  const border = colors.border;
  const green = colors.green.primary;
  const red = colors.red.primary;
  const accent = isDark ? '#6C63FF' : '#5B52E6';
  const accentSoft = isDark ? 'rgba(108,99,255,0.12)' : 'rgba(91,82,230,0.08)';
  const textP = colors.text.primary;
  const textS = colors.text.secondary;
  const textM = colors.text.muted;

  const Pill = ({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) => (
    <TouchableOpacity
      onPress={onPress}
      style={[s.pill, { backgroundColor: active ? accent : card, borderColor: active ? accent : border }]}
    >
      <Text style={[s.pillText, { color: active ? '#FFF' : textS }]}>{label}</Text>
    </TouchableOpacity>
  );

  const isCompact = screenW < 380;
  const Stat = ({ label, value, color: c }: { label: string; value: string | number; color?: string }) => (
    <View style={s.stat}>
      <Text style={[s.statLabel, { color: textM, fontSize: isCompact ? 7 : 9 }]}>{label}</Text>
      <Text style={[s.statValue, { color: c || textP, fontSize: isCompact ? 12 : 15 }]} numberOfLines={1} adjustsFontSizeToFit>{value}</Text>
    </View>
  );

  return (
    <SafeAreaView style={[s.safe, { backgroundColor: bg }]}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchAll(); }} tintColor={accent} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={s.header}>
          <View>
            <Text style={[s.title, { color: textP, fontSize: isCompact ? 22 : 28 }]}>Trading Engine</Text>
            <Text style={[s.subtitle, { color: textM }]}>NY5 Co-Location  ·  Sub-µs Pipeline</Text>
          </View>
          <View style={[s.statusBadge, { backgroundColor: isHalted ? 'rgba(239,68,68,0.12)' : 'rgba(34,197,94,0.12)' }]}>
            <View style={[s.statusDot, { backgroundColor: isHalted ? red : green }]} />
            <Text style={[s.statusText, { color: isHalted ? red : green }]}>{isHalted ? 'HALTED' : 'LIVE'}</Text>
          </View>
        </View>

        {/* Tab Bar */}
        <View style={s.tabs}>
          <Pill label="Engine" active={tab === 'engine'} onPress={() => setTab('engine')} />
          <Pill label="Arb Bot" active={tab === 'bot'} onPress={() => setTab('bot')} />
          <Pill label="Wallet" active={tab === 'wallet'} onPress={() => setTab('wallet')} />
        </View>

        {tab === 'engine' && (
          <>
            {/* Tick-to-Trade */}
            <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
              <Text style={[s.cardLabel, { color: accent }]}>TICK-TO-TRADE</Text>
              <View style={s.tttRow}>
                <View style={s.tttMain}>
                  <Text style={[s.tttValue, { color: accent, fontSize: isCompact ? 26 : 36 }]}>{ttt.p50_us || '—'}</Text>
                  <Text style={[s.tttUnit, { color: textM }]}>µs p50</Text>
                </View>
                <View style={[s.tttDivider, { backgroundColor: border }]} />
                <Stat label="p95" value={`${ttt.p95_us || '—'}µs`} color={accent} />
                <Stat label="p99" value={`${ttt.p99_us || '—'}µs`} color={accent} />
                <Stat label="p99.9" value={`${ttt.p999_us || '—'}µs`} color={accent} />
              </View>
            </View>

            {/* Throughput Metrics */}
            <View style={s.metricsRow}>
              {[
                { label: 'Events/s', value: Math.round(health.events_per_second || 0), c: green },
                { label: 'Orders/s', value: Math.round(health.orders_per_second || 0), c: accent },
                { label: 'Fills', value: (dashboard?.positions?.summary?.fills_processed || 0).toLocaleString(), c: '#F59E0B' },
              ].map((m) => (
                <View key={m.label} style={[s.metricCard, { backgroundColor: card, borderColor: border }]}>
                  <Text style={[s.metricLabel, { color: textM }]}>{m.label}</Text>
                  <Text style={[s.metricValue, { color: m.c }]}>{m.value}</Text>
                </View>
              ))}
            </View>

            {/* FPGA */}
            <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
              <View style={s.fpgaRow}>
                <View style={[s.fpgaIcon, { backgroundColor: accentSoft }]}>
                  <Ionicons name="hardware-chip" size={20} color={accent} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[s.fpgaTitle, { color: textP }]}>FPGA 250MHz 8-Stage</Text>
                  <Text style={[s.fpgaSub, { color: textM }]}>
                    {(fpga.ticks_processed || 0).toLocaleString()} ticks  ·  {fpga.signals_generated || 0} signals  ·  {fpga.avg_pipeline_ns || 0}ns
                  </Text>
                </View>
              </View>
              {fpga.pipeline_stages && (
                <View style={s.pipelineRow}>
                  {(fpga.pipeline_stages || []).map((st: any, i: number) => (
                    <View key={i} style={s.pipelineStage}>
                      <View style={[s.pipelineBar, { height: Math.max(6, st.target_ns * 3), backgroundColor: accent }]} />
                      <Text style={[s.pipelineLabel, { color: textM }]}>{st.name?.replace('_', '\n')}</Text>
                    </View>
                  ))}
                </View>
              )}
            </View>

            {/* Strategy Cards */}
            <View style={s.stratRow}>
              <View style={[s.stratCard, { backgroundColor: card, borderColor: border }]}>
                <View style={s.stratHead}>
                  <Ionicons name="swap-horizontal" size={16} color={accent} />
                  <Text style={[s.stratName, { color: textS }]}>Market Making</Text>
                </View>
                <Text style={[s.stratPnl, { color: (mm.total_pnl || 0) >= 0 ? green : red, fontSize: isCompact ? 16 : 22 }]}>
                  ${(mm.total_pnl || 0).toFixed(2)}
                </Text>
                <Text style={[s.stratMeta, { color: textM }]}>{mm.total_trades || 0} trades  ·  {mm.active_quotes || 0} quotes</Text>
              </View>
              <View style={[s.stratCard, { backgroundColor: card, borderColor: border }]}>
                <View style={s.stratHead}>
                  <Ionicons name="git-compare" size={16} color="#F59E0B" />
                  <Text style={[s.stratName, { color: textS }]}>Latency Arb</Text>
                </View>
                <Text style={[s.stratPnl, { color: green, fontSize: isCompact ? 16 : 22 }]}>${(arb.theoretical_profit || 0).toFixed(2)}</Text>
                <Text style={[s.stratMeta, { color: textM }]}>{arb.opportunities || 0} opps  ·  {arb.hit_rate || 0}%</Text>
              </View>
            </View>

            {/* Market Making Book */}
            {mmTable.length > 0 && (
              <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
                <Text style={[s.cardTitle, { color: textP }]}>Market Making Book</Text>
                <View style={[s.tableHead, { borderBottomColor: border }]}>
                  <Text style={[s.th, { flex: 1.2, color: accent }]}>Stock</Text>
                  <Text style={[s.th, { flex: 1, color: accent }]}>Bid</Text>
                  <Text style={[s.th, { flex: 1, color: accent }]}>Ask</Text>
                  <Text style={[s.th, { flex: 0.6, color: accent }]}>Sprd</Text>
                  <Text style={[s.th, { flex: 0.6, color: accent }]}>Trds</Text>
                  <Text style={[s.th, { flex: 1, color: accent }]}>P&L</Text>
                </View>
                {mmTable.slice(0, 12).map((r: any, i: number) => (
                  <View key={i} style={[s.row, i % 2 === 0 && { backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)' }]}>
                    <Text style={[s.td, { flex: 1.2, color: textP, fontWeight: '700' }]}>{r.stock}</Text>
                    <Text style={[s.td, { flex: 1, color: green }]}>${r.buy_price?.toFixed(2)}</Text>
                    <Text style={[s.td, { flex: 1, color: red }]}>${r.sell_price?.toFixed(2)}</Text>
                    <Text style={[s.td, { flex: 0.6, color: textS }]}>${r.spread?.toFixed(2)}</Text>
                    <Text style={[s.td, { flex: 0.6, color: textS }]}>{r.trades_executed || 0}</Text>
                    <Text style={[s.td, { flex: 1, color: (r.profit || 0) >= 0 ? green : red, fontWeight: '700' }]}>
                      ${(r.profit || 0).toFixed(2)}
                    </Text>
                  </View>
                ))}
              </View>
            )}

            {/* Risk Engine */}
            <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
              <Text style={[s.cardTitle, { color: textP }]}>Risk Engine</Text>
              <View style={s.riskGrid}>
                <Stat label="Checks" value={(risk.checks_run || 0).toLocaleString()} />
                <Stat label="Pass Rate" value={`${risk.pass_rate || 0}%`} color={Number(risk.pass_rate) > 95 ? green : '#F59E0B'} />
                <Stat label="Latency" value={`${risk.avg_check_latency_us || 0}µs`} color={accent} />
                <Stat label="Daily P&L" value={`$${(risk.daily_pnl || 0).toFixed(0)}`} color={(risk.daily_pnl || 0) >= 0 ? green : red} />
              </View>
              {risk.circuit_breaker && (
                <View style={[s.cbBanner, { borderTopColor: border }]}>
                  <Ionicons name="warning" size={14} color={red} />
                  <Text style={[s.cbText, { color: red }]}>CIRCUIT BREAKER ACTIVE</Text>
                </View>
              )}
            </View>

            {/* Latency */}
            <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
              <Text style={[s.cardTitle, { color: textP }]}>Latency Breakdown</Text>
              {Object.entries(latency).map(([stage, data]: [string, any], i: number) => {
                const avg = data?.avg_us || 0;
                const pct = Math.min(avg / 50 * 100, 100);
                return (
                  <View key={stage} style={[s.latRow, i > 0 && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: border }]}>
                    <Text style={[s.latName, { color: textS }]}>{stage.replace(/_/g, ' ')}</Text>
                    <View style={[s.latBarBg, { backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }]}>
                      <View style={[s.latBar, { width: `${pct}%`, backgroundColor: accent }]} />
                    </View>
                    <Text style={[s.latVal, { color: accent }]}>{avg}µs</Text>
                  </View>
                );
              })}
            </View>
          </>
        )}

        {tab === 'bot' && (
          <>
            {/* Bot Hero */}
            <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
              <View style={s.botHeader}>
                <View style={[s.botIcon, { backgroundColor: botRunning ? 'rgba(34,197,94,0.12)' : accentSoft }]}>
                  <Ionicons name="flash" size={28} color={botRunning ? green : accent} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[s.botTitle, { color: textP }]}>HFT Arbitrage Bot</Text>
                  <Text style={[s.botSub, { color: textM }]}>
                    {botStatus?.bot_id || 'Not initialized'}  ·  {botRunning ? (brokerStatus?.connected ? 'Live with Alpaca' : '3 Strategies (sim)') : 'Stopped'}
                  </Text>
                  {botRunning && botStatus?.uptime_seconds > 0 && (
                    <Text style={[s.botUptime, { color: textM }]}>
                      Uptime: {Math.floor(botStatus.uptime_seconds / 60)}m {Math.round(botStatus.uptime_seconds % 60)}s  ·  Scan: 8ms
                      {brokerStatus?.connected && '  ·  Real orders'}
                    </Text>
                  )}
                </View>
                {botRunning && (
                  <TouchableOpacity
                    onPress={() => toggleBot()}
                    style={[s.botBtn, { backgroundColor: 'rgba(239,68,68,0.12)' }]}
                  >
                    <Ionicons name="stop" size={20} color={red} />
                    <Text style={[s.botBtnText, { color: red }]}>Stop</Text>
                  </TouchableOpacity>
                )}
              </View>

              {/* Broker + Bot: one flow — when Alpaca is connected, the same button runs the bot with real orders */}
              {!botRunning && (
                <View style={{ marginTop: SPACING.md }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                    {brokerStatus?.connected ? (
                      <>
                        <Ionicons name="checkmark-circle" size={18} color={green} />
                        <Text style={{ fontSize: 12, fontWeight: '600', color: green }}>
                          Alpaca connected — bot will send real limit orders
                        </Text>
                      </>
                    ) : (
                      <>
                        <Ionicons name="information-circle-outline" size={18} color={textM} />
                        <Text style={{ fontSize: 12, fontWeight: '500', color: textM }}>
                          Connect Alpaca in the Wallet tab to trade live; otherwise bot runs in simulation only
                        </Text>
                      </>
                    )}
                  </View>
                  <Text style={{ fontSize: 11, fontWeight: '600', color: textM, marginBottom: 8, letterSpacing: 0.3 }}>TRADING BUDGET</Text>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                    <View style={{ flex: 1 }}>
                      <TextInput
                        style={[s.budgetInput, { backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)', color: textP, borderColor: border }]}
                        placeholder="Custom amount ($)"
                        placeholderTextColor={textM}
                        keyboardType="numeric"
                        value={tradeBudget}
                        onChangeText={setTradeBudget}
                      />
                    </View>
                  </View>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                    {[1000, 5000, 10000, 25000, 50000, 100000].map((amt) => {
                      const selected = tradeBudget === String(amt);
                      return (
                        <TouchableOpacity
                          key={amt}
                          onPress={() => setTradeBudget(String(amt))}
                          style={[s.budgetChip, {
                            backgroundColor: selected ? accent : (isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)'),
                            borderColor: selected ? accent : border,
                          }]}
                        >
                          <Text style={{ fontSize: 12, fontWeight: '700', color: selected ? '#FFF' : textS }}>
                            ${amt >= 1000 ? `${amt / 1000}K` : amt}
                          </Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                  <TouchableOpacity
                    onPress={() => {
                      const budget = parseFloat(tradeBudget) || 10000;
                      toggleBot(budget);
                    }}
                    style={[s.hireBtn, {
                      backgroundColor: brokerStatus?.connected ? 'rgba(34,197,94,0.18)' : 'rgba(34,197,94,0.12)',
                      borderWidth: brokerStatus?.connected ? 1 : 0,
                      borderColor: brokerStatus?.connected ? green : 'transparent',
                    }]}
                  >
                    <Ionicons name="play" size={18} color={green} />
                    <Text style={{ fontSize: 15, fontWeight: '800', color: green }}>
                      {brokerStatus?.connected
                        ? `Run bot with Alpaca — $${(parseFloat(tradeBudget) || 10000).toLocaleString()} budget`
                        : `Start bot — $${(parseFloat(tradeBudget) || 10000).toLocaleString()} budget (sim only)`}
                    </Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>

            {/* P&L Chart */}
            {pnlHistory.length > 2 && (
              <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <Text style={[s.cardTitle, { color: textP, marginBottom: 0 }]}>Bot P&L Curve</Text>
                  <Text style={{ fontSize: 15, fontWeight: '800', color: totalPnl >= 0 ? green : red, fontVariant: ['tabular-nums'] as any }}>
                    {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
                  </Text>
                </View>
                <View style={{ height: 6 }} />
                <FluidChart
                  data={pnlHistory}
                  height={180}
                  width={chartWidth}
                  showLabels={true}
                  showGrid={true}
                  showCrosshair={true}
                  showPriceHeader={false}
                  padding={{ top: 16, right: 12, bottom: 28, left: 54 }}
                />
              </View>
            )}

            {/* Bot Stats */}
            <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
              <Text style={[s.cardTitle, { color: textP }]}>Performance</Text>
              <View style={[s.riskGrid, { marginBottom: SPACING.sm }]}>
                <Stat label="Trading budget" value={`$${(wallet.initial_balance ?? wallet.balance ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} color={accent} />
                <Stat label="Balance" value={`$${(wallet.balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} color={Number(wallet.balance) <= Number(wallet.initial_balance) ? textP : green} />
                <Stat label="Total P&L" value={`$${totalPnl.toFixed(2)}`} color={totalPnl >= 0 ? green : red} />
                <Stat label="Win Rate" value={`${wallet.win_rate || 0}%`} color={(wallet.win_rate || 0) > 50 ? green : red} />
              </View>
              <View style={s.riskGrid}>
                <Stat label="Trades" value={wallet.total_trades || 0} />
                <Stat label="Wins" value={wallet.winning_trades || 0} color={green} />
                <Stat label="Losses" value={wallet.losing_trades || 0} color={red} />
                <Stat label="Opps" value={`${botStatus?.opportunities_executed || 0}/${botStatus?.opportunities_seen || 0}`} />
              </View>
            </View>

            {/* Strategy Breakdown */}
            {botStatus?.strategies && (
              <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
                <Text style={[s.cardTitle, { color: textP }]}>Strategy Performance</Text>
                {Object.entries(botStatus.strategies as Record<string, any>).map(([key, st]: [string, any], idx: number) => {
                  const stratColor = key === 'LATENCY_ARB' ? accent : key === 'STAT_ARB' ? '#F59E0B' : '#10B981';
                  const stratIcon = key === 'LATENCY_ARB' ? 'git-compare' : key === 'STAT_ARB' ? 'stats-chart' : 'trending-up';
                  return (
                    <View key={key} style={[
                      { paddingVertical: 12 },
                      idx > 0 && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: border },
                    ]}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 8 }}>
                        <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: stratColor + '18', justifyContent: 'center', alignItems: 'center', marginRight: 8 }}>
                          <Ionicons name={stratIcon as any} size={14} color={stratColor} />
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontSize: 13, fontWeight: '700', color: textP }}>{st.name}</Text>
                          <Text style={{ fontSize: 9, color: textM, marginTop: 1 }}>
                            {st.opps_seen} opps  ·  {st.trades} trades  ·  θ{(st.adaptive_threshold || 1).toFixed(2)}
                          </Text>
                        </View>
                        <View style={{ alignItems: 'flex-end' }}>
                          <Text style={{ fontSize: 15, fontWeight: '800', color: (st.total_pnl || 0) >= 0 ? green : red, fontVariant: ['tabular-nums'] as any }}>
                            {(st.total_pnl || 0) >= 0 ? '+' : ''}${(st.total_pnl || 0).toFixed(2)}
                          </Text>
                          <Text style={{ fontSize: 10, color: (st.win_rate || 0) >= 50 ? green : red, fontWeight: '600', marginTop: 1 }}>
                            {st.win_rate || 0}% WR
                          </Text>
                        </View>
                      </View>
                      <View style={{ flexDirection: 'row', gap: 6 }}>
                        {st.trades > 0 && (
                          <View style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)', overflow: 'hidden' }}>
                            <View style={{ width: `${Math.min(st.win_rate || 0, 100)}%`, height: '100%', borderRadius: 2, backgroundColor: stratColor }} />
                          </View>
                        )}
                      </View>
                    </View>
                  );
                })}
              </View>
            )}

            {/* Adaptive Learning Stats */}
            {botStatus?.learning?.symbols_tracked > 0 && (
              <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: SPACING.md }}>
                  <Ionicons name="bulb" size={16} color="#F59E0B" />
                  <Text style={[s.cardTitle, { marginBottom: 0, color: textP }]}>Adaptive Learning</Text>
                </View>
                <Text style={{ fontSize: 10, color: textM, marginBottom: SPACING.sm }}>
                  Tracking {botStatus.learning.symbols_tracked} symbols  ·  dp/dt · d²p/dt² · ∫mom·dt · gradient descent
                </Text>
                {Object.entries(botStatus.learning.trackers || {}).slice(0, 6).map(([sym, t]: [string, any], i: number) => (
                  <View key={sym} style={[
                    { paddingVertical: 7 },
                    i > 0 && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: border },
                  ]}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 3 }}>
                      <Text style={{ width: 52, fontSize: 11, fontWeight: '700', color: textP }}>{sym}</Text>
                      <View style={{ flex: 1, flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
                        <Text style={{ fontSize: 9, color: textM }}>σ {t.volatility?.toFixed(3)}</Text>
                        <Text style={{ fontSize: 9, color: (t.velocity || 0) >= 0 ? green : red }}>
                          dp/dt {(t.velocity || 0) >= 0 ? '+' : ''}{t.velocity?.toFixed(3)}
                        </Text>
                        <Text style={{ fontSize: 9, color: (t.acceleration || 0) >= 0 ? '#10B981' : '#F59E0B' }}>
                          d²p {(t.acceleration || 0) >= 0 ? '+' : ''}{t.acceleration?.toFixed(3)}
                        </Text>
                      </View>
                      <Text style={{ fontSize: 9, color: accent, fontWeight: '600' }}>
                        S:{(t.signal_strength || 0).toFixed(2)}
                      </Text>
                    </View>
                    <View style={{ flexDirection: 'row', gap: 8, paddingLeft: 52 }}>
                      <Text style={{ fontSize: 8, color: (t.integrated_momentum || 0) >= 0 ? green : red }}>
                        ∫mom {(t.integrated_momentum || 0) >= 0 ? '+' : ''}{(t.integrated_momentum || 0).toFixed(3)}
                      </Text>
                      <Text style={{ fontSize: 8, color: Math.abs(t.mean_rev_z || 0) > 1.5 ? '#F59E0B' : textM }}>
                        z {t.mean_rev_z?.toFixed(1)}
                      </Text>
                      <Text style={{ fontSize: 8, color: textM }}>{t.samples} ticks</Text>
                    </View>
                  </View>
                ))}
              </View>
            )}

            {/* Recent Trades */}
            {(botStatus?.recent_trades || []).length > 0 && (
              <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: SPACING.md }}>
                  <Text style={[s.cardTitle, { marginBottom: 0, color: textP }]}>Recent Trades</Text>
                  <Text style={{ fontSize: 11, color: textM }}>{(botStatus.recent_trades || []).length} trades</Text>
                </View>

                {/* Trades Total Summary */}
                {(() => {
                  const trades = botStatus.recent_trades || [];
                  const totalPnl = trades.reduce((sm: number, t: any) => sm + (t.net_profit || 0), 0);
                  const totalCost = trades.reduce((sm: number, t: any) => sm + (t.cost || t.buy_price * t.quantity || 0), 0);
                  const totalRevenue = trades.reduce((sm: number, t: any) => sm + (t.revenue || t.sell_price * t.quantity || 0), 0);
                  return (
                    <View style={[s.tradeSummary, { backgroundColor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)', borderColor: border }]}>
                      <View style={s.tradeSummaryRow}>
                        <Text style={[s.tradeSummaryLabel, { color: textM }]}>Total Cost</Text>
                        <Text style={[s.tradeSummaryValue, { color: textS }]}>${totalCost.toFixed(2)}</Text>
                      </View>
                      <View style={s.tradeSummaryRow}>
                        <Text style={[s.tradeSummaryLabel, { color: textM }]}>Total Revenue</Text>
                        <Text style={[s.tradeSummaryValue, { color: textS }]}>${totalRevenue.toFixed(2)}</Text>
                      </View>
                      <View style={[s.tradeSummaryRow, { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: border, paddingTop: 8, marginTop: 4 }]}>
                        <Text style={[s.tradeSummaryLabel, { color: textP, fontWeight: '700', fontSize: 12 }]}>P&L</Text>
                        <Text style={[s.tradeSummaryValue, { color: totalPnl >= 0 ? green : red, fontWeight: '800', fontSize: 15 }]}>
                          {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
                        </Text>
                      </View>
                    </View>
                  );
                })()}

                {/* Individual Trades */}
                {(botStatus.recent_trades || []).slice(-12).reverse().map((t: any, i: number) => {
                  const cost = t.cost || (t.buy_price * t.quantity);
                  const revenue = t.revenue || (t.sell_price * t.quantity);
                  const stratColor = t.strategy === 'LATENCY_ARB' ? accent : t.strategy === 'STAT_ARB' ? '#F59E0B' : '#10B981';
                  const stratLabel = t.strategy === 'LATENCY_ARB' ? 'ARB' : t.strategy === 'STAT_ARB' ? 'STAT' : 'MOM';
                  return (
                    <View key={t.id || i} style={[s.tradeRow, i > 0 && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: border }]}>
                      <View style={{ flex: 1 }}>
                        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                          <Text style={[s.tradeSymbol, { color: textP }]}>{t.symbol}</Text>
                          <View style={[s.tradeQtyBadge, { backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)' }]}>
                            <Text style={{ fontSize: 9, fontWeight: '700', color: textM }}>{t.quantity} shr</Text>
                          </View>
                          <View style={{ paddingHorizontal: 5, paddingVertical: 1, borderRadius: 3, backgroundColor: stratColor + '20' }}>
                            <Text style={{ fontSize: 8, fontWeight: '800', color: stratColor, letterSpacing: 0.5 }}>{stratLabel}</Text>
                          </View>
                          {t.status === 'stopped_out' && (
                            <View style={{ paddingHorizontal: 5, paddingVertical: 1, borderRadius: 3, backgroundColor: 'rgba(239,68,68,0.12)' }}>
                              <Text style={{ fontSize: 8, fontWeight: '800', color: red, letterSpacing: 0.5 }}>STOP</Text>
                            </View>
                          )}
                        </View>
                        <Text style={[s.tradeVenues, { color: textM }]}>
                          {t.buy_venue} → {t.sell_venue}
                        </Text>
                        <View style={s.tradeDetailRow}>
                          <Text style={{ fontSize: 10, color: green }}>Buy ${t.buy_price?.toFixed(2)}</Text>
                          <Text style={{ fontSize: 10, color: textM }}> · </Text>
                          <Text style={{ fontSize: 10, color: red }}>Sell ${t.sell_price?.toFixed(2)}</Text>
                        </View>
                      </View>
                      <View style={{ alignItems: 'flex-end', minWidth: 80 }}>
                        <Text style={[s.tradePnl, { color: t.net_profit >= 0 ? green : red }]}>
                          {t.net_profit >= 0 ? '+' : ''}${t.net_profit?.toFixed(2)}
                        </Text>
                        <Text style={{ fontSize: 9, color: textM, marginTop: 2 }}>
                          ${cost.toFixed(2)} → ${revenue.toFixed(2)}
                        </Text>
                        <Text style={[s.tradeTime, { color: textM }]}>
                          {new Date(t.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </Text>
                      </View>
                    </View>
                  );
                })}
              </View>
            )}
          </>
        )}

        {tab === 'wallet' && (
          <>
            {/* Wallet Hero */}
            <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
              <View style={s.walletHeader}>
                <View style={[s.walletIcon, { backgroundColor: accentSoft }]}>
                  <Ionicons name="wallet" size={32} color={accent} />
                </View>
                <View>
                  <Text style={[s.walletLabel, { color: textM }]}>Trading Balance</Text>
                  <Text style={[s.walletBalance, { color: textP, fontSize: isCompact ? 24 : 32 }]} adjustsFontSizeToFit numberOfLines={1}>
                    ${(wallet.balance ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </Text>
                  {Number(wallet.initial_balance) > 0 && (
                    <Text style={{ fontSize: 11, color: textM, marginTop: 2 }}>
                      Max to trade: ${Number(wallet.initial_balance).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </Text>
                  )}
                </View>
              </View>
            </View>

            {/* Wallet Stats */}
            <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
              <View style={s.riskGrid}>
                <Stat label="Trading budget" value={`$${(wallet.initial_balance ?? wallet.total_deposited ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} color={accent} />
                <Stat label="Deposited" value={`$${(wallet.total_deposited ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} color={green} />
                <Stat label="Withdrawn" value={`$${(wallet.total_withdrawn ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} color={red} />
                <Stat label="Profit" value={`$${(wallet.total_profit ?? 0).toFixed(2)}`} color={(wallet.total_profit ?? 0) >= 0 ? green : red} />
              </View>
              <View style={[s.riskGrid, { marginTop: SPACING.sm }]}>
                <Stat label="Return" value={`${(wallet.total_return_pct ?? 0).toFixed(2)}%`} color={(wallet.total_return_pct ?? 0) >= 0 ? green : red} />
              </View>
            </View>

            {/* Deposit / Withdraw */}
            <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
              <Text style={[s.cardTitle, { color: textP }]}>Fund Management</Text>
              <View style={s.inputRow}>
                <TextInput
                  style={[s.input, { backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)', color: textP, borderColor: border }]}
                  placeholder="Amount ($)"
                  placeholderTextColor={textM}
                  keyboardType="numeric"
                  value={depositAmt}
                  onChangeText={setDepositAmt}
                />
              </View>
              <View style={s.btnRow}>
                <TouchableOpacity style={[s.actionBtn, { backgroundColor: 'rgba(34,197,94,0.12)' }]} onPress={doDeposit}>
                  <Ionicons name="arrow-down" size={16} color={green} />
                  <Text style={[s.actionBtnText, { color: green }]}>Deposit</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[s.actionBtn, { backgroundColor: 'rgba(239,68,68,0.12)' }]} onPress={doWithdraw}>
                  <Ionicons name="arrow-up" size={16} color={red} />
                  <Text style={[s.actionBtnText, { color: red }]}>Withdraw</Text>
                </TouchableOpacity>
              </View>
            </View>

            {/* Quick Deposits */}
            <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
              <Text style={[s.cardTitle, { color: textP }]}>Quick Deposit</Text>
              <View style={s.quickRow}>
                {[1000, 5000, 10000, 25000, 50000].map((amt) => (
                  <TouchableOpacity
                    key={amt}
                    style={[s.quickBtn, { backgroundColor: accentSoft, borderColor: accent }]}
                    onPress={async () => {
                      try { await api.depositToWallet(amt); fetchAll(); } catch (e: any) { Alert.alert('Error', e.message); }
                    }}
                  >
                    <Text style={[s.quickBtnText, { color: accent }]}>${(amt / 1000)}K</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Broker (Alpaca — real/paper trading) */}
            <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
              <Text style={[s.cardTitle, { color: textP }]}>Broker connection</Text>
              <Text style={[s.brokerHint, { color: textM, marginBottom: 8 }]}>
                Connect once here; then in the Arb Bot tab, one button runs the bot and sends real orders to Alpaca.
              </Text>
              {brokerStatus?.connected ? (
                <>
                  <View style={s.brokerRow}>
                    <View style={[s.brokerBadge, { backgroundColor: 'rgba(34,197,94,0.12)' }]}>
                      <Ionicons name="link" size={18} color={green} />
                      <Text style={[s.brokerProvider, { color: green }]}>{brokerStatus.provider ?? 'Alpaca'}</Text>
                    </View>
                    {brokerStatus.account && (
                      <View style={{ marginTop: 8 }}>
                        {brokerStatus.account.account_number ? (
                          <Text style={[s.brokerHint, { color: textM, marginBottom: 4 }]}>Account #{brokerStatus.account.account_number}</Text>
                        ) : null}
                        <Text style={[s.brokerLabel, { color: textM }]}>Buying power</Text>
                        <Text style={[s.brokerValue, { color: textP }]}>
                          ${Number(brokerStatus.account.buying_power ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </Text>
                        <Text style={[s.brokerLabel, { color: textM, marginTop: 4 }]}>Portfolio value</Text>
                        <Text style={[s.brokerValue, { color: textP }]}>
                          ${Number(brokerStatus.account.portfolio_value ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </Text>
                      </View>
                    )}
                  </View>
                  <TouchableOpacity
                    style={[s.actionBtn, { backgroundColor: 'rgba(239,68,68,0.12)', marginTop: 12 }]}
                    onPress={async () => {
                      try { await api.disconnectBroker(); fetchAll(); } catch (e: any) { Alert.alert('Error', e.message); }
                    }}
                  >
                    <Ionicons name="unlink" size={16} color={red} />
                    <Text style={[s.actionBtnText, { color: red }]}>Disconnect broker</Text>
                  </TouchableOpacity>
                </>
              ) : (
                <>
                  <Text style={[s.brokerHint, { color: textM }]}>
                    Connect your Alpaca account to trade with real or paper funds. Get API keys at alpaca.markets. If you added keys to backend .env, restart the backend and pull to refresh—the broker may already be connected.
                  </Text>
                  <TextInput
                    style={[s.input, { backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)', color: textP, borderColor: border, marginTop: 8 }]}
                    placeholder="API Key ID"
                    placeholderTextColor={textM}
                    value={brokerKey}
                    onChangeText={setBrokerKey}
                    autoCapitalize="none"
                  />
                  <TextInput
                    style={[s.input, { backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)', color: textP, borderColor: border, marginTop: 6 }]}
                    placeholder="API Secret"
                    placeholderTextColor={textM}
                    value={brokerSecret}
                    onChangeText={setBrokerSecret}
                    secureTextEntry
                    autoCapitalize="none"
                  />
                  <TouchableOpacity
                    style={{ flexDirection: 'row', alignItems: 'center', marginTop: 8 }}
                    onPress={() => setBrokerPaper(!brokerPaper)}
                  >
                    <View style={[s.checkbox, { borderColor: border }]}>
                      {brokerPaper && <Ionicons name="checkmark" size={14} color={accent} />}
                    </View>
                    <Text style={[s.brokerHint, { color: textS, marginLeft: 8 }]}>Paper trading</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={{ flexDirection: 'row', alignItems: 'center', marginTop: 6 }}
                    onPress={() => setBrokerUseBrokerApi(!brokerUseBrokerApi)}
                  >
                    <View style={[s.checkbox, { borderColor: border }]}>
                      {brokerUseBrokerApi && <Ionicons name="checkmark" size={14} color={accent} />}
                    </View>
                    <Text style={[s.brokerHint, { color: textS, marginLeft: 8 }]}>Use Broker API (sandbox)</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[s.actionBtn, { backgroundColor: accentSoft, marginTop: 12 }]}
                    disabled={brokerConnecting}
                    onPress={async () => {
                      const key = brokerKey.trim();
                      const secret = brokerSecret.trim();
                      if (!key || !secret) {
                        Alert.alert('Missing keys', 'Please enter your API Key ID and Secret from alpaca.markets.');
                        return;
                      }
                      setBrokerConnecting(true);
                      try {
                        const res = await api.connectBroker(key, secret, brokerPaper, brokerUseBrokerApi) as {
                          status?: string;
                          verified_with_alpaca?: boolean;
                          account_id?: string;
                          account_number?: string;
                          buying_power?: number;
                          equity?: number;
                          currency?: string;
                        };
                        setBrokerKey('');
                        setBrokerSecret('');
                        fetchAll();
                        const verified = res?.verified_with_alpaca !== false;
                        const bp = res?.buying_power != null ? Number(res.buying_power).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
                        const acct = res?.account_number || res?.account_id?.slice(0, 8) || 'Alpaca';
                        const msg = verified
                          ? `Connected and verified with Alpaca.\n\nAccount: ${acct}\nBuying power: $${bp} ${res?.currency || 'USD'}\n\nYou can now trade with paper or live funds.`
                          : `Connected to Alpaca.\n\nAccount: ${acct}\nBuying power: $${bp}\n\nYou can now trade.`;
                        Alert.alert('Alpaca connected', msg);
                      } catch (e: any) {
                        const msg = e?.message || e?.toString?.() || 'Connection failed.';
                        const hint = msg.includes('fetch') || msg.includes('Network') || msg.includes('Failed to')
                          ? '\n\nMake sure the backend is running (e.g. uvicorn from the backend folder) and that this device can reach it. On a physical device use your computer\'s IP instead of 127.0.0.1.'
                          : '';
                        Alert.alert('Connection failed', msg + hint);
                      } finally {
                        setBrokerConnecting(false);
                      }
                    }}
                  >
                    {brokerConnecting ? (
                      <>
                        <ActivityIndicator size="small" color={accent} />
                        <Text style={[s.actionBtnText, { color: accent, marginLeft: 8 }]}>Verifying with Alpaca…</Text>
                      </>
                    ) : (
                      <>
                        <Ionicons name="link" size={16} color={accent} />
                        <Text style={[s.actionBtnText, { color: accent }]}>Connect Alpaca (API keys)</Text>
                      </>
                    )}
                  </TouchableOpacity>

                  <View style={{ flexDirection: 'row', alignItems: 'center', marginVertical: 12, gap: 8 }}>
                    <View style={{ flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: border }} />
                    <Text style={{ fontSize: 11, color: textM }}>or OAuth</Text>
                    <View style={{ flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: border }} />
                  </View>
                  <Text style={[s.brokerHint, { color: textM, marginBottom: 8 }]}>
                    Connect with Alpaca OAuth: no API keys. You’ll sign in at Alpaca and authorize this app.
                  </Text>
                  <TouchableOpacity
                    style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 8 }}
                    onPress={() => setOauthEnv(o => o === 'paper' ? 'live' : 'paper')}
                  >
                    <View style={[s.checkbox, { borderColor: border }]}>
                      {oauthEnv === 'paper' && <Ionicons name="checkmark" size={14} color={accent} />}
                    </View>
                    <Text style={[s.brokerHint, { color: textS, marginLeft: 8 }]}>Paper account (uncheck for live)</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[s.actionBtn, { backgroundColor: isDark ? 'rgba(108,99,255,0.15)' : 'rgba(91,82,230,0.12)', borderWidth: 1, borderColor: accent }]}
                    disabled={oauthOpening}
                    onPress={async () => {
                      setOauthOpening(true);
                      try {
                        const res = await api.getAlpacaOAuthAuthorizeUrl(oauthEnv) as { authorization_url?: string; warning?: string };
                        const url = res?.authorization_url;
                        if (!url) {
                          Alert.alert('OAuth not configured', 'Backend needs ALPACA_OAUTH_CLIENT_ID and ALPACA_OAUTH_REDIRECT_URI. See .env.example.');
                          return;
                        }
                        // Warn if localhost detected
                        if (res?.warning === 'localhost_detected') {
                          Alert.alert(
                            'Localhost detected',
                            'Your redirect URI is localhost. Alpaca cannot reach localhost.\n\n' +
                            'Options:\n' +
                            '1. Use ngrok: ngrok http 8000 → use the ngrok URL in ALPACA_OAUTH_REDIRECT_URI\n' +
                            '2. Deploy your backend (Vercel/Railway) → use the deployed URL\n' +
                            '3. Use API keys instead (no OAuth needed)\n\n' +
                            'Opening Alpaca anyway, but the callback will fail unless you fix the redirect URI.',
                            [
                              { text: 'Cancel', style: 'cancel' },
                              { text: 'Open anyway', onPress: () => {
                                if (Platform.OS === 'web' && typeof window !== 'undefined') {
                                  window.open(url, '_blank', 'noopener,noreferrer');
                                } else {
                                  Linking.openURL(url).catch(() => {
                                    Alert.alert('Cannot open link', 'Open this URL in your browser:\n' + url);
                                  });
                                }
                              }},
                            ],
                          );
                          return;
                        }
                        if (Platform.OS === 'web' && typeof window !== 'undefined') {
                          window.open(url, '_blank', 'noopener,noreferrer');
                        } else {
                          const can = await Linking.canOpenURL(url).catch(() => false);
                          if (!can) {
                            Linking.openURL(url).catch(() => {
                              Alert.alert('Cannot open link', 'Open this URL in your browser:\n' + url);
                            });
                          } else {
                            await Linking.openURL(url);
                          }
                        }
                        Alert.alert(
                          'Authorize in browser',
                          'After authorizing at Alpaca, return to this app and pull down to refresh. Your broker connection will appear when the callback completes.',
                        );
                      } catch (e: any) {
                        const msg = e?.message || e?.toString?.() || 'Could not open Alpaca authorization.';
                        Alert.alert('Error', msg.includes('fetch') || msg.includes('Failed') ? msg + '\n\nIs the backend running on http://localhost:8000?' : msg);
                      } finally {
                        setOauthOpening(false);
                      }
                    }}
                  >
                    {oauthOpening ? (
                      <ActivityIndicator size="small" color={accent} />
                    ) : (
                      <>
                        <Ionicons name="open-outline" size={16} color={accent} />
                        <Text style={[s.actionBtnText, { color: accent }]}>Connect with Alpaca (OAuth)</Text>
                      </>
                    )}
                  </TouchableOpacity>
                </>
              )}
            </View>

            {/* P&L Chart in Wallet */}
            {pnlHistory.length > 2 && (
              <View style={[s.card, { backgroundColor: card, borderColor: border }]}>
                <Text style={[s.cardTitle, { color: textP }]}>Cumulative P&L</Text>
                <FluidChart
                  data={pnlHistory}
                  height={160}
                  width={chartWidth}
                  showLabels={true}
                  showGrid={true}
                  showCrosshair={true}
                  showPriceHeader={false}
                  padding={{ top: 12, right: 12, bottom: 28, left: 54 }}
                />
              </View>
            )}
          </>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { flex: 1 },
  content: { paddingHorizontal: SPACING.lg },

  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', paddingTop: SPACING.sm, marginBottom: SPACING.lg },
  title: { fontSize: 28, fontWeight: '800', letterSpacing: -0.5 },
  subtitle: { fontSize: 11, marginTop: 2, letterSpacing: 0.3 },

  statusBadge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 100, gap: 5 },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusText: { fontSize: 10, fontWeight: '800', letterSpacing: 0.8 },

  tabs: { flexDirection: 'row', gap: 8, marginBottom: SPACING.lg },
  pill: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 100, borderWidth: 1 },
  pillText: { fontSize: 13, fontWeight: '600' },

  card: { borderRadius: RADIUS.lg, borderWidth: 1, padding: SPACING.md, marginBottom: SPACING.md },
  cardLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 1.5, marginBottom: SPACING.sm },
  cardTitle: { fontSize: 15, fontWeight: '700', marginBottom: SPACING.md },

  tttRow: { flexDirection: 'row', alignItems: 'center' },
  tttMain: { alignItems: 'center', paddingRight: SPACING.md },
  tttValue: { fontSize: 36, fontWeight: '800', fontVariant: ['tabular-nums'] },
  tttUnit: { fontSize: 11, marginTop: 2 },
  tttDivider: { width: 1, height: 44, marginHorizontal: SPACING.sm },

  stat: { flex: 1, alignItems: 'center', paddingVertical: 4 },
  statLabel: { fontSize: 9, fontWeight: '600', letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 3 },
  statValue: { fontSize: 15, fontWeight: '800', fontVariant: ['tabular-nums'] },

  metricsRow: { flexDirection: 'row', gap: 8, marginBottom: SPACING.md },
  metricCard: { flex: 1, borderRadius: RADIUS.lg, borderWidth: 1, padding: SPACING.sm, alignItems: 'center' },
  metricLabel: { fontSize: 9, fontWeight: '600', letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 3 },
  metricValue: { fontSize: 18, fontWeight: '800', fontVariant: ['tabular-nums'] },

  fpgaRow: { flexDirection: 'row', alignItems: 'center', gap: SPACING.sm, marginBottom: SPACING.sm },
  fpgaIcon: { width: 40, height: 40, borderRadius: 20, justifyContent: 'center', alignItems: 'center' },
  fpgaTitle: { fontSize: 14, fontWeight: '700' },
  fpgaSub: { fontSize: 10, marginTop: 1 },
  pipelineRow: { flexDirection: 'row', justifyContent: 'space-between', paddingTop: SPACING.sm },
  pipelineStage: { alignItems: 'center', flex: 1 },
  pipelineBar: { width: 18, borderRadius: 4, marginBottom: 3 },
  pipelineLabel: { fontSize: 7, textAlign: 'center', lineHeight: 9 },

  stratRow: { flexDirection: 'row', gap: 8, marginBottom: SPACING.md },
  stratCard: { flex: 1, borderRadius: RADIUS.lg, borderWidth: 1, padding: SPACING.md },
  stratHead: { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 6 },
  stratName: { fontSize: 12, fontWeight: '600' },
  stratPnl: { fontSize: 22, fontWeight: '800', fontVariant: ['tabular-nums'] },
  stratMeta: { fontSize: 10, marginTop: 3 },

  tableHead: { flexDirection: 'row', paddingBottom: 8, borderBottomWidth: StyleSheet.hairlineWidth, marginBottom: 4 },
  th: { fontSize: 8, fontWeight: '700', letterSpacing: 0.5, textTransform: 'uppercase' },
  row: { flexDirection: 'row', paddingVertical: 7 },
  td: { fontSize: 11, fontVariant: ['tabular-nums'] },

  riskGrid: { flexDirection: 'row' },
  cbBanner: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: SPACING.sm, paddingTop: SPACING.sm, borderTopWidth: StyleSheet.hairlineWidth },
  cbText: { fontSize: 11, fontWeight: '700' },

  latRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8 },
  latName: { flex: 1.5, fontSize: 11, textTransform: 'capitalize' },
  latBarBg: { flex: 2, height: 5, borderRadius: 3, overflow: 'hidden' },
  latBar: { height: '100%', borderRadius: 3 },
  latVal: { flex: 0.7, fontSize: 11, fontWeight: '700', textAlign: 'right', fontVariant: ['tabular-nums'] },

  botHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACING.md },
  botIcon: { width: 52, height: 52, borderRadius: 26, justifyContent: 'center', alignItems: 'center' },
  botTitle: { fontSize: 18, fontWeight: '700' },
  botSub: { fontSize: 11, marginTop: 2 },
  botUptime: { fontSize: 10, marginTop: 1 },
  botBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingVertical: 10, borderRadius: 100 },
  botBtnText: { fontSize: 13, fontWeight: '700' },
  budgetInput: { borderWidth: 1, borderRadius: RADIUS.md, paddingHorizontal: 14, paddingVertical: 10, fontSize: 16, fontWeight: '600', fontVariant: ['tabular-nums'] },
  budgetChip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 100, borderWidth: 1 },
  hireBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: RADIUS.md },

  tradeSummary: { borderRadius: RADIUS.md, borderWidth: 1, padding: SPACING.sm, marginBottom: SPACING.sm },
  tradeSummaryRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 3 },
  tradeSummaryLabel: { fontSize: 11 },
  tradeSummaryValue: { fontSize: 11, fontWeight: '700', fontVariant: ['tabular-nums'] },

  tradeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10 },
  tradeSymbol: { fontSize: 13, fontWeight: '700' },
  tradeVenues: { fontSize: 10, marginTop: 2 },
  tradeDetailRow: { flexDirection: 'row', alignItems: 'center', marginTop: 3 },
  tradeQtyBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  tradePnl: { fontSize: 14, fontWeight: '800', fontVariant: ['tabular-nums'] },
  tradeTime: { fontSize: 9, marginTop: 2 },

  walletHeader: { flexDirection: 'row', alignItems: 'center', gap: SPACING.md },
  walletIcon: { width: 56, height: 56, borderRadius: 28, justifyContent: 'center', alignItems: 'center' },
  walletLabel: { fontSize: 11, fontWeight: '600', letterSpacing: 0.3 },
  walletBalance: { fontSize: 32, fontWeight: '800', fontVariant: ['tabular-nums'], marginTop: 2 },

  inputRow: { marginBottom: SPACING.sm },
  input: { borderWidth: 1, borderRadius: RADIUS.md, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, fontWeight: '600' },
  btnRow: { flexDirection: 'row', gap: 10 },
  actionBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderRadius: RADIUS.md },
  actionBtnText: { fontSize: 14, fontWeight: '700' },

  quickRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  quickBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 100, borderWidth: 1 },
  quickBtnText: { fontSize: 12, fontWeight: '700' },

  brokerRow: {},
  brokerBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 6, paddingHorizontal: 10, borderRadius: RADIUS.md, alignSelf: 'flex-start' },
  brokerProvider: { fontSize: 13, fontWeight: '700' },
  brokerLabel: { fontSize: 11, fontWeight: '600' },
  brokerValue: { fontSize: 16, fontWeight: '700', fontVariant: ['tabular-nums'] },
  brokerHint: { fontSize: 12, lineHeight: 18 },
  checkbox: { width: 20, height: 20, borderRadius: 4, borderWidth: 1.5, justifyContent: 'center', alignItems: 'center' },
});
