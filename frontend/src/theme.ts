export const SPACING = {
  xs: 4, sm: 8, md: 14, lg: 20, xl: 28, xxl: 40, xxxl: 56,
};

export const FONT_SIZES = {
  xs: 11, sm: 13, base: 16, lg: 18, xl: 22, xxl: 28, xxxl: 34, display: 42, hero: 52,
};

export const RADIUS = {
  sm: 8, md: 14, lg: 20, xl: 24, full: 9999,
};

export interface ThemeColors {
  bg: { primary: string; secondary: string; tertiary: string; elevated: string };
  text: { primary: string; secondary: string; tertiary: string; muted: string; accent: string };
  border: string;
  card: string;
  cardShadow: string;
  green: { primary: string; soft: string; text: string };
  red: { primary: string; soft: string; text: string };
  accent: {
    blue: string; blueSoft: string; purple: string; purpleSoft: string;
    amber: string; amberSoft: string; cyan: string; cyanSoft: string;
  };
  glass: { fill: string; border: string; borderLight: string; fillHover: string; highlight: string; innerGlow: string };
  surface: { card: string; glass: string; glassBorder: string; elevated: string };
  status: { success: string; warning: string; error: string; info: string };
  brand: { primary: string; secondary: string; aiGlow: string };
  chart: { green: string; red: string; blue: string; purple: string; yellow: string };
}

export const LIGHT: ThemeColors = {
  bg: { primary: '#FFFFFF', secondary: '#F8F9FA', tertiary: '#F0F1F3', elevated: '#FFFFFF' },
  text: { primary: '#1A1A1A', secondary: '#6B7280', tertiary: '#9CA3AF', muted: '#C4C4C4', accent: '#00C805' },
  border: '#E8E8E8',
  card: '#FFFFFF',
  cardShadow: 'rgba(0,0,0,0.06)',
  green: { primary: '#00C805', soft: 'rgba(0,200,5,0.08)', text: '#00C805' },
  red: { primary: '#FF5000', soft: 'rgba(255,80,0,0.08)', text: '#FF5000' },
  accent: {
    blue: '#4C6EF5', blueSoft: 'rgba(76,110,245,0.08)',
    purple: '#7C3AED', purpleSoft: 'rgba(124,58,237,0.08)',
    amber: '#F59E0B', amberSoft: 'rgba(245,158,11,0.08)',
    cyan: '#06B6D4', cyanSoft: 'rgba(6,182,212,0.08)',
  },
  glass: { fill: 'rgba(0,0,0,0.02)', border: '#E8E8E8', borderLight: '#D1D5DB', fillHover: 'rgba(0,0,0,0.04)', highlight: 'rgba(0,0,0,0.02)', innerGlow: 'rgba(0,0,0,0.01)' },
  surface: { card: '#FFFFFF', glass: '#FFFFFF', glassBorder: '#E8E8E8', elevated: '#FFFFFF' },
  status: { success: '#00C805', warning: '#F59E0B', error: '#FF5000', info: '#4C6EF5' },
  brand: { primary: '#4C6EF5', secondary: '#7C3AED', aiGlow: 'rgba(76,110,245,0.08)' },
  chart: { green: '#00C805', red: '#FF5000', blue: '#4C6EF5', purple: '#7C3AED', yellow: '#F59E0B' },
};

export const DARK: ThemeColors = {
  bg: { primary: '#000000', secondary: '#0C0C0C', tertiary: '#1A1A1A', elevated: '#1A1A1A' },
  text: { primary: '#FAFAFA', secondary: '#9CA3AF', tertiary: '#6B7280', muted: '#4B5563', accent: '#00DC82' },
  border: '#222222',
  card: '#111111',
  cardShadow: 'transparent',
  green: { primary: '#00DC82', soft: 'rgba(0,220,130,0.12)', text: '#00DC82' },
  red: { primary: '#FF4757', soft: 'rgba(255,71,87,0.12)', text: '#FF4757' },
  accent: {
    blue: '#60A5FA', blueSoft: 'rgba(96,165,250,0.12)',
    purple: '#A78BFA', purpleSoft: 'rgba(167,139,250,0.12)',
    amber: '#FBBF24', amberSoft: 'rgba(251,191,36,0.12)',
    cyan: '#22D3EE', cyanSoft: 'rgba(34,211,238,0.12)',
  },
  glass: { fill: 'rgba(255,255,255,0.04)', border: 'rgba(255,255,255,0.10)', borderLight: 'rgba(255,255,255,0.16)', fillHover: 'rgba(255,255,255,0.07)', highlight: 'rgba(255,255,255,0.06)', innerGlow: 'rgba(255,255,255,0.02)' },
  surface: { card: 'rgba(255,255,255,0.04)', glass: 'rgba(255,255,255,0.04)', glassBorder: 'rgba(255,255,255,0.10)', elevated: 'rgba(26,26,46,0.95)' },
  status: { success: '#00DC82', warning: '#FBBF24', error: '#FF4757', info: '#60A5FA' },
  brand: { primary: '#60A5FA', secondary: '#A78BFA', aiGlow: 'rgba(96,165,250,0.10)' },
  chart: { green: '#00DC82', red: '#FF4757', blue: '#60A5FA', purple: '#A78BFA', yellow: '#FBBF24' },
};

// Backward compat for screens that still import COLORS directly
export const COLORS = DARK;
