'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const MOD = pathToFileURL(path.join(__dirname, '..', '..', 'src', 'plotkit', 'static', 'ui', 'layout.js')).href;

test('clampRect: clamps size to bounds and position into wrap', async () => {
  const m = await import(MOD);
  const r = m.clampRect({ left: -5, top: 9999, width: 9999, height: 10 }, { minW: 260, minH: 180, maxW: 1000, maxH: 600 });
  assert.deepEqual(r, { left: 0, top: 420, width: 1000, height: 180 });
  const r2 = m.clampRect({ left: 10, top: 20, width: 100, height: 100 }, { minW: 260, minH: 180, maxW: 1000, maxH: 600 });
  assert.deepEqual(r2, { left: 10, top: 20, width: 260, height: 180 });
});

test('normalizeGridRect: only 4 finite numbers within 0..1 accepted, returns copy', async () => {
  const m = await import(MOD);
  const ok = [0, 0, 0.5, 1];
  const out = m.normalizeGridRect(ok);
  assert.deepEqual(out, ok);
  assert.notEqual(out, ok);
  assert.equal(m.normalizeGridRect([0, 0, 0.5, 1, 0.2]), null);
  assert.equal(m.normalizeGridRect([-0.1, 0, 1.2, 1]), null);
  assert.equal(m.normalizeGridRect(['x', 0, 1, 1]), null);
  assert.equal(m.normalizeGridRect([NaN, 0, 1, 1]), null);
});
