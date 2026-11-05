// Behavior-parity check for view3d.js (original HEAD) vs emitted typed build.
// Covers all exported non-WebGL surface: PALETTE, hexToRgba, parseFrame/Mesh/Volume/Particles,
// and View3D public API shape/prototype. GL drawing is not exercised (type-only changed).
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const EMITTED = path.join(ROOT, 'src/plotkit/static/view3d.js');

function loadPK3D(code, label) {
  const sandboxWindow = {};
  const factory = new Function('window', code + '\n;return window.PK3D;');
  const pk = factory(sandboxWindow);
  if (!pk) throw new Error(label + ': window.PK3D not set');
  return pk;
}

const origCode = execSync('git show HEAD:src/plotkit/static/view3d.js', { cwd: ROOT, encoding: 'utf8' });
const emitCode = fs.readFileSync(EMITTED, 'utf8');
const A = loadPK3D(origCode, 'orig');
const B = loadPK3D(emitCode, 'emitted');

let pass = 0, fail = 0;
function ok(name, cond, extra) { if (cond) { pass++; } else { fail++; console.log('[FAIL] ' + name + (extra ? ' :: ' + extra : '')); } }
function eqArr(a, b) { if (!a || !b || a.length !== b.length) return false; for (let i = 0; i < a.length; i++) { if (!(a[i] === b[i] || (Number.isNaN(a[i]) && Number.isNaN(b[i])))) return false; } return true; }
function eqJson(a, b) { return JSON.stringify(a) === JSON.stringify(b); }

// 1) surface keys
const ka = Object.keys(A).sort().join(',');
const kb = Object.keys(B).sort().join(',');
ok('export keys identical (' + ka + ')', ka === kb, ka + ' vs ' + kb);

// 2) PALETTE
ok('PALETTE equal', eqArr(A.PALETTE, B.PALETTE));

// 3) hexToRgba
for (const inp of [['#4ea1ff'], ['4ea1ff'], ['#ff0000', 0.5], ['zzz'], ['', 0.25], ['#ffffff']]) {
  ok('hexToRgba(' + JSON.stringify(inp) + ')', eqArr(A.hexToRgba.apply(null, inp), B.hexToRgba.apply(null, inp)));
}

