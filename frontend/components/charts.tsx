"use client";
/**
 * Small SVG charts. Rules (dataviz skill): bars ≤ 24px with a 4px rounded data end, square at the
 * baseline; hairline solid gridlines; text in ink tokens, never series colour; per-mark hover
 * tooltip with a hit target bigger than the mark; a legend whenever there are ≥ 2 series.
 * Series palette validated with validate_palette.js (light): all checks PASS.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";

export const SERIES_COLORS = ["#2F5BD3", "#C1121F", "#1A8FB8", "#D9572B"] as const;

function useWidth<T extends HTMLElement>(fallback = 640) {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => e && setW(Math.max(280, Math.floor(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
}

function ticks(max: number, count = 4): number[] {
  return Array.from({ length: count + 1 }, (_, i) => (max / count) * i);
}

function tickLabel(v: number): string {
  if (v >= 10_000) return `${Math.round(v / 1000)}K`;
  return Number.isInteger(v) ? v.toLocaleString("en-IN") : v.toFixed(v < 1 ? 2 : 1);
}

/** Bar path: square at x0, 4px rounded at the data end. */
function barPath(x0: number, x1: number, y: number, h: number): string {
  const w = Math.max(0, x1 - x0);
  const r = Math.min(4, w, h / 2);
  return `M${x0},${y} H${x0 + w - r} Q${x0 + w},${y} ${x0 + w},${y + r} V${y + h - r} Q${x0 + w},${y + h} ${x0 + w - r},${y + h} H${x0} Z`;
}

interface Tip { x: number; y: number; content: ReactNode }

function Tooltip({ tip }: { tip: Tip | null }) {
  if (!tip) return null;
  return (
    <div role="tooltip" style={{
      position: "absolute", left: tip.x, top: tip.y, transform: "translate(-50%, calc(-100% - 10px))",
      background: "var(--ink)", color: "#fff", fontSize: 12, padding: "7px 10px", borderRadius: 6,
      pointerEvents: "none", whiteSpace: "nowrap", boxShadow: "var(--shadow-2)", zIndex: 5, lineHeight: 1.45,
    }}>{tip.content}</div>
  );
}

// ---------------------------------------------------------------- Horizontal bars (single series)
export interface BarDatum {
  key: string;
  label: string;
  sublabel?: string;
  value: number | null;
  /** marks the reference row with a text tag (identity is never colour-only) */
  isReference?: boolean;
  tooltip?: ReactNode;
}

export function HBarChart({ data, valueFormat = tickLabel, refLine, refLineLabel, ariaLabel, color = SERIES_COLORS[0] }: {
  data: BarDatum[];
  valueFormat?: (v: number) => string;
  refLine?: number;
  refLineLabel?: string;
  ariaLabel: string;
  color?: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<Tip | null>(null);
  const labelW = Math.min(170, Math.max(110, width * 0.26));
  const valueW = 64;
  const rowH = 34;
  const barH = 18;
  const top = refLine !== undefined ? 22 : 8;
  const axisH = 24;
  const plotW = Math.max(60, width - labelW - valueW);
  const maxV = niceMax(Math.max(refLine ?? 0, ...data.map((d) => d.value ?? 0)));
  const x = (v: number) => labelW + (v / maxV) * plotW;
  const height = top + data.length * rowH + axisH;

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <svg className="chart" width={width} height={height} role="img" aria-label={ariaLabel}>
        {ticks(maxV).map((t) => (
          <g key={t}>
            <line className="grid" x1={x(t)} x2={x(t)} y1={top - 4} y2={top + data.length * rowH} />
            <text x={x(t)} y={height - 6} textAnchor="middle">{tickLabel(t)}</text>
          </g>
        ))}
        <line className="axis" x1={labelW} x2={labelW} y1={top - 4} y2={top + data.length * rowH} />
        {data.map((d, i) => {
          const y = top + i * rowH;
          return (
            <g key={d.key}
              onMouseMove={(e) => {
                const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                setTip({ x: e.clientX - box.left, y: e.clientY - box.top, content: d.tooltip ?? `${d.label}: ${d.value === null ? "—" : valueFormat(d.value)}` });
              }}
              onMouseLeave={() => setTip(null)}>
              <rect x={0} y={y} width={width} height={rowH} fill="transparent" />
              <text x={labelW - 10} y={y + rowH / 2 - (d.sublabel ? 3 : -4)} textAnchor="end" className="label-strong">{d.label}</text>
              {d.sublabel && <text x={labelW - 10} y={y + rowH / 2 + 11} textAnchor="end" fontSize={11}>{d.sublabel}</text>}
              {d.value !== null && d.value > 0 && <path d={barPath(labelW, x(d.value), y + (rowH - barH) / 2, barH)} fill={color} />}
              <text x={d.value !== null ? x(d.value) + 6 : labelW + 6} y={y + rowH / 2 + 4} className="label-strong num">
                {d.value === null ? "—" : valueFormat(d.value)}{d.isReference ? "  · ref" : ""}
              </text>
            </g>
          );
        })}
        {refLine !== undefined && (
          <g>
            <line className="ref-line" x1={x(refLine)} x2={x(refLine)} y1={top - 6} y2={top + data.length * rowH} />
            {refLineLabel && <text x={x(refLine)} y={12} textAnchor="middle" fontSize={11}>{refLineLabel}</text>}
          </g>
        )}
      </svg>
      <Tooltip tip={tip} />
    </div>
  );
}

