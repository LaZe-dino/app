import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import Animated, {
  FadeInDown,
  FadeInLeft,
  SlideInRight,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
  withSequence,
  Easing,
} from 'react-native-reanimated';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, FONT_SIZES, RADIUS } from '../theme';

interface SwarmThought {
  id: string;
  agent: string;
  agentType: string;
  thought: string;
  symbol?: string;
  timestamp: string;
  eventType: string;
}

interface Props {
  events: any[];
  maxItems?: number;
}

const AGENT_ICONS: Record<string, string> = {
  scout: 'eye-outline',
  analyst: 'analytics-outline',
  news_hound: 'newspaper-outline',
  strategist: 'bulb-outline',
  ingestion: 'document-text-outline',
  quantitative: 'stats-chart-outline',
  synthesis: 'git-merge-outline',
  risk: 'shield-checkmark-outline',
};

const AGENT_COLORS: Record<string, string> = {
  scout: COLORS.status.warning,
  analyst: COLORS.brand.primary,
  news_hound: COLORS.brand.secondary,
  strategist: COLORS.status.success,
  ingestion: '#FF9800',
  quantitative: COLORS.brand.primary,
  synthesis: '#E040FB',
  risk: COLORS.status.error,
};

function agentTypeFromName(name: string): string {
  const lower = name.toLowerCase();
  if (lower.includes('scout')) return 'scout';
  if (lower.includes('analyst')) return 'analyst';
  if (lower.includes('news')) return 'news_hound';
  if (lower.includes('strategist')) return 'strategist';
  if (lower.includes('ingestion')) return 'ingestion';
  if (lower.includes('quant')) return 'quantitative';
  if (lower.includes('synthesis')) return 'synthesis';
  if (lower.includes('risk')) return 'risk';
  return 'strategist';
}

function formatThought(event: any): string {
  const type = event.event_type || '';
  const data = event.data || {};
  const agent = event.source_agent || '';

  if (type === 'price_spike') {
    return `Detected ${data.direction || ''} price spike of ${data.change_pct?.toFixed(1)}% — alerting Analyst`;
  }
  if (type === 'volume_anomaly') {
    return `Volume spike: ${data.spike_ratio?.toFixed(1)}x average — unusual activity detected`;
  }
  if (type === 'technical_signal') {
    const bias = data.bias || 'neutral';
    return `Technical analysis complete — bias: ${bias.toUpperCase()}, RSI: ${data.rsi || 'N/A'}`;
  }
  if (type === 'sentiment_shift') {
    return `Sentiment shift detected: ${data.sentiment_label || 'neutral'} (score: ${data.sentiment_score?.toFixed(2)})`;
  }
  if (type === 'news_alert') {
    const headline = data.top_headlines?.[0] || 'Breaking news detected';
    return headline;
  }
  if (type === 'trade_recommendation') {
    const action = data.action || data.original_thesis?.action || 'HOLD';
    const conf = data.confidence || data.original_thesis?.confidence || 0;
    return `${action} signal — confidence: ${(conf * 100).toFixed(0)}%`;
  }
  if (type === 'risk_alert') {
    const verdict = data.risk_verdict?.verdict || 'REVIEWING';
    return `Risk verdict: ${verdict} — ${data.risk_verdict?.reasoning || 'Evaluating exposure limits'}`;
  }
  if (type === 'agent_handoff') {
    return `Handing off to ${event.target_agent || 'next agent'}`;
  }
  if (type === 'swarm_cycle_complete') {
    return `Full analysis cycle complete`;
  }
  if (type === 'agent_status') {
    return `Agent ${data.action || 'update'}: ${data.state || ''}`;
  }
  return `Processing ${event.symbol || 'data'}...`;
}

function PulsingDot({ color }: { color: string }) {
  const opacity = useSharedValue(1);

  useEffect(() => {
    opacity.value = withRepeat(
      withSequence(
        withTiming(0.3, { duration: 800, easing: Easing.inOut(Easing.ease) }),
        withTiming(1, { duration: 800, easing: Easing.inOut(Easing.ease) }),
      ),
      -1,
      false,
    );
  }, []);

  const animStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
  }));

  return (
    <Animated.View
      style={[
        { width: 8, height: 8, borderRadius: 4, backgroundColor: color },
        animStyle,
      ]}
    />
  );
}

