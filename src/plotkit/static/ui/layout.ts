/* Pure layout-rect helpers: pixel rect clamping and 0..1 grid-rect validation.
 * Kept free of DOM so it can be exercised by tests/ui/layout.uitest.cjs. */
export interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface RectBounds {
  minW: number;
  minH: number;
  maxW: number;
  maxH: number;
}

/** Clamp a pixel rect into bounds: width/height within [min,max], position within the wrap. */
export function clampRect(rect: Rect, bounds: RectBounds): Rect {
  const { minW, minH, maxW, maxH } = bounds;
  const width = Math.max(minW, Math.min(maxW, Math.round(rect.width)));
  const height = Math.max(minH, Math.min(maxH, Math.round(rect.height)));
  const left = Math.max(0, Math.min(maxW - width, Math.round(rect.left)));
  const top = Math.max(0, Math.min(maxH - height, Math.round(rect.top)));
  return { left, top, width, height };
}

/** Validate a v1 grid rect: exactly 4 finite numbers all in 0..1. Returns a copy or null. */
export function normalizeGridRect(rect: unknown): number[] | null {
  if (!Array.isArray(rect) || rect.length !== 4) return null;
  for (const v of rect) {
    if (typeof v !== "number" || !Number.isFinite(v) || v < 0 || v > 1) return null;
  }
  return (rect as number[]).slice();
}
