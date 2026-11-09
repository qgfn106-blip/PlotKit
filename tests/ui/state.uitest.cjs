'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const MOD = pathToFileURL(path.join(__dirname, '..', '..', 'src', 'plotkit', 'static', 'ui', 'state.js')).href;

test('normalizeLayout: defaults + coerce malformed arrays', async () => {
  const m = await import(MOD);
  assert.deepEqual(m.normalizeLayout(null), { panelWidth: 380, sections: {}, expanded: [], groups: [] });
  const out = m.normalizeLayout({ panelWidth: 'wide', expanded: 'L0', groups: null, sections: [1, 2] });
  assert.equal(out.panelWidth, 380);
  assert.deepEqual(out.expanded, []);
  assert.deepEqual(out.groups, []);
  assert.deepEqual(out.sections, {});
});

test('normalizeLayout: clamps panel width, filters arrays, keeps extra group keys', async () => {
  const m = await import(MOD);
  const out = m.normalizeLayout({
    panelWidth: 9999,
    expanded: ['L0', 3, 'L2'],
    sections: { a: true },
    groups: [{ id: 'g1', name: 'G', open: true, layerIds: ['L0', 5], extra: 1 }],
  });
  assert.equal(out.panelWidth, 620);
  assert.deepEqual(out.expanded, ['L0', 'L2']);
  assert.equal(out.groups.length, 1);
  assert.deepEqual(out.groups[0].layerIds, ['L0']);
  assert.equal(out.groups[0].open, true);
  assert.equal(out.groups[0].extra, 1);
});

test('serialize/restore round-trip stable; clampPanelWidth bounds', async () => {
  const m = await import(MOD);
  const src = { panelWidth: 460, sections: { a: true }, expanded: ['L0', 'L2'], groups: [{ id: 'g1', name: 'G', open: true, layerIds: ['L0', 'L1'] }] };
  const text = m.serializeLayout(src);
  assert.deepEqual(m.restoreLayout(text), m.normalizeLayout(src));
  assert.deepEqual(m.restoreLayout('{not json'), m.normalizeLayout(null));
  assert.equal(m.clampPanelWidth(100, 300, 620), 300);
  assert.equal(m.clampPanelWidth(500, 300, 620), 500);
  assert.equal(m.clampPanelWidth(NaN), 380);
});
