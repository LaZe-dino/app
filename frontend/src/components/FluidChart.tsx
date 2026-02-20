import React, { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import {
  View, Text, StyleSheet, useWindowDimensions,
  Animated as RNAnimated, PanResponder,
} from 'react-native';
import Svg, {
  Path, Defs, LinearGradient, Stop, Line,
  Text as SvgText, Rect, Circle, G,
} from 'react-native-svg';
import { useTheme } from '../contexts/ThemeContext';

// ─── Types ──────────────────────────────────────────────────────────

export interface DataPoint {
  time: string;
  value: number;
  volume?: number;
}

export type TimeRange = '1D' | '1W' | '1M' | '3M' | '1Y' | 'MAX';

export interface FluidChartProps {
  data: DataPoint[];
  width?: number;
  height?: number;
  color?: string;
  showGrid?: boolean;
  showLabels?: boolean;
  showVolume?: boolean;
  showCrosshair?: boolean;
  showPriceHeader?: boolean;
  showRangeSelector?: boolean;
  ranges?: TimeRange[];
  activeRange?: TimeRange;
  onRangeChange?: (range: TimeRange) => void;
  onCrosshairChange?: (point: { value: number; change: number; changePct: number; time: string } | null) => void;
  animated?: boolean;
  padding?: { top: number; right: number; bottom: number; left: number };
  formatValue?: (v: number) => string;
  formatTime?: (t: string, range?: TimeRange) => string;
}

// ─── Smooth cubic bezier path ───────────────────────────────────────

function smoothPath(pts: { x: number; y: number }[]): string {
  if (pts.length < 2) return '';
  let d = `M ${pts[0].x},${pts[0].y}`;
  const t = 0.3;
  for (let i = 0; i < pts.length - 1; i++) {
    const c = pts[i], n = pts[i + 1];
    const p = pts[i - 1] || c, a = pts[i + 2] || n;
    d += ` C ${c.x + (n.x - p.x) * t},${c.y + (n.y - p.y) * t} ${n.x - (a.x - c.x) * t},${n.y - (a.y - c.y) * t} ${n.x},${n.y}`;
  }
  return d;
}

// ─── Helpers ────────────────────────────────────────────────────────

function defaultFormatValue(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 10_000) return `${(v / 1_000).toFixed(1)}K`;
  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(2)}K`;
  return Math.abs(v) < 1 ? v.toFixed(4) : v.toFixed(2);
}

function defaultFormatTime(t: string, range?: TimeRange): string {
  try {
    const d = new Date(t);
    if (isNaN(d.getTime())) return t.slice(-5);
    if (range === '1D') return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (range === '1W') return d.toLocaleDateString([], { weekday: 'short' });
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch {
    return t.slice(-5);
  }
}

function downsample(data: DataPoint[], maxPts: number): DataPoint[] {
  if (data.length <= maxPts) return data;
  const step = data.length / maxPts;
  const result: DataPoint[] = [data[0]];
  for (let i = 1; i < maxPts - 1; i++) {
    const idx = Math.round(i * step);
    result.push(data[Math.min(idx, data.length - 1)]);
  }
  result.push(data[data.length - 1]);
  return result;
}

// ─── Component ──────────────────────────────────────────────────────

const DEFAULT_RANGES: TimeRange[] = ['1D', '1W', '1M', '3M', '1Y', 'MAX'];

export default function FluidChart({
  data,
  width: propWidth,
  height = 220,
  color: propColor,
  showGrid = true,
  showLabels = true,
  showVolume = false,
  showCrosshair = true,
  showPriceHeader = true,
  showRangeSelector = false,
  ranges = DEFAULT_RANGES,
  activeRange,
  onRangeChange,
  onCrosshairChange,
  animated = true,
  padding: padProp,
  formatValue = defaultFormatValue,
  formatTime = defaultFormatTime,
}: FluidChartProps) {
  const { colors, isDark } = useTheme();
  const { width: screenW } = useWindowDimensions();
  const width = propWidth || screenW - 40;
  const padding = padProp || { top: 20, right: 16, bottom: showVolume ? 56 : 30, left: 50 };

  const [selectedRange, setSelectedRange] = useState<TimeRange>(activeRange || '1D');
  const [touchIdx, setTouchIdx] = useState<number | null>(null);
  const fadeAnim = useRef(new RNAnimated.Value(1)).current;
  const svgRef = useRef<View>(null);

  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom - (showVolume ? 32 : 0);
  const volH = showVolume ? 28 : 0;

  // Downsample for performance
  const sampled = useMemo(() => downsample(data || [], 200), [data]);

  const dataKey = useMemo(() => {
    if (!sampled.length) return '';
    return `${sampled.length}-${sampled[0]?.value}-${sampled[sampled.length - 1]?.value}-${selectedRange}`;
  }, [sampled, selectedRange]);

  useEffect(() => {
    if (animated && dataKey) {
      fadeAnim.setValue(0.2);
      RNAnimated.timing(fadeAnim, { toValue: 1, duration: 350, useNativeDriver: true }).start();
    }
  }, [dataKey, animated]);

  // ── Computed chart data ────────────────────────────────────────────

  const { points, lineColor, linePath, areaPath, yLabels, xLabels, minVal, maxVal, volumes, maxVol } = useMemo(() => {
    if (!sampled || sampled.length < 2) {
      return { points: [], lineColor: colors.green.primary, linePath: '', areaPath: '', yLabels: [], xLabels: [], minVal: 0, maxVal: 0, volumes: [], maxVol: 0 };
    }

    const values = sampled.map(d => d.value);
    const mn = Math.min(...values);
    const mx = Math.max(...values);
    const rng = mx - mn || 1;
    const pad = rng * 0.06;
    const aMn = mn - pad, aMx = mx + pad, aRng = aMx - aMn;

    const isUp = values[values.length - 1] >= values[0];
    const lc = propColor || (isUp ? colors.green.primary : colors.red.primary);

    const pts = sampled.map((d, i) => ({
      x: padding.left + (i / (sampled.length - 1)) * chartW,
      y: padding.top + (1 - (d.value - aMn) / aRng) * chartH,
    }));

    const lp = smoothPath(pts);
    const ap = lp
      + ` L ${pts[pts.length - 1].x},${padding.top + chartH}`
      + ` L ${pts[0].x},${padding.top + chartH} Z`;

    // Y labels
    const yl: { y: number; label: string }[] = [];
    for (let i = 0; i <= 4; i++) {
      const val = aMn + (aRng * (4 - i) / 4);
      yl.push({ y: padding.top + (i / 4) * chartH, label: formatValue(val) });
    }

    // X labels
    const xl: { x: number; label: string }[] = [];
    const step = Math.max(1, Math.floor(sampled.length / 5));
    for (let i = 0; i < sampled.length; i += step) {
      xl.push({ x: padding.left + (i / (sampled.length - 1)) * chartW, label: formatTime(sampled[i].time, selectedRange) });
    }

    // Volume
    const vols = sampled.map(d => d.volume || 0);
    const mxV = Math.max(...vols, 1);

    return { points: pts, lineColor: lc, linePath: lp, areaPath: ap, yLabels: yl, xLabels: xl, minVal: mn, maxVal: mx, volumes: vols, maxVol: mxV };
  }, [sampled, width, height, colors, propColor, padding, chartW, chartH, selectedRange, formatValue, formatTime]);

  // ── Touch / Pan handler ────────────────────────────────────────────

  const panResponder = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => showCrosshair,
    onMoveShouldSetPanResponder: () => showCrosshair,
    onPanResponderGrant: (e) => {
      if (!showCrosshair) return;
      const x = e.nativeEvent.locationX;
      const idx = xToIndex(x);
      if (idx !== null) setTouchIdx(idx);
    },
    onPanResponderMove: (e) => {
      if (!showCrosshair) return;
      const x = e.nativeEvent.locationX;
      const idx = xToIndex(x);
      if (idx !== null) setTouchIdx(idx);
    },
    onPanResponderRelease: () => {
      setTimeout(() => setTouchIdx(null), 200);
    },
    onPanResponderTerminate: () => {
      setTouchIdx(null);
    },
  }), [showCrosshair, points]);

  const xToIndex = useCallback((x: number): number | null => {
    if (points.length < 2) return null;
    if (x < padding.left || x > padding.left + chartW) return null;
    const ratio = (x - padding.left) / chartW;
    const idx = Math.round(ratio * (sampled.length - 1));
    return Math.max(0, Math.min(idx, sampled.length - 1));
  }, [points, padding.left, chartW, sampled.length]);

  // ── Crosshair data ─────────────────────────────────────────────────

  const crosshair = useMemo(() => {
    if (touchIdx === null || !sampled[touchIdx] || !points[touchIdx]) return null;
    const d = sampled[touchIdx];
    const pt = points[touchIdx];
    const change = d.value - sampled[0].value;
    const changePct = sampled[0].value !== 0 ? (change / sampled[0].value) * 100 : 0;
    let timeLabel: string;
    try {
      const dt = new Date(d.time);
      timeLabel = isNaN(dt.getTime()) ? d.time : dt.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      timeLabel = d.time;
    }
    return { x: pt.x, y: pt.y, value: d.value, change, changePct, time: timeLabel, volume: d.volume };
  }, [touchIdx, sampled, points]);

  // Display values: when touching, show crosshair value; otherwise show latest
  const displayVal = crosshair ? crosshair.value : (sampled.length > 0 ? sampled[sampled.length - 1].value : 0);
  const firstVal = sampled.length > 0 ? sampled[0].value : 0;
  const dispChange = displayVal - firstVal;
  const dispChangePct = firstVal !== 0 ? (dispChange / firstVal) * 100 : 0;
  const isPositive = dispChange >= 0;

  useEffect(() => {
    if (!onCrosshairChange) return;
    if (crosshair) {
      onCrosshairChange({ value: crosshair.value, change: crosshair.change, changePct: crosshair.changePct, time: crosshair.time });
    } else {
      onCrosshairChange(null);
    }
  }, [crosshair, onCrosshairChange]);

  // ── Range selector handler ─────────────────────────────────────────

  const handleRange = useCallback((r: TimeRange) => {
    setSelectedRange(r);
    setTouchIdx(null);
    onRangeChange?.(r);
  }, [onRangeChange]);

  // ── Render ─────────────────────────────────────────────────────────

  if (!data || data.length < 2) {
    return (
      <View style={[st.wrap, { width, height }]}>
        <Svg width={width} height={height}>
          <SvgText x={width / 2} y={height / 2} fill={colors.text.muted} fontSize={12} textAnchor="middle">
            Waiting for data...
          </SvgText>
        </Svg>
      </View>
    );
  }

  const tooltipW = 80;
  const tooltipH = 30;

  return (
    <View style={{ width }}>
      {/* Price header (updates on touch) */}
      {showPriceHeader && (
        <View style={st.priceHeader}>
          <Text style={[st.priceValue, { color: colors.text.primary }]} numberOfLines={1} adjustsFontSizeToFit>
            ${displayVal.toFixed(2)}
          </Text>
          <View style={[st.changeBadge, { backgroundColor: isPositive ? colors.green.primary + '18' : colors.red.primary + '18' }]}>
            <Text style={[st.changeText, { color: isPositive ? colors.green.primary : colors.red.primary }]}>
              {isPositive ? '+' : ''}{dispChange.toFixed(2)}  ({isPositive ? '+' : ''}{dispChangePct.toFixed(2)}%)
            </Text>
          </View>
          {crosshair && (
            <Text style={[st.touchTime, { color: colors.text.muted }]}>{crosshair.time}</Text>
          )}
        </View>
      )}

      {/* Chart */}
      <RNAnimated.View style={{ width, height, opacity: fadeAnim }}>
        <View ref={svgRef} style={[st.wrap, { width, height }]} {...panResponder.panHandlers}>
          <Svg width={width} height={height}>
            <Defs>
              <LinearGradient id="areaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <Stop offset="0%" stopColor={lineColor} stopOpacity="0.25" />
                <Stop offset="50%" stopColor={lineColor} stopOpacity="0.08" />
                <Stop offset="100%" stopColor={lineColor} stopOpacity="0.0" />
              </LinearGradient>
            </Defs>

            {/* Grid lines — very subtle */}
            {showGrid && yLabels.map((yl, i) => (
              <Line key={`g${i}`} x1={padding.left} y1={yl.y} x2={padding.left + chartW} y2={yl.y}
                stroke={colors.border} strokeWidth={0.5} strokeDasharray="4,4" opacity={0.2} />
            ))}

            {/* Volume bars */}
            {showVolume && volumes.length > 1 && (() => {
              const volTop = padding.top + chartH + 4;
              const barW = Math.max(1, chartW / volumes.length - 0.5);
              return volumes.map((v, i) => {
                const barH = (v / maxVol) * volH;
                if (barH < 0.5) return null;
                const x = padding.left + (i / (volumes.length - 1)) * chartW - barW / 2;
                const isVolUp = i > 0 ? sampled[i].value >= sampled[i - 1].value : true;
                return (
                  <Rect key={`v${i}`} x={x} y={volTop + volH - barH} width={barW} height={barH}
                    rx={1} fill={isVolUp ? colors.green.primary : colors.red.primary} opacity={touchIdx === i ? 0.6 : 0.2} />
                );
              });
            })()}

            {/* Area fill */}
            <Path d={areaPath} fill="url(#areaGrad)" />

            {/* Price line */}
            <Path d={linePath} fill="none" stroke={lineColor} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />

            {/* Y-axis labels */}
            {showLabels && yLabels.map((yl, i) => (
              <SvgText key={`y${i}`} x={padding.left - 6} y={yl.y + 3.5} fill={colors.text.muted}
                fontSize={9} textAnchor="end" fontWeight="500" opacity={0.5}>
                {yl.label}
              </SvgText>
            ))}

            {/* X-axis labels */}
            {showLabels && xLabels.map((xl, i) => (
              <SvgText key={`x${i}`} x={xl.x} y={height - (showVolume ? 2 : 4)} fill={colors.text.muted}
                fontSize={8} textAnchor="middle" fontWeight="500" opacity={0.5}>
                {xl.label}
              </SvgText>
            ))}

            {/* Crosshair */}
            {crosshair && (
              <G>
                {/* Vertical line */}
                <Line x1={crosshair.x} y1={padding.top} x2={crosshair.x} y2={padding.top + chartH + (showVolume ? volH + 4 : 0)}
                  stroke={colors.text.muted} strokeWidth={0.7} strokeDasharray="3,3" opacity={0.35} />
                {/* Horizontal line */}
                <Line x1={padding.left} y1={crosshair.y} x2={padding.left + chartW} y2={crosshair.y}
                  stroke={colors.text.muted} strokeWidth={0.5} strokeDasharray="3,3" opacity={0.25} />
                {/* Glow dot */}
                <Circle cx={crosshair.x} cy={crosshair.y} r={8} fill={lineColor} opacity={0.15} />
                <Circle cx={crosshair.x} cy={crosshair.y} r={5} fill={lineColor} stroke={colors.bg.primary} strokeWidth={2} />
                <Circle cx={crosshair.x} cy={crosshair.y} r={2} fill={colors.bg.primary} />

                {/* Tooltip */}
                <Rect
                  x={Math.min(Math.max(crosshair.x - tooltipW / 2, padding.left), width - padding.right - tooltipW)}
                  y={Math.max(crosshair.y - tooltipH - 12, padding.top)}
                  width={tooltipW} height={tooltipH} rx={8}
                  fill={isDark ? 'rgba(255,255,255,0.95)' : 'rgba(0,0,0,0.88)'}
                />
                <SvgText
                  x={Math.min(Math.max(crosshair.x, padding.left + tooltipW / 2), width - padding.right - tooltipW / 2)}
                  y={Math.max(crosshair.y - tooltipH - 12, padding.top) + 13}
                  fill={isDark ? '#000' : '#fff'} fontSize={11} fontWeight="700" textAnchor="middle">
                  ${crosshair.value.toFixed(2)}
                </SvgText>
                <SvgText
                  x={Math.min(Math.max(crosshair.x, padding.left + tooltipW / 2), width - padding.right - tooltipW / 2)}
                  y={Math.max(crosshair.y - tooltipH - 12, padding.top) + 25}
                  fill={isDark ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.5)'} fontSize={8} fontWeight="500" textAnchor="middle">
                  {crosshair.volume ? `Vol: ${(crosshair.volume / 1000).toFixed(0)}K` : ''}
                </SvgText>
              </G>
            )}

            {/* End dot */}
            {points.length > 0 && !crosshair && (
              <G>
                <Circle cx={points[points.length - 1].x} cy={points[points.length - 1].y} r={4} fill={lineColor} opacity={0.3} />
                <Circle cx={points[points.length - 1].x} cy={points[points.length - 1].y} r={2.5} fill={lineColor} />
              </G>
            )}
          </Svg>
        </View>
      </RNAnimated.View>

      {/* Time range selector */}
      {showRangeSelector && (
        <View style={st.rangeRow}>
          {ranges.map((r) => {
            const active = r === selectedRange;
            return (
              <View key={r} style={{ flex: 1 }}>
                <View
                  style={[st.rangeBtn, {
                    backgroundColor: active ? (lineColor + '18') : 'transparent',
                  }]}
                  onTouchEnd={() => handleRange(r)}
                >
                  <Text style={[st.rangeTxt, {
                    color: active ? lineColor : colors.text.muted,
                    fontWeight: active ? '800' : '500',
                  }]}>{r}</Text>
                </View>
              </View>
            );
          })}
        </View>
      )}
    </View>
  );
}

// ─── Styles ─────────────────────────────────────────────────────────

const st = StyleSheet.create({
  wrap: { justifyContent: 'center', alignItems: 'center' },
  priceHeader: { flexDirection: 'row', alignItems: 'baseline', gap: 8, paddingHorizontal: 4, marginBottom: 4, flexWrap: 'wrap' },
  priceValue: { fontSize: 24, fontWeight: '800', fontVariant: ['tabular-nums'], letterSpacing: -0.5 },
  changeBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  changeText: { fontSize: 12, fontWeight: '700', fontVariant: ['tabular-nums'] },
  touchTime: { fontSize: 10, marginLeft: 'auto' },
  rangeRow: { flexDirection: 'row', marginTop: 8, gap: 4, paddingHorizontal: 4 },
  rangeBtn: { paddingVertical: 7, borderRadius: 8, alignItems: 'center' },
  rangeTxt: { fontSize: 12, letterSpacing: 0.3 },
});
