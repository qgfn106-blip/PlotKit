function kindChoices(meta, current) {
  const all = Array.isArray(meta) ? meta : [];
  const flat = [];
  const deep = [];
  for (const k of all) {
    if (!k || typeof k !== "object" || !k.kind) continue;
    const base = `${k.description || k.kind} \xB7 ${k.kind}`;
    if (k.dimension === 3) deep.push({ value: k.kind, label: `${base}\uFF083D\uFF09` });
    else flat.push({ value: k.kind, label: base });
  }
  const pairs = flat.concat(deep);
  if (current && !pairs.some((p) => p.value === current)) {
    pairs.unshift({ value: current, label: current });
  }
  return { flat, deep, pairs };
}
export {
  kindChoices
};