// ---- buffer builders ----
function abFromBuffer(buf) { return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length); }
function buildFrame() {
  const meta = { name: 'layer', vmin: 0, vmax: 9 };
  const mj = Buffer.from(JSON.stringify(meta), 'utf8');
  const n = 2;
  const buf = Buffer.alloc(12 + mj.length + n * 12);
  buf.writeUInt32LE(0x504c4b31, 0); buf.writeUInt32LE(mj.length, 4); buf.writeUInt32LE(n, 8);
  mj.copy(buf, 12);
  const f = new Float32Array([1, 2, 3, 4, 5, 6]);
  Buffer.from(f.buffer, f.byteOffset, f.byteLength).copy(buf, 12 + mj.length);
  return abFromBuffer(buf);
}
function buildMesh() {
  const meta = { name: 'm' };
  const mj = Buffer.from(JSON.stringify(meta), 'utf8');
  const nvert = 2, ntri = 1;
  const buf = Buffer.alloc(16 + mj.length + nvert * 12 + nvert * 12 + ntri * 12);
  buf.writeUInt32LE(0x504c4b32, 0); buf.writeUInt32LE(mj.length, 4); buf.writeUInt32LE(nvert, 8); buf.writeUInt32LE(ntri, 12);
  mj.copy(buf, 16);
  let off = 16 + mj.length;
  const pos = new Float32Array([0, 0, 0, 1, 1, 1]); Buffer.from(pos.buffer, pos.byteOffset, pos.byteLength).copy(buf, off); off += nvert * 12;
  const nor = new Float32Array([0, 0, 1, 0, 0, 1]); Buffer.from(nor.buffer, nor.byteOffset, nor.byteLength).copy(buf, off); off += nvert * 12;
  const idx = new Uint32Array([0, 1, 0]); Buffer.from(idx.buffer, idx.byteOffset, idx.byteLength).copy(buf, off);
  return abFromBuffer(buf);
}
function buildVolume() {
  const meta = { nx: 2, ny: 2, nz: 2, x: [0, 1], y: [0, 1], z: [0, 1], vmin: 0, vmax: 1 };
  const mj = Buffer.from(JSON.stringify(meta), 'utf8');
  const buf = Buffer.alloc(12 + mj.length + 8 * 4);
  buf.writeUInt32LE(0x504c4b33, 0); buf.writeUInt32LE(mj.length, 4);
  mj.copy(buf, 12);
  const f = new Float32Array([0, .1, .2, .3, .4, .5, .6, .7]);
  Buffer.from(f.buffer, f.byteOffset, f.byteLength).copy(buf, 12 + mj.length);
  return abFromBuffer(buf);
}
function buildParticles() {
  const meta = { count: 2, x: [0, 1], y: [0, 1], z: [0, 1] };
  const mj = Buffer.from(JSON.stringify(meta), 'utf8');
  const n = 2;
  const buf = Buffer.alloc(12 + mj.length + n * 12 + n * 4);
  buf.writeUInt32LE(0x504c4b34, 0); buf.writeUInt32LE(mj.length, 4); buf.writeUInt32LE(n, 8);
  mj.copy(buf, 12);
  let off = 12 + mj.length;
  const xyz = new Float32Array([1, 2, 3, 4, 5, 6]); Buffer.from(xyz.buffer, xyz.byteOffset, xyz.byteLength).copy(buf, off); off += n * 12;
  const sc = new Float32Array([0.1, 0.9]); Buffer.from(sc.buffer, sc.byteOffset, sc.byteLength).copy(buf, off);
  return abFromBuffer(buf);
}

// 4) parseFrame
{
  const b = buildFrame();
  const a = A.parseFrame(b.slice(0)), c = B.parseFrame(b.slice(0));
  ok('parseFrame.meta', eqJson(a.meta, c.meta));
  ok('parseFrame.positions', eqArr(a.positions, c.positions));
}
// 5) parseMesh
{
  const b = buildMesh();
  const a = A.parseMesh(b.slice(0)), c = B.parseMesh(b.slice(0));
  ok('parseMesh.meta', eqJson(a.meta, c.meta));
  ok('parseMesh.positions', eqArr(a.positions, c.positions));
  ok('parseMesh.normals', eqArr(a.normals, c.normals));
  ok('parseMesh.indices', eqArr(a.indices, c.indices));
}
// 6) parseVolume
{
  const b = buildVolume();
  const a = A.parseVolume(b.slice(0)), c = B.parseVolume(b.slice(0));
  ok('parseVolume.meta', eqJson(a.meta, c.meta));
  ok('parseVolume.field', eqArr(a.field, c.field));
}
// 7) parseParticles
{
  const b = buildParticles();
  const a = A.parseParticles(b.slice(0)), c = B.parseParticles(b.slice(0));
  ok('parseParticles.meta', eqJson(a.meta, c.meta));
  ok('parseParticles.xyz', eqArr(a.xyz, c.xyz));
  ok('parseParticles.scalar', eqArr(a.scalar, c.scalar));
}
// 8) View3D API shape
ok('View3D is function (orig/emit)', typeof A.View3D === 'function' && typeof B.View3D === 'function');
const pa = Object.getOwnPropertyNames(A.View3D.prototype).sort().join(',');
const pb = Object.getOwnPropertyNames(B.View3D.prototype).sort().join(',');
ok('View3D.prototype methods identical', pa === pb, pa + ' vs ' + pb);

console.log('\n=== view3d parity: ' + pass + ' passed, ' + fail + ' failed ===');
process.exit(fail ? 1 : 0);
