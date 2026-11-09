function clampRect(rect, bounds) {
  const { minW, minH, maxW, maxH } = bounds;
  const width = Math.max(minW, Math.min(maxW, Math.round(rect.width)));
  const height = Math.max(minH, Math.min(maxH, Math.round(rect.height)));
  const left = Math.max(0, Math.min(maxW - width, Math.round(rect.left)));
  const top = Math.max(0, Math.min(maxH - height, Math.round(rect.top)));
  return { left, top, width, height };
}
function normalizeGridRect(rect) {
  if (!Array.isArray(rect) || rect.length !== 4) return null;
  for (const v of rect) {
    if (typeof v !== "number" || !Number.isFinite(v) || v < 0 || v > 1) return null;
  }
  return rect.slice();
}
export {
  clampRect,
  normalizeGridRect
};
