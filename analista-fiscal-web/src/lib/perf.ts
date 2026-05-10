"use client";

interface PerfEntry {
  name: string;
  start: number;
  end: number;
  duration: number;
  detail?: Record<string, unknown>;
}

const RING_SIZE = 200;
const ring: PerfEntry[] = [];

function push(entry: PerfEntry) {
  ring.push(entry);
  if (ring.length > RING_SIZE) ring.shift();
  if (typeof window !== "undefined") {
    // Console agrupado para não poluir, expandido manualmente
    // eslint-disable-next-line no-console
    console.debug(
      `[perf] ${entry.name} ${entry.duration.toFixed(1)}ms`,
      entry.detail ?? ""
    );
  }
}

type StopFn = (detail?: Record<string, unknown>) => void;

export function perfMark(name: string): StopFn {
  if (typeof performance === "undefined") return () => {};
  const start = performance.now();
  return (detail?: Record<string, unknown>) => {
    const end = performance.now();
    push({ name, start, end, duration: end - start, detail });
  };
}

export function perfRecord(
  name: string,
  start: number,
  detail?: Record<string, unknown>
): void {
  if (typeof performance === "undefined") return;
  const end = performance.now();
  push({ name, start, end, duration: end - start, detail });
}

export function perfDump(): PerfEntry[] {
  return [...ring];
}

export function perfSummary(): Record<
  string,
  { count: number; min: number; max: number; avg: number; p95: number }
> {
  const grouped = new Map<string, number[]>();
  for (const e of ring) {
    const arr = grouped.get(e.name) ?? [];
    arr.push(e.duration);
    grouped.set(e.name, arr);
  }
  const out: Record<
    string,
    { count: number; min: number; max: number; avg: number; p95: number }
  > = {};
  for (const [name, values] of grouped) {
    const sorted = [...values].sort((a, b) => a - b);
    const sum = sorted.reduce((acc, v) => acc + v, 0);
    const p95Idx = Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95));
    out[name] = {
      count: sorted.length,
      min: sorted[0] ?? 0,
      max: sorted[sorted.length - 1] ?? 0,
      avg: sum / sorted.length,
      p95: sorted[p95Idx] ?? 0,
    };
  }
  return out;
}

if (typeof window !== "undefined") {
  (
    window as unknown as { __perf: { dump: () => PerfEntry[]; summary: () => unknown } }
  ).__perf = { dump: perfDump, summary: perfSummary };
}
