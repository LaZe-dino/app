import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../contexts/ThemeContext';
import { SPACING, FONT_SIZES, RADIUS } from '../theme';

interface SignalBadgeProps {
  action: string;
  confidence: number;
  small?: boolean;
}

export default function SignalBadge({ action, confidence, small }: SignalBadgeProps) {
  const { colors } = useTheme();

  const color =
    action === 'BUY' ? colors.green.primary :
    action === 'SELL' ? colors.red.primary :
    colors.accent.amber;
  const bg =
    action === 'BUY' ? colors.green.soft :
    action === 'SELL' ? colors.red.soft :
    colors.accent.amberSoft;
  const icon =
    action === 'BUY' ? 'arrow-up' :
    action === 'SELL' ? 'arrow-down' :
    'remove-outline';

  return (
    <View style={[styles.badge, { backgroundColor: bg }, small && styles.badgeSmall]}>
      <Ionicons name={icon as any} size={small ? 11 : 13} color={color} />
      <Text style={[styles.text, { color }, small && styles.textSmall]}>{action}</Text>
      <Text style={[styles.conf, { color: colors.text.tertiary }, small && styles.textSmall]}>
        {Math.round(confidence * 100)}%
      </Text>
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
    fontWeight: '500',
  },
});
