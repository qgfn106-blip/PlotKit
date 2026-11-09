'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const MOD = pathToFileURL(path.join(__dirname, '..', '..', 'src', 'plotkit', 'static', 'ui', 'inspector.js')).href;

test('kindChoices: splits 2D/3D, builds labels, keeps order', async () => {
  const m = await import(MOD);
  const meta = [
    { kind: 'line', description: '折线', dimension: 2 },
    { kind: 'surface', description: '曲面', dimension: 3 },
  ];
  const r = m.kindChoices(meta, 'line');
  assert.deepEqual(r.flat, [{ value: 'line', label: '折线 · line' }]);
  assert.deepEqual(r.deep, [{ value: 'surface', label: '曲面 · surface（3D）' }]);
  assert.deepEqual(r.pairs.map((p) => p.value), ['line', 'surface']);
});

test('kindChoices: ensures current kind present, tolerates junk entries', async () => {
  const m = await import(MOD);
  const r = m.kindChoices([{ kind: 'line' }, null, {}, { kind: 'bar' }], 'custom');
  assert.deepEqual(r.pairs.map((p) => p.value), ['custom', 'line', 'bar']);
  assert.deepEqual(m.kindChoices(null, 'x').pairs, [{ value: 'x', label: 'x' }]);
});
