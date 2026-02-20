import React from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { COLORS, FONT_SIZES, SPACING } from '../theme';

export default function LoadingScreen({ message = 'Loading...' }: { message?: string }) {
  return (
    <View style={styles.container}>
      <ActivityIndicator size="small" color={COLORS.accent.blue} />
      <Text style={styles.text}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.bg.primary,
    justifyContent: 'center',
    alignItems: 'center',
    gap: SPACING.md,
  },
  text: {
    color: COLORS.text.tertiary,
    fontSize: FONT_SIZES.sm,
    fontWeight: '500',
    letterSpacing: 0.2,
  },
});
