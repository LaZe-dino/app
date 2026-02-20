import React from 'react';
import { View, StyleSheet, ViewStyle, Platform } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { RADIUS, SPACING } from '../theme';

interface GlassCardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  variant?: 'default' | 'elevated' | 'subtle';
}

export default function GlassCard({ children, style, variant = 'default' }: GlassCardProps) {
  const { colors, isDark } = useTheme();

  const bgColor = isDark
    ? (variant === 'elevated' ? colors.glass.fillHover : colors.glass.fill)
    : colors.card;

  const borderColor = isDark
    ? (variant === 'elevated' ? colors.glass.borderLight : variant === 'subtle' ? 'rgba(255,255,255,0.05)' : colors.glass.border)
    : colors.border;

  return (
    <View style={[
      styles.outer,
      {
        backgroundColor: bgColor,
        borderColor,
        ...(isDark ? {} : {
          shadowColor: '#000',
          shadowOffset: { width: 0, height: 1 },
          shadowOpacity: 0.05,
          shadowRadius: 3,
          ...(Platform.OS === 'android' ? { elevation: 1 } : {}),
        }),
      },
      style,
    ]}>
      <View style={styles.inner}>
        {children}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  outer: {
    borderRadius: RADIUS.xl,
    overflow: 'hidden',
    borderWidth: 0.5,
  },
  inner: {
    padding: SPACING.lg,
  },
});
