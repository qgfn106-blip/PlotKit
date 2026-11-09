/* Pure UI-state helpers: layout normalization / serialize & restore.
 * Kept free of DOM so it can be exercised by tests/ui/state.uitest.cjs. */
export interface NormalizedGroup {
  id: string;
  name: string;
  open: boolean;
  layerIds: string[];
  hidden?: boolean;
  [key: string]: unknown;
}

export interface NormalizedLayout {
  panelWidth: number;
  sections: Record<string, unknown>;
  expanded: string[];
  groups: NormalizedGroup[];
}

export const DEFAULT_LAYOUT: NormalizedLayout = {
  panelWidth: 380,
  sections: {},
  expanded: [],
  groups: [],
};

/** Clamp a panel width to [min, max], rounding; non-finite/non-positive -> fallback. */
export function clampPanelWidth(width: unknown, min = 300, max = 620, fallback = 380): number {
  const n = Number(width);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return Math.max(min, Math.min(max, Math.round(n)));
}

function normalizeGroup(g: unknown): NormalizedGroup {
  const src: Record<string, unknown> = g && typeof g === "object" ? { ...(g as Record<string, unknown>) } : {};
  const out: NormalizedGroup = {
    ...(src as object),
    id: String(src.id != null ? src.id : ""),
    name: String(src.name != null ? src.name : ""),
    open: Boolean(src.open),
    layerIds: Array.isArray(src.layerIds) ? (src.layerIds as unknown[]).filter((x) => typeof x === "string") as string[] : [],
  };
  if ("hidden" in src) out.hidden = Boolean(src.hidden);
  return out;
}

/** Normalize an arbitrary layout payload (missing / malformed -> defaults). Does not mutate input. */
export function normalizeLayout(raw: unknown): NormalizedLayout {
  const src: Record<string, unknown> = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const sections =
    src.sections && typeof src.sections === "object" && !Array.isArray(src.sections)
      ? { ...(src.sections as Record<string, unknown>) }
      : {};
  const expanded = Array.isArray(src.expanded) ? (src.expanded as unknown[]).filter((x) => typeof x === "string") as string[] : [];
  const groups = Array.isArray(src.groups)
    ? (src.groups as unknown[]).filter((g) => g && typeof g === "object").map(normalizeGroup)
    : [];
  return { panelWidth: clampPanelWidth(src.panelWidth), sections, expanded, groups };
}

/** Deterministic serialize of a layout (normalized first). */
export function serializeLayout(layout: unknown): string {
  return JSON.stringify(normalizeLayout(layout));
}

/** Restore a layout from a JSON string; invalid JSON -> defaults. */
export function restoreLayout(text: unknown): NormalizedLayout {
  if (typeof text !== "string") return normalizeLayout(null);
  try {
    return normalizeLayout(JSON.parse(text));
  } catch {
    return normalizeLayout(null);
  }
}
