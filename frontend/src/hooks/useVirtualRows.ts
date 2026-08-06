/**
 * useVirtualRows — fixed-height row windowing for the app's data tables
 * (Phase 5).
 *
 * WHY THIS AND NOT @tanstack/react-virtual: the plan named TanStack Virtual,
 * but this machine's pnpm store was pruned by a snap refresh, so the existing
 * node_modules is hard-linked to a store that no longer exists and NO new
 * dependency can be installed without a full ~900-package reinstall. This
 * hook is deliberately kept behind one module boundary with a
 * library-shaped result ({ startIndex, endIndex, padTop, padBottom }) so
 * swapping in TanStack Virtual later is a one-file change and no call site
 * moves. See docs/phases/phase-05-ui-overhaul.md.
 *
 * Contract:
 * - Rows are a FIXED height (`rowHeight`). Every table using this renders
 *   uniform rows; variable heights would need measurement and are out of scope.
 * - Below `threshold` rows, windowing is OFF and every row renders. That
 *   matches .claude/rules/ui.md ("≥200 rows or live-updating → virtualize")
 *   and keeps small tables (and their tests) behaving exactly as before.
 * - The viewport is an explicit scroll container (`overflow-y-auto` + a
 *   bounded height), NOT the window — that is also what makes a sticky
 *   table header work.
 * - State updates only when the visible WINDOW changes, never per scrolled
 *   pixel; scroll handling is rAF-throttled and the listener is passive.
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

export interface VirtualRowsOptions {
  /** Total row count in the dataset. */
  count: number;
  /** Height of one rendered row, in px. Must match the real row height. */
  rowHeight: number;
  /** Extra rows rendered above and below the viewport (default 8). */
  overscan?: number;
  /** Row count below which windowing is disabled entirely (default 200). */
  threshold?: number;
}

export interface VirtualRowsResult {
  /** False when the dataset is under `threshold` — all rows render. */
  virtualized: boolean;
  /** First row index to render (inclusive). */
  startIndex: number;
  /** Last row index to render (EXCLUSIVE) — use `slice(startIndex, endIndex)`. */
  endIndex: number;
  /** Spacer height standing in for the rows above the window. */
  padTop: number;
  /** Spacer height standing in for the rows below the window. */
  padBottom: number;
}

/**
 * Assumed viewport height before the container has been measured. Without
 * this, the first paint would render only the overscan (a near-blank table
 * for one frame); with it, the first paint is a full screen of rows and
 * measurement only corrects the edges.
 */
const ASSUMED_VIEWPORT_PX = 640;

const DEFAULT_OVERSCAN = 8;
const DEFAULT_THRESHOLD = 200;

export function useVirtualRows(
  viewportRef: React.RefObject<HTMLElement | null>,
  { count, rowHeight, overscan = DEFAULT_OVERSCAN, threshold = DEFAULT_THRESHOLD }: VirtualRowsOptions,
): VirtualRowsResult {
  const virtualized = count >= threshold && rowHeight > 0;

  const [range, setRange] = useState<{ start: number; end: number }>({ start: 0, end: count });
  const viewportHeightRef = useRef(ASSUMED_VIEWPORT_PX);
  const rafRef = useRef<number | null>(null);

  const recompute = useCallback(() => {
    const el = viewportRef.current;
    const scrollTop = el?.scrollTop ?? 0;
    const height = viewportHeightRef.current || ASSUMED_VIEWPORT_PX;

    const first = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
    const visible = Math.ceil(height / rowHeight);
    const last = Math.min(count, first + visible + overscan * 2);

    // Only re-render when the window actually moved.
    setRange((prev) => (prev.start === first && prev.end === last ? prev : { start: first, end: last }));
  }, [count, overscan, rowHeight, viewportRef]);

  // Measure the container, then keep it measured. useLayoutEffect so the
  // first committed paint already uses the real height where available.
  useLayoutEffect(() => {
    if (!virtualized) return;
    const el = viewportRef.current;
    if (el) viewportHeightRef.current = el.clientHeight || ASSUMED_VIEWPORT_PX;
    recompute();

    // jsdom (and older browsers) may not implement ResizeObserver — the
    // hook must still window correctly without it.
    if (el && typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(() => {
        viewportHeightRef.current = el.clientHeight || ASSUMED_VIEWPORT_PX;
        recompute();
      });
      ro.observe(el);
      return () => ro.disconnect();
    }
  }, [virtualized, recompute, viewportRef]);

  useEffect(() => {
    if (!virtualized) return;
    const el = viewportRef.current;
    if (!el) return;

    const onScroll = () => {
      // Coalesce a burst of scroll events into one recompute per frame.
      if (rafRef.current !== null) return;
      const run = () => {
        rafRef.current = null;
        recompute();
      };
      rafRef.current =
        typeof requestAnimationFrame === "function"
          ? requestAnimationFrame(run)
          : (setTimeout(run, 16) as unknown as number);
    };

    el.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      el.removeEventListener("scroll", onScroll);
      if (rafRef.current !== null) {
        if (typeof cancelAnimationFrame === "function") cancelAnimationFrame(rafRef.current);
        else clearTimeout(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [virtualized, recompute, viewportRef]);

  if (!virtualized) {
    return { virtualized: false, startIndex: 0, endIndex: count, padTop: 0, padBottom: 0 };
  }

  // `count` can shrink between a recompute and this render (a filter change
  // arrives before the effect reruns) — clamp so we never slice past the end
  // or emit a negative spacer.
  const startIndex = Math.min(range.start, Math.max(0, count - 1));
  const endIndex = Math.min(range.end, count);
  return {
    virtualized: true,
    startIndex,
    endIndex,
    padTop: startIndex * rowHeight,
    padBottom: Math.max(0, (count - endIndex) * rowHeight),
  };
}
