'use strict';
const test = require('node:test');
const assert = require('node:assert');
const u = require('../.tsbuild/plot2d.utils.js');

test('niceStep: 1/2/5×10^k', () => {
  assert.strictEqual(u.niceStep(100, 10), 20);
  assert.strictEqual(u.niceStep(1, 5), 0.5);
  assert.strictEqual(u.niceStep(0, 1), 1);
});

test('ticksLinear', () => {
  const r = u.ticksLinear(0, 100, 5);
  assert.deepStrictEqual(r.ticks, [0, 50, 100]);
  assert.strictEqual(r.step, 50);
});

test('ticksLog', () => {
  assert.deepStrictEqual(u.ticksLog(1, 100, 10).ticks, [1, 10, 100]);
  assert.deepStrictEqual(u.ticksLog(-1, 0, 5).ticks, []);
});

test('fmtNum', () => {
  assert.strictEqual(u.fmtNum(0), '0');
  assert.strictEqual(u.fmtNum(12345), '12345');
  assert.strictEqual(u.fmtNum(0.00001), '1e-5');
});

test('extent', () => {
  assert.deepStrictEqual(u.extent([1, 2, 3]), [1, 3]);
  assert.strictEqual(u.extent([]), null);
  assert.deepStrictEqual(u.extent([5, 5]), [4.5, 5.5]);
});

test('padRange', () => {
  assert.deepStrictEqual(u.padRange([0, 10], 0.1), [-1, 11]);
  assert.deepStrictEqual(u.padRange(null, 0.1), [0, 1]);
});

test('union', () => {
  assert.deepStrictEqual(u.union(null, [1, 2]), [1, 2]);
  assert.deepStrictEqual(u.union([0, 1], [2, 3]), [0, 3]);
});

test('quantile', () => {
  assert.strictEqual(u.quantile([1, 2, 3, 4], 0.5), 2.5);
  assert.strictEqual(u.quantile([], 0.5), 0);
});

test('hexAlpha', () => {
  assert.strictEqual(u.hexAlpha('#4fc3f7', 0.5), 'rgba(79,195,247,0.5)');
  assert.strictEqual(u.hexAlpha('bad', 0.3), 'rgba(79,195,247,0.3)');
});

test('colorRamp', () => {
  assert.strictEqual(u.colorRamp(5, 0, 10), 'rgb(224,243,248)');
  assert.strictEqual(u.colorRamp(0, 0, 10), 'rgb(49,54,149)');
  assert.strictEqual(u.colorRamp(10, 0, 10), 'rgb(215,48,39)');
});