// ---------------------------------------------------------------- Dot + range plot (multi-series)
export interface RangeDatum {
  category: string;
  categorySub?: string;
  series: string;
  value: number | null;
  low?: number | null;
  high?: number | null;
  tooltip?: ReactNode;
}

/** One row per category; each series is a dot (value) with an optional low–high whisker (e.g. 95% CI). */
export function DotRangePlot({ data, series, ariaLabel, valueFormat = (v: number) => v.toFixed(2), refLine, refLineLabel }: {
  data: RangeDatum[];
  series: string[];
  ariaLabel: string;
  valueFormat?: (v: number) => string;
  refLine?: number;
  refLineLabel?: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<Tip | null>(null);
  const categories = Array.from(new Map(data.map((d) => [d.category, d.categorySub])).entries());
  const labelW = Math.min(150, Math.max(100, width * 0.22));
  const rightPad = 24;
  const laneH = 16;
  const rowH = Math.max(36, series.length * laneH + 14);
  const top = 22;
  const axisH = 24;
  const plotW = Math.max(60, width - labelW - rightPad);
  const all = data.flatMap((d) => [d.value, d.high, refLine]).filter((v): v is number => typeof v === "number");
  const maxV = niceMax(Math.max(0, ...all));
  const x = (v: number) => labelW + (v / maxV) * plotW;
  const height = top + categories.length * rowH + axisH;
  const colorOf = (s: string) => SERIES_COLORS[series.indexOf(s) % SERIES_COLORS.length];

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {series.length > 1 && (
        <div className="piece-legend" style={{ marginBottom: 8 }} aria-label="Legend">
          {series.map((s) => (
            <span key={s}><span className="swatch" style={{ background: colorOf(s), borderColor: colorOf(s), borderRadius: "50%" }} />{s}</span>
          ))}
        </div>
      )}
      <svg className="chart" width={width} height={height} role="img" aria-label={ariaLabel}>
        {ticks(maxV).map((t) => (
          <g key={t}>
            <line className="grid" x1={x(t)} x2={x(t)} y1={top - 4} y2={top + categories.length * rowH} />
            <text x={x(t)} y={height - 6} textAnchor="middle">{tickLabel(t)}</text>
          </g>
        ))}
        {refLine !== undefined && (
          <g>
            <line className="ref-line" x1={x(refLine)} x2={x(refLine)} y1={top - 8} y2={top + categories.length * rowH} />
            {refLineLabel && <text x={x(refLine)} y={11} textAnchor="middle" fontSize={11}>{refLineLabel}</text>}
          </g>
        )}
        {categories.map(([cat, sub], ci) => {
          const y0 = top + ci * rowH;
          return (
            <g key={cat}>
              {ci > 0 && <line className="grid" x1={0} x2={width} y1={y0} y2={y0} />}
              <text x={labelW - 12} y={y0 + rowH / 2 - (sub ? 2 : -4)} textAnchor="end" className="label-strong">{cat}</text>
              {sub && <text x={labelW - 12} y={y0 + rowH / 2 + 12} textAnchor="end" fontSize={11}>{sub}</text>}
              {series.map((s, si) => {
                const d = data.find((r) => r.category === cat && r.series === s);
                if (!d || d.value === null) return null;
                const cy = y0 + 7 + laneH / 2 + si * laneH + (rowH - 14 - series.length * laneH) / 2;
                const c = colorOf(s);
                return (
                  <g key={s}
                    onMouseMove={(e) => {
                      const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                      setTip({ x: e.clientX - box.left, y: e.clientY - box.top, content: d.tooltip ?? `${cat} · ${s}: ${valueFormat(d.value as number)}` });
                    }}
                    onMouseLeave={() => setTip(null)}>
                    <rect x={labelW} y={cy - laneH / 2} width={plotW} height={laneH} fill="transparent" />
                    {typeof d.low === "number" && typeof d.high === "number" && (
                      <line x1={x(d.low)} x2={x(d.high)} y1={cy} y2={cy} stroke={c} strokeWidth={2} strokeLinecap="round" opacity={0.45} />
                    )}
                    <circle cx={x(d.value)} cy={cy} r={5} fill={c} stroke="#fff" strokeWidth={2} />
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
      <Tooltip tip={tip} />
    </div>
  );
}