function ThoughtBubble({ thought, index }: { thought: SwarmThought; index: number }) {
  const agentColor = AGENT_COLORS[thought.agentType] || COLORS.text.muted;
  const agentIcon = AGENT_ICONS[thought.agentType] || 'cube-outline';

  return (
    <Animated.View
      entering={FadeInDown.delay(index * 60).duration(400).springify()}
      style={styles.thoughtRow}
    >
      <View style={[styles.agentDot, { backgroundColor: `${agentColor}25` }]}>
        <Ionicons name={agentIcon as any} size={14} color={agentColor} />
      </View>

      <View style={styles.thoughtContent}>
        <View style={styles.thoughtHeader}>
          <Text style={[styles.agentName, { color: agentColor }]}>
            {thought.agent}
          </Text>
          {thought.symbol && (
            <Animated.View entering={SlideInRight.delay(100)} style={styles.symbolBadge}>
              <Text style={styles.symbolText}>{thought.symbol}</Text>
            </Animated.View>
          )}
          <Text style={styles.thoughtTime}>
            {new Date(thought.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            })}
          </Text>
        </View>

        <Animated.Text
          entering={FadeInLeft.delay(index * 60 + 100).duration(300)}
          style={styles.thoughtText}
        >
          {thought.thought}
        </Animated.Text>
      </View>
    </Animated.View>
  );
}

export default function SwarmThoughtFeed({ events, maxItems = 20 }: Props) {
  const [thoughts, setThoughts] = useState<SwarmThought[]>([]);
  const scrollRef = useRef<ScrollView>(null);

  useEffect(() => {
    const mapped: SwarmThought[] = events
      .filter((e) => e.event_type && e.event_type !== 'agent_status')
      .map((e, i) => ({
        id: e.event_id || `evt-${i}-${Date.now()}`,
        agent: e.source_agent || 'Swarm',
        agentType: agentTypeFromName(e.source_agent || ''),
        thought: formatThought(e),
        symbol: e.symbol,
        timestamp: e.timestamp || new Date().toISOString(),
        eventType: e.event_type,
      }))
      .slice(-maxItems);

    setThoughts(mapped);
  }, [events, maxItems]);

  useEffect(() => {
    const timer = setTimeout(() => {
      scrollRef.current?.scrollToEnd({ animated: true });
    }, 200);
    return () => clearTimeout(timer);
  }, [thoughts.length]);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <PulsingDot color={COLORS.status.success} />
        <Text style={styles.headerText}>SWARM THOUGHT STREAM</Text>
        <Text style={styles.headerCount}>{thoughts.length}</Text>
      </View>

      <ScrollView
        ref={scrollRef}
        style={styles.feed}
        contentContainerStyle={styles.feedContent}
        showsVerticalScrollIndicator={false}
        nestedScrollEnabled
      >
        {thoughts.length === 0 ? (
          <Animated.View entering={FadeInDown} style={styles.emptyWrap}>
            <Ionicons name="radio-outline" size={24} color={COLORS.text.muted} />
            <Text style={styles.emptyText}>Listening for swarm activity...</Text>
          </Animated.View>
        ) : (
          thoughts.map((t, i) => (
            <ThoughtBubble key={t.id} thought={t} index={i} />
          ))
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: RADIUS.lg,
    backgroundColor: COLORS.surface.card,
    borderWidth: 0.5,
    borderColor: COLORS.surface.glassBorder,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
    paddingHorizontal: SPACING.md,
    paddingVertical: SPACING.sm,
    borderBottomWidth: 0.5,
    borderBottomColor: COLORS.surface.glassBorder,
    backgroundColor: COLORS.bg.tertiary,
  },
  headerText: {
    fontSize: 9,
    fontWeight: '800',
    color: COLORS.status.success,
    fontFamily: 'Menlo',
    letterSpacing: 1.5,
    flex: 1,
  },
  headerCount: {
    fontSize: 9,
    fontWeight: '700',
    color: COLORS.text.muted,
    fontFamily: 'Menlo',
  },
  feed: {
    maxHeight: 320,
  },
  feedContent: {
    padding: SPACING.sm,
  },
  emptyWrap: {
    alignItems: 'center',
    paddingVertical: SPACING.xl,
    gap: SPACING.sm,
  },
  emptyText: {
    fontSize: FONT_SIZES.xs,
    color: COLORS.text.muted,
    fontFamily: 'Menlo',
  },
  thoughtRow: {
    flexDirection: 'row',
    marginBottom: SPACING.xs,
    alignItems: 'flex-start',
  },
  agentDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: SPACING.sm,
    marginTop: 2,
  },
  thoughtContent: {
    flex: 1,
    backgroundColor: COLORS.bg.tertiary,
    borderRadius: RADIUS.md,
    padding: SPACING.sm,
  },
  thoughtHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: SPACING.sm,
    marginBottom: 3,
  },
  agentName: {
    fontSize: 9,
    fontWeight: '800',
    fontFamily: 'Menlo',
  },
  symbolBadge: {
    backgroundColor: `${COLORS.brand.primary}20`,
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderRadius: 3,
  },
  symbolText: {
    fontSize: 8,
    color: COLORS.brand.primary,
    fontFamily: 'Menlo',
    fontWeight: '700',
  },
  thoughtTime: {
    fontSize: 8,
    color: COLORS.text.muted,
    fontFamily: 'Menlo',
    marginLeft: 'auto',
  },
  thoughtText: {
    fontSize: FONT_SIZES.xs,
    color: COLORS.text.secondary,
    lineHeight: 16,
  },
});
