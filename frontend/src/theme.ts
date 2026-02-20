/**
 * Design System — Apple Liquid Glass + Robinhood
 *
 * Backgrounds:  Deep rich blacks with blue undertone (Apple dark mode)
 * Surfaces:     High-transparency frosted glass with luminous borders
 * Typography:   Large bold numbers (Robinhood), clean SF-style labels
 * Spacing:      Generous whitespace for breathing room
 */

export const COLORS = {
  bg: {
    primary: '#050508',
    secondary: '#0C0C12',
    tertiary: '#131320',
    elevated: '#1A1A2E',
  },
  glass: {
    fill: 'rgba(255, 255, 255, 0.04)',
    fillHover: 'rgba(255, 255, 255, 0.07)',
    border: 'rgba(255, 255, 255, 0.10)',
    borderLight: 'rgba(255, 255, 255, 0.16)',
    highlight: 'rgba(255, 255, 255, 0.06)',
    innerGlow: 'rgba(255, 255, 255, 0.02)',
  },
  text: {
    primary: '#FAFAFA',
    secondary: '#9CA3AF',
    tertiary: '#6B7280',
    muted: '#4B5563',
    accent: '#60A5FA',
  },
  green: {
    primary: '#00DC82',
    soft: 'rgba(0, 220, 130, 0.12)',
    text: '#34D399',
  },
  red: {
    primary: '#FF4757',
    soft: 'rgba(255, 71, 87, 0.12)',
    text: '#FB7185',
  },
  accent: {
    blue: '#60A5FA',
    blueSoft: 'rgba(96, 165, 250, 0.12)',
    purple: '#A78BFA',
    purpleSoft: 'rgba(167, 139, 250, 0.12)',
    amber: '#FBBF24',
    amberSoft: 'rgba(251, 191, 36, 0.12)',
    cyan: '#22D3EE',
    cyanSoft: 'rgba(34, 211, 238, 0.12)',
  },
  // Backward compat aliases
  surface: {
    card: 'rgba(255, 255, 255, 0.04)',
    glass: 'rgba(255, 255, 255, 0.04)',
    glassBorder: 'rgba(255, 255, 255, 0.10)',
    elevated: 'rgba(26, 26, 46, 0.95)',
  },
  status: {
    success: '#00DC82',
    warning: '#FBBF24',
    error: '#FF4757',
    info: '#60A5FA',
  },
  brand: {
    primary: '#60A5FA',
    secondary: '#A78BFA',
    aiGlow: 'rgba(96, 165, 250, 0.10)',
  },
  chart: {
    green: '#00DC82',
    red: '#FF4757',
    blue: '#60A5FA',
    purple: '#A78BFA',
    yellow: '#FBBF24',
  },
};

export const SPACING = {
  xs: 4,
  sm: 8,
  md: 14,
  lg: 20,
  xl: 28,
  xxl: 40,
  xxxl: 56,
};

export const FONT_SIZES = {
  xs: 11,
  sm: 13,
  base: 16,
  lg: 18,
  xl: 22,
  xxl: 28,
  xxxl: 34,
  display: 42,
  hero: 52,
};

export const RADIUS = {
  sm: 8,
  md: 14,
  lg: 20,
  xl: 24,
  full: 9999,
};
