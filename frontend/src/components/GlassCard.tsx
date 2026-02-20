import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { BlurView } from 'expo-blur';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, RADIUS, SPACING } from '../theme';

interface GlassCardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  intensity?: number;
  variant?: 'default' | 'elevated' | 'subtle';
}

export default function GlassCard({
  children,
  style,
  intensity = 40,
  variant = 'default',
}: GlassCardProps) {
  const borderColor =
    variant === 'elevated' ? COLORS.glass.borderLight :
    variant === 'subtle' ? 'rgba(255,255,255,0.05)' :
    COLORS.glass.border;

  return (
    <View style={[styles.outer, { borderColor }, style]}>
      {/* Top edge highlight — simulates light refraction on glass */}
      <LinearGradient
        colors={['rgba(255,255,255,0.09)', 'rgba(255,255,255,0.0)']}
        style={styles.topHighlight}
      />
      <BlurView intensity={intensity} tint="dark" style={styles.blur}>
        <View style={[styles.inner, variant === 'elevated' && styles.innerElevated]}>
          {children}
        </View>
      </BlurView>
    </View>
  );
}

const styles = StyleSheet.create({
  outer: {
    borderRadius: RADIUS.xl,
    overflow: 'hidden',
    borderWidth: 0.5,
    position: 'relative',
  },
  topHighlight: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: 1,
    zIndex: 1,
  },
  blur: {
    overflow: 'hidden',
  },
  inner: {
    backgroundColor: COLORS.glass.fill,
    padding: SPACING.lg,
  },
  innerElevated: {
    backgroundColor: COLORS.glass.fillHover,
  },
});
