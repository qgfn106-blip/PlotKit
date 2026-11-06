'use strict';
const test = require('node:test');
const assert = require('node:assert');
const u = require('../.tsbuild/plot3d.utils.js');

const I = new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
const near = (a, b, eps = 1e-6) => Math.abs(a - b) <= eps;

test('vec3 ops', () => {
  assert.deepStrictEqual(u.sub([1, 2, 3], [4, 5, 6]), [-3, -3, -3]);
  assert.strictEqual(u.dot([1, 2, 3], [4, 5, 6]), 32);
  assert.deepStrictEqual(u.cross([1, 0, 0], [0, 1, 0]), [0, 0, 1]);
  const n = u.norm([3, 4, 0]);
  assert.ok(near(n[0], 0.6) && near(n[1], 0.8) && near(n[2], 0));
});

test('mat4Mul / invert identity', () => {
  assert.deepStrictEqual(Array.from(u.mat4Mul(I, I)), Array.from(I));
  assert.deepStrictEqual(Array.from(u.invert(I)), Array.from(I));
  assert.strictEqual(u.invert(new Float32Array(16)), null);
});

test('applyMat4', () => {
  assert.deepStrictEqual(u.applyMat4(I, [1, 2, 3, 1]), [1, 2, 3, 1]);
});

test('perspective', () => {
  const m = u.perspective(Math.PI / 2, 1, 0.1, 100);
  assert.strictEqual(m.length, 16);
  assert.ok(near(m[0], 1) && near(m[5], 1));
  assert.ok(near(m[11], -1));
});

test('lookAt puts eye at origin looking -z', () => {
  const m = u.lookAt([0, 0, 1], [0, 0, 0], [0, 1, 0]);
  const p = u.applyMat4(m, [0, 0, 1, 1]);
  assert.ok(near(p[0], 0) && near(p[1], 0) && near(p[2], 0) && near(p[3], 1));
});

test('niceTicks', () => {
  assert.deepStrictEqual(u.niceTicks(0, 100, 5), [0, 20, 40, 60, 80, 100]);
  assert.deepStrictEqual(u.niceTicks(5, 5, 5), [5]);
});

test('clamp', () => {
  assert.strictEqual(u.clamp(5, 0, 3), 3);
  assert.strictEqual(u.clamp(-1, 0, 3), 0);
  assert.strictEqual(u.clamp(2, 0, 3), 2);
});

test('fmtTick', () => {
  assert.strictEqual(u.fmtTick(0), '0');
  assert.strictEqual(u.fmtTick(100000), '1.0e5');
  assert.strictEqual(u.fmtTick(1.2345), '1.23');
});

test('hexToRgba', () => {
  const r = u.hexToRgba('#ff0000');
  assert.ok(near(r[0], 1) && near(r[1], 0) && near(r[2], 0) && near(r[3], 1));
  const b = u.hexToRgba('bad', 0.5);
  assert.ok(near(b[0], 0.3) && near(b[1], 0.6) && near(b[2], 1) && near(b[3], 0.5));
});
