import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, SPACING, FONT_SIZES, RADIUS } from '../theme';

interface SignalBadgeProps {
  action: string;
  confidence: number;
  small?: boolean;
}

export default function SignalBadge({ action, confidence, small }: SignalBadgeProps) {
  const color =
    action === 'BUY' ? COLORS.green.primary :
    action === 'SELL' ? COLORS.red.primary :
    COLORS.accent.amber;
  const bg =
    action === 'BUY' ? COLORS.green.soft :
    action === 'SELL' ? COLORS.red.soft :
    COLORS.accent.amberSoft;
  const icon =
    action === 'BUY' ? 'arrow-up' :
    action === 'SELL' ? 'arrow-down' :
    'remove-outline';

  return (
    <View style={[styles.badge, { backgroundColor: bg }, small && styles.badgeSmall]}>
      <Ionicons name={icon as any} size={small ? 11 : 13} color={color} />
      <Text style={[styles.text, { color }, small && styles.textSmall]}>{action}</Text>
      <Text style={[styles.conf, small && styles.textSmall]}>{Math.round(confidence * 100)}%</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: SPACING.md,
    paddingVertical: SPACING.sm,
    borderRadius: RADIUS.full,
    gap: 5,
  },
  badgeSmall: {
    paddingHorizontal: SPACING.sm + 2,
    paddingVertical: SPACING.xs + 1,
  },
  text: {
    fontSize: FONT_SIZES.sm,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  textSmall: {
    fontSize: FONT_SIZES.xs,
  },
  conf: {
    fontSize: FONT_SIZES.xs,
    color: COLORS.text.tertiary,
    fontWeight: '500',
  },
});
