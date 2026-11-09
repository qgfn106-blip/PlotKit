/* Pure inspector helpers: schema-driven kind option generation.
 * Kept free of DOM so it can be exercised by tests/ui/inspector.uitest.cjs. */
export interface KindMeta {
  kind?: string;
  description?: string;
  dimension?: number;
  [key: string]: unknown;
}

export interface KindChoice {
  value: string;
  label: string;
}

export interface KindChoices {
  flat: KindChoice[];
  deep: KindChoice[];
  pairs: KindChoice[];
}

/** Build the 图型 (kind) choices from catalog metadata; ensure the current kind is present. */
export function kindChoices(meta: unknown, current?: string): KindChoices {
  const all: KindMeta[] = Array.isArray(meta) ? (meta as KindMeta[]) : [];
  const flat: KindChoice[] = [];
  const deep: KindChoice[] = [];
  for (const k of all) {
    if (!k || typeof k !== "object" || !k.kind) continue;
    const base = `${k.description || k.kind} · ${k.kind}`;
    if (k.dimension === 3) deep.push({ value: k.kind, label: `${base}（3D）` });
    else flat.push({ value: k.kind, label: base });
  }
  const pairs = flat.concat(deep);
  if (current && !pairs.some((p) => p.value === current)) {
    pairs.unshift({ value: current, label: current });
  }
  return { flat, deep, pairs };
}
