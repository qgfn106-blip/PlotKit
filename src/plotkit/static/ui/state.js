const DEFAULT_LAYOUT = {
  panelWidth: 380,
  sections: {},
  expanded: [],
  groups: []
};
function clampPanelWidth(width, min = 300, max = 620, fallback = 380) {
  const n = Number(width);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return Math.max(min, Math.min(max, Math.round(n)));
}
function normalizeGroup(g) {
  const src = g && typeof g === "object" ? { ...g } : {};
  const out = {
    ...src,
    id: String(src.id != null ? src.id : ""),
    name: String(src.name != null ? src.name : ""),
    open: Boolean(src.open),
    layerIds: Array.isArray(src.layerIds) ? src.layerIds.filter((x) => typeof x === "string") : []
  };
  if ("hidden" in src) out.hidden = Boolean(src.hidden);
  return out;
}
function normalizeLayout(raw) {
  const src = raw && typeof raw === "object" ? raw : {};
  const sections = src.sections && typeof src.sections === "object" && !Array.isArray(src.sections) ? { ...src.sections } : {};
  const expanded = Array.isArray(src.expanded) ? src.expanded.filter((x) => typeof x === "string") : [];
  const groups = Array.isArray(src.groups) ? src.groups.filter((g) => g && typeof g === "object").map(normalizeGroup) : [];
  return { panelWidth: clampPanelWidth(src.panelWidth), sections, expanded, groups };
}
function serializeLayout(layout) {
  return JSON.stringify(normalizeLayout(layout));
}
function restoreLayout(text) {
  if (typeof text !== "string") return normalizeLayout(null);
  try {
    return normalizeLayout(JSON.parse(text));
  } catch {
    return normalizeLayout(null);
  }
}
export {
  DEFAULT_LAYOUT,
  clampPanelWidth,
  normalizeLayout,
  restoreLayout,
  serializeLayout
};
