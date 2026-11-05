// 行为等价比对工具：原始 render2d.js（迁移前）vs tsc 编译产物。
// 用法：
//   git show <baseline-ref>:src/plotkit/static/render2d.js > /tmp/orig.js
//   node scripts/verify_render2d_parity.js /tmp/orig.js src/plotkit/static/render2d.js
// 判定：两者在录制型 canvas 上执行 Plot2D.render + pick，canvas 操作序列完全一致即 PASS。
// Behavioral parity check: original render2d.js vs tsc-emitted render2d.js
// Runs both in a vm with a recording canvas context, calls Plot2D.render + pick,
// and compares the exact sequence of canvas operations.
const fs = require("fs");
const vm = require("vm");

function makeCtx(ops, canvas) {
  const state = {};
  return new Proxy(state, {
    get(t, p) {
      if (p in t) return t[p];
      if (p === "canvas") return canvas;
      return (...a) => {
        ops.push([p, a.map((x) => (typeof x === "number" ? x : typeof x === "string" ? x : x === null ? null : x === undefined ? undefined : "[obj]"))]);
        if (p === "measureText") return { width: 7 * String(a[0] || "").length };
        if (p === "createLinearGradient" || p === "createRadialGradient" || p === "createPattern")
          return { addColorStop() {} };
        if (p === "getImageData") return { data: new Uint8ClampedArray(4) };
        if (p === "createImageData") return { data: new Uint8ClampedArray(4), width: 1, height: 1 };
        return undefined;
      };
    },
    set(t, p, v) {
      t[p] = v;
      ops.push(["SET", p, typeof v === "number" ? v : String(v)]);
      return true;
    },
  });
}

function buildSpec() {
  return {
    figure: { title: "Parity Test", xlabel: "x", ylabel: "y" },
    layers: [
      { kind: "line", data: { x: "x", y: "y" }, style: { color: "#4fc3f7", width: 2, mode: "line+marker" } },
      { kind: "step", data: { x: "x", y: "y" } },
      { kind: "points", data: { x: "x", y: "y2" }, marker: { symbol: "square", size: 6 } },
      { kind: "bar", data: { x: "x", y: "y2" }, style: { color: "#ff8a65" } },
      { kind: "area", data: { x: "x", y: "y" }, style: { opacity: 0.4 } },
      { kind: "ecdf", data: { x: "x", y: "y" } },
      { kind: "stem", data: { x: "x", y: "y" } },
      { kind: "stairs", data: { x: "x", y: "y" } },
      { kind: "barh", data: { x: "x", y: "y2" } },
      { kind: "violin", data: { x: "x", y: "y" } },
      { kind: "boxplot", data: { x: "x", y: "y" } },
    ],
  };
}

function makeStore() {
  const x = new Float32Array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  const y = new Float32Array([1, 4, 2, 5, 3, 6, 2, 7, 4, 8]);
  const y2 = new Float32Array([2, 3, 1, 4, 2, 5, 3, 6, 5, 7]);
  const data = { x: { values: x, total: x.length }, y: { values: y, total: y.length }, y2: { values: y2, total: y2.length } };
  return { get: (name) => data[name] || null };
}

function run(code, label) {
  const ops = [];
  const canvas = { clientWidth: 640, clientHeight: 420, width: 0, height: 0, style: {} };
  const ctx = makeCtx(ops, canvas);
  canvas.getContext = () => ctx;
  const windowObj = { devicePixelRatio: 1 };
  const sandbox = { window: windowObj, document: { documentElement: {} }, Math, Float32Array, Map, Set, Array, Object, String, Number, isFinite, parseInt, parseFloat, Infinity, NaN, console };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox, { filename: label });
  const Plot2D = windowObj.Plot2D || sandbox.window.Plot2D;
  if (!Plot2D) throw new Error("Plot2D not defined (" + label + ")");
  const spec = buildSpec();
  const store = makeStore();
  const res = Plot2D.render(canvas, spec, store, { tokens: { paper: "#0f172a", plot: "#111827", text: "#e2e8f0", muted: "#94a3b8", grid: "#1f2937", accent: "#4fc3f7" }, t: Infinity, tMin: null, overrides: {}, dpr: 1 });
  // pick a couple of points
  let pickRes = null;
  try { pickRes = Plot2D.pick(res, 320, 210); } catch (e) { pickRes = "PICK_ERR:" + e.message; }
  let pickRes2 = null;
  try { pickRes2 = Plot2D.pick(res, 50, 50); } catch (e) { pickRes2 = "PICK_ERR:" + e.message; }
  return { ops, resKeys: res ? Object.keys(res) : null, pickRes, pickRes2, axes: res && res.axes ? res.axes.length : null, pickables: res && res.pickables ? res.pickables.length : null };
}

const orig = fs.readFileSync(process.argv[2], "utf8");
const emitted = fs.readFileSync(process.argv[3], "utf8");

let a, b;
try { a = run(orig, "orig"); } catch (e) { console.log("ORIG THREW:", e.message); process.exit(2); }
try { b = run(emitted, "emitted"); } catch (e) { console.log("EMITTED THREW:", e.message); process.exit(2); }

console.log("orig ops:", a.ops.length, " emitted ops:", b.ops.length);
console.log("orig resKeys:", JSON.stringify(a.resKeys), " axes:", a.axes, " pickables:", a.pickables);
console.log("emitted resKeys:", JSON.stringify(b.resKeys), " axes:", b.axes, " pickables:", b.pickables);
console.log("pick1 orig:", JSON.stringify(a.pickRes), " emitted:", JSON.stringify(b.pickRes));
console.log("pick2 orig:", JSON.stringify(a.pickRes2), " emitted:", JSON.stringify(b.pickRes2));

const sa = JSON.stringify(a.ops);
const sb = JSON.stringify(b.ops);
if (sa === sb) {
  console.log("PARITY: IDENTICAL canvas op sequence ✅");
} else {
  console.log("PARITY: DIFFERENCES ❌");
  const n = Math.min(a.ops.length, b.ops.length);
  let shown = 0;
  for (let i = 0; i < n && shown < 12; i++) {
    const x = JSON.stringify(a.ops[i]), y = JSON.stringify(b.ops[i]);
    if (x !== y) { console.log("  @" + i + " orig=" + x + " emit=" + y); shown++; }
  }
  if (a.ops.length !== b.ops.length) console.log("  length differs: " + a.ops.length + " vs " + b.ops.length);
}
