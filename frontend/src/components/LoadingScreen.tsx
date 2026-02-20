import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useTheme } from '../contexts/ThemeContext';
import { FONT_SIZES, SPACING } from '../theme';

export default function LoadingScreen({ message = 'Loading...' }: { message?: string }) {
  const { colors } = useTheme();

  return (
    <View style={[styles.container, { backgroundColor: colors.bg.primary }]}>
      <ActivityIndicator size="small" color={colors.green.primary} />
      <Text style={[styles.text, { color: colors.text.tertiary }]}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: SPACING.md,
  },
  text: {
    fontSize: FONT_SIZES.sm,
    fontWeight: '500',
    letterSpacing: 0.2,
  },
});
