/* NS 涡旋视图：体积 raymarch（轴对称场）+ GPU 粒子 + 轨迹束 + 叠层。
 * 场来自 /api/ns/*（真实速度场，无随机数据）。
 */
"use strict";

const NS = (() => {
  const VERT = `#version 300 es
  in vec2 aPos;
  void main() { gl_Position = vec4(aPos, 0.0, 1.0); }`;

  const FRAG_VOL = `#version 300 es
  precision highp float;
  uniform vec2 uRes;
  uniform mat4 uInvVP;
  uniform vec3 uCam;
  uniform sampler2D uField;   // (r,z) -> [log10 Omega, |u|]
  uniform vec2 uExtent;       // r_max, z_max
  uniform float uStep;
  uniform float uDensity;
  uniform vec2 uRange;
  uniform float uAxis;
  uniform vec3 uCore, uMid, uOuter;
  out vec4 fragColor;

  vec3 ramp(float s) {
    // 0 → 外圈蓝紫, 0.55 → 青绿, 1 → 橙黄核心
    vec3 c = mix(uOuter, uMid, smoothstep(0.05, 0.55, s));
    return mix(c, uCore, smoothstep(0.55, 1.0, s));
  }

  float sampleField(vec3 p, out float speed) {
    float r = length(p.xy) / uExtent.x;
    float z = (p.z / uExtent.y) * 0.5 + 0.5;
    if (r > 1.0 || z < 0.0 || z > 1.0) { speed = 0.0; return 0.0; }
    vec4 t = texture(uField, vec2(r, z));
    speed = t.g;
    return t.r;
  }

  void main() {
    vec2 ndc = gl_FragCoord.xy / uRes * 2.0 - 1.0;
    vec4 pNear = uInvVP * vec4(ndc, -1.0, 1.0);
    vec4 pFar  = uInvVP * vec4(ndc,  1.0, 1.0);
    vec3 o = pNear.xyz / pNear.w;
    vec3 d = normalize(pFar.xyz / pFar.w - o);

    // 与圆柱包围盒求交：|xy| <= r_max, |z| <= z_max
    float t0 = 0.0, t1 = 60.0;
    float a = dot(d.xy, d.xy);
    float b = 2.0 * dot(o.xy, d.xy);
    float c = dot(o.xy, o.xy) - uExtent.x * uExtent.x;
    if (a > 1e-8) {
      float disc = b * b - 4.0 * a * c;
      if (disc < 0.0) { fragColor = vec4(0.0); return; }
      float sq = sqrt(disc);
      t0 = max(t0, (-b - sq) / (2.0 * a));
      t1 = min(t1, (-b + sq) / (2.0 * a));
    }
    if (abs(d.z) > 1e-8) {
      float za = (-uExtent.y - o.z) / d.z;
      float zb = ( uExtent.y - o.z) / d.z;
      t0 = max(t0, min(za, zb));
      t1 = min(t1, max(za, zb));
    }
    if (t1 <= t0) { fragColor = vec4(0.0); return; }

    float dt = max(uStep, (t1 - t0) / 220.0);
    vec3 acc = vec3(0.0);
    float alpha = 0.0;
    for (float s = t0; s < t1; s += dt) {
      vec3 p = o + d * s;
      float speed;
      float v = sampleField(p, speed);
      if (v > -20.0) {
        float omega = pow(10.0, v);
        float x = clamp(omega / max(uAxis, 1e-6), 0.0, 1.0);
        float dens = pow(x, 5.0) * uDensity;
        float speedN = clamp(speed / 6.0, 0.0, 1.0);
        vec3 col = ramp(x) * (0.55 + 0.9 * speedN);
        float radial = smoothstep(1.0, 0.72, length(p.xz) / uExtent.x);
        float axial = smoothstep(1.0, 0.85, abs(p.y) / uExtent.y);
        float a = clamp(dens * dt * 6.0, 0.0, 0.5) * radial * axial;
        acc += (1.0 - alpha) * a * col;
        alpha += (1.0 - alpha) * a;
        if (alpha > 0.985) break;
      }
    }
    // 轻微辉光：把亮度做一次软压缩
    acc = acc / (1.0 + 0.35 * acc);
    fragColor = vec4(acc, alpha);
  }`;

  const VERT_PT = `#version 300 es
  in vec3 aPos;
  in float aAge;
  uniform mat4 uVP;
  uniform float uPointSize;
  out float vAge;
  void main() {
    vec4 c = uVP * vec4(aPos, 1.0);
    gl_Position = c;
    gl_PointSize = uPointSize * (1.0 - 0.35 * aAge) * (3.0 / max(c.w, 0.2));
    vAge = aAge;
  }`;

  const FRAG_PT = `#version 300 es
  precision highp float;
  in float vAge;
  uniform vec3 uColor;
  out vec4 fragColor;
  void main() {
    vec2 q = gl_PointCoord * 2.0 - 1.0;
    float d = dot(q, q);
    if (d > 1.0) discard;
    float a = (1.0 - d) * (1.0 - vAge) * 0.9;
    fragColor = vec4(uColor * (1.0 - 0.3 * vAge), a);
  }`;

  const VERT_LN = `#version 300 es
  in vec3 aPos;
  in float aT;
  uniform mat4 uVP;
  uniform float uHead;
  out float vA;
  void main() {
    gl_Position = uVP * vec4(aPos, 1.0);
    vA = clamp((uHead - aT) * 6.0, 0.0, 1.0) * 0.55;
  }`;

  const FRAG_LN = `#version 300 es
  precision highp float;
  in float vA;
  uniform vec3 uColor;
  out vec4 fragColor;
  void main() { fragColor = vec4(uColor, vA); }`;

  const mat4 = {
    mul(a, b) {
      const o = new Float32Array(16);
      for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) {
        let s = 0;
        for (let k = 0; k < 4; k++) s += a[k * 4 + j] * b[i * 4 + k];
        o[i * 4 + j] = s;
      }
      return o;
    },
    perspective(fovy, aspect, near, far) {
      const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
      return new Float32Array([f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0]);
    },
    lookAt(eye, target, up) {
      const z = norm(sub(eye, target)), x = norm(cross(up, z)), y = cross(z, x);
      return new Float32Array([
        x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0,
        -dot(x, eye), -dot(y, eye), -dot(z, eye), 1]);
    },
    invert(m) {
      const inv = new Float32Array(16);
      const a = m;
      const b00 = a[0] * a[5] - a[1] * a[4], b01 = a[0] * a[6] - a[2] * a[4];
      const b02 = a[0] * a[7] - a[3] * a[4], b03 = a[1] * a[6] - a[2] * a[5];
      const b04 = a[1] * a[7] - a[3] * a[5], b05 = a[2] * a[7] - a[3] * a[6];
      const b06 = a[8] * a[13] - a[9] * a[12], b07 = a[8] * a[14] - a[10] * a[12];
      const b08 = a[8] * a[15] - a[11] * a[12], b09 = a[9] * a[14] - a[10] * a[13];
      const b10 = a[9] * a[15] - a[11] * a[13], b11 = a[10] * a[15] - a[11] * a[14];
      let det = b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06;
      if (!det) return null;
      det = 1 / det;
      inv[0] = (a[5] * b11 - a[6] * b10 + a[7] * b09) * det;
      inv[1] = (a[2] * b10 - a[1] * b11 - a[3] * b09) * det;
      inv[2] = (a[13] * b05 - a[14] * b04 + a[15] * b03) * det;
      inv[3] = (a[10] * b04 - a[9] * b05 - a[11] * b03) * det;
      inv[4] = (a[6] * b08 - a[4] * b11 - a[7] * b07) * det;
      inv[5] = (a[0] * b11 - a[2] * b08 + a[3] * b07) * det;
      inv[6] = (a[14] * b02 - a[12] * b05 - a[15] * b01) * det;
      inv[7] = (a[8] * b05 - a[10] * b02 + a[11] * b01) * det;
      inv[8] = (a[4] * b10 - a[5] * b08 + a[7] * b06) * det;
      inv[9] = (a[1] * b08 - a[0] * b10 - a[3] * b06) * det;
      inv[10] = (a[12] * b04 - a[13] * b02 + a[15] * b00) * det;
      inv[11] = (a[9] * b02 - a[8] * b04 - a[11] * b00) * det;
      inv[12] = (a[5] * b07 - a[4] * b09 - a[6] * b06) * det;
      inv[13] = (a[0] * b09 - a[1] * b07 + a[2] * b06) * det;
      inv[14] = (a[13] * b01 - a[12] * b03 - a[14] * b00) * det;
      inv[15] = (a[8] * b03 - a[9] * b01 + a[10] * b00) * det;
      return inv;
    },
  };
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const norm = (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };

  function compile(gl, type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }

  function program(gl, vs, fs) {
    const p = gl.createProgram();
    gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, vs));
    gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    return p;
  }

  class NSView {
    constructor(canvas, opts = {}) {
      this.canvas = canvas;
      this.gl = canvas.getContext("webgl2", { antialias: false, alpha: false, preserveDrawingBuffer: true });
      if (!this.gl) throw new Error("需要 WebGL2");
      const gl = this.gl;

      this.quad = program(gl, VERT, FRAG_VOL);
      this.points = program(gl, VERT_PT, FRAG_PT);
      this.lines = program(gl, VERT_LN, FRAG_LN);

      this.quadBuf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, this.quadBuf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);

      this.tex = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, this.tex);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

      this.cam = { yaw: -0.6, pitch: 0.12, dist: 2.9, target: [0, 0, 0] };
      this.extent = [0.35, 1.2];
      this.particles = null;
      this.trails = null;
      this.settings = { density: 1.0, pointSize: 6.0, showParticles: true, showTrails: true };
      this.stats = { fps: 0 };
      this._frames = 0;
      this._t0 = performance.now();

      this._bindInput();
      this._resize();
      window.addEventListener("resize", () => this._resize());
      requestAnimationFrame(() => this._loop());
    }

    _resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = this.canvas.clientWidth || 800, h = this.canvas.clientHeight || 600;
      this.canvas.width = Math.round(w * dpr);
      this.canvas.height = Math.round(h * dpr);
    }

    _bindInput() {
      const c = this.canvas;
      let drag = null;
      c.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY }; c.setPointerCapture(e.pointerId); });
      c.addEventListener("pointerup", () => { drag = null; });
      c.addEventListener("pointermove", (e) => {
        if (!drag) return;
        this.cam.yaw += (e.clientX - drag.x) * 0.008;
        this.cam.pitch = Math.max(-1.4, Math.min(1.4, this.cam.pitch + (e.clientY - drag.y) * 0.006));
        drag = { x: e.clientX, y: e.clientY };
      });
      c.addEventListener("wheel", (e) => {
        e.preventDefault();
        this.cam.dist = Math.max(0.5, Math.min(12, this.cam.dist * (1 + Math.sign(e.deltaY) * 0.08)));
      }, { passive: false });
    }

    setField(meta, data) {
      const gl = this.gl;
      const nz = meta.n_z, nr = meta.n_r;
      const scalar = data.subarray(0, nz * nr);
      const speed = data.subarray(nz * nr, nz * nr * 2);
      const packed = new Float32Array(nz * nr * 2);
      for (let i = 0; i < nz * nr; i++) { packed[i * 2] = scalar[i]; packed[i * 2 + 1] = speed[i]; }
      gl.bindTexture(gl.TEXTURE_2D, this.tex);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RG16F, nr, nz, 0, gl.RG, gl.FLOAT, packed);
      this.extent = [meta.r_max, meta.z_max];
      this.fieldMeta = meta;
      this.vmin = meta.vmin; this.vmax = meta.vmax; this.omegaAxis = meta.omega_p995;
    }

    setVelocity(meta, data) {
      this.vel = { n: meta.n, extent: meta.extent, zExtent: meta.z_extent, data };
    }

    seedParticles(count = 24000) {
      const rng = mulberry32(12345);
      const pos = new Float32Array(count * 3);
      const age = new Float32Array(count);
      for (let i = 0; i < count; i++) {
        const th = rng() * Math.PI * 2;
        const rr = 0.02 + 0.12 * Math.sqrt(rng());
        pos[i * 3] = rr * Math.cos(th);
        pos[i * 3 + 1] = rr * Math.sin(th);
        pos[i * 3 + 2] = (rng() * 2 - 1) * 0.75;
        age[i] = rng();
      }
      const gl = this.gl;
      const vbo = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
      gl.bufferData(gl.ARRAY_BUFFER, pos, gl.DYNAMIC_DRAW);
      const abo = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, abo);
      gl.bufferData(gl.ARRAY_BUFFER, age, gl.STATIC_DRAW);
      this.particles = { pos, age, vbo, abo, count };
    }

    setTrails(meta, data) {
      const { steps, seeds } = meta;
      const gl = this.gl;
      const vbo = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
      const tbo = gl.createBuffer();
      const tt = new Float32Array(steps * seeds);
      for (let s = 0; s < steps; s++) for (let k = 0; k < seeds; k++) tt[s * seeds + k] = s / (steps - 1);
      gl.bindBuffer(gl.ARRAY_BUFFER, tbo);
      gl.bufferData(gl.ARRAY_BUFFER, tt, gl.STATIC_DRAW);
      this.trails = { steps, seeds, vbo, tbo, head: 1.0 };
    }

    _advect(dt) {
      const v = this.vel, P = this.particles;
      if (!v || !P) return;
      const n = v.n, ext = v.extent, zext = v.zExtent, D = v.data;
      const step = 0.012 * Math.max(dt, 0.4);
      const sample = (x, y, z, out) => {
        const fx = (x / ext * 0.5 + 0.5) * (n - 1);
        const fy = (y / ext * 0.5 + 0.5) * (n - 1);
        const fz = (z / zext * 0.5 + 0.5) * (n - 1);
        if (fx < 0 || fy < 0 || fz < 0 || fx > n - 1 || fy > n - 1 || fz > n - 1) { out[0] = out[1] = out[2] = 0; return false; }
        const i0 = Math.floor(fx), j0 = Math.floor(fy), k0 = Math.floor(fz);
        const i1 = Math.min(i0 + 1, n - 1), j1 = Math.min(j0 + 1, n - 1), k1 = Math.min(k0 + 1, n - 1);
        const tx = fx - i0, ty = fy - j0, tz = fz - k0;
        const idx = (i, j, k) => (i + j * n + k * n * n) * 3;
        for (let c = 0; c < 3; c++) {
          const c00 = D[idx(i0, j0, k0) + c] * (1 - tx) + D[idx(i1, j0, k0) + c] * tx;
          const c10 = D[idx(i0, j1, k0) + c] * (1 - tx) + D[idx(i1, j1, k0) + c] * tx;
          const c01 = D[idx(i0, j0, k1) + c] * (1 - tx) + D[idx(i1, j0, k1) + c] * tx;
          const c11 = D[idx(i0, j1, k1) + c] * (1 - tx) + D[idx(i1, j1, k1) + c] * tx;
          const c0 = c00 * (1 - ty) + c10 * ty, c1 = c01 * (1 - ty) + c11 * ty;
          out[c] = c0 * (1 - tz) + c1 * tz;
        }
        return true;
      };
      const k1 = [0, 0, 0], k2 = [0, 0, 0];
      const pos = P.pos, age = P.age;
      for (let i = 0; i < P.count; i++) {
        const o = i * 3;
        let x = pos[o], y = pos[o + 1], z = pos[o + 2];
        sample(x, y, z, k1);
        sample(x + 0.5 * step * k1[0], y + 0.5 * step * k1[1], z + 0.5 * step * k1[2], k2);
        x += step * k2[0]; y += step * k2[1]; z += step * k2[2];
        const rr = Math.hypot(x, y);
        if (!isFinite(x) || rr > ext * 1.6 || Math.abs(z) > zext * 1.15) {
          const th = Math.random() * Math.PI * 2, rad = 0.02 + 0.12 * Math.sqrt(Math.random());
          x = rad * Math.cos(th); y = rad * Math.sin(th); z = (Math.random() * 2 - 1) * 0.75;
          age[i] = 1.0;
        }
        age[i] = Math.min(1.0, age[i] + 0.004);
        pos[o] = x; pos[o + 1] = y; pos[o + 2] = z;
      }
      const gl = this.gl;
      gl.bindBuffer(gl.ARRAY_BUFFER, P.vbo);
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, pos);
      gl.bindBuffer(gl.ARRAY_BUFFER, P.abo);
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, age);
    }

    _loop() {
      const now = performance.now();
      const dt = Math.min(0.05, (now - (this._last || now)) / 1000);
      this._last = now;
      this._frames++;
      if (now - this._t0 > 500) {
        this.stats.fps = Math.round(this._frames * 1000 / (now - this._t0));
        this._frames = 0; this._t0 = now;
        if (this.onStats) this.onStats(this.stats);
      }
      if (this.settings.showParticles) this._advect(dt);
      this._draw();
      requestAnimationFrame(() => this._loop());
    }

    _draw() {
      const gl = this.gl;
      const w = this.canvas.width, h = this.canvas.height;
      gl.viewport(0, 0, w, h);
      gl.clearColor(0.016, 0.02, 0.03, 1.0);
      gl.clear(gl.COLOR_BUFFER_BIT);

      const eye = [
        this.cam.target[0] + this.cam.dist * Math.cos(this.cam.pitch) * Math.cos(this.cam.yaw),
        this.cam.target[1] + this.cam.dist * Math.cos(this.cam.pitch) * Math.sin(this.cam.yaw),
        this.cam.target[2] + this.cam.dist * Math.sin(this.cam.pitch),
      ];
      const proj = mat4.perspective(0.8, w / h, 0.05, 100);
      const view = mat4.lookAt(eye, this.cam.target, [0, 0, 1]);
      const vp = mat4.mul(proj, view);
      const inv = mat4.invert(vp);

      // 1) 体积
      gl.useProgram(this.quad);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.quadBuf);
      const aPos = gl.getAttribLocation(this.quad, "aPos");
      gl.enableVertexAttribArray(aPos);
      gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
      gl.uniform2f(gl.getUniformLocation(this.quad, "uRes"), w, h);
      gl.uniformMatrix4fv(gl.getUniformLocation(this.quad, "uInvVP"), false, inv);
      gl.uniform3fv(gl.getUniformLocation(this.quad, "uCam"), eye);
      gl.uniform2f(gl.getUniformLocation(this.quad, "uExtent"), this.extent[0], this.extent[1]);
      gl.uniform1f(gl.getUniformLocation(this.quad, "uStep"), 0.006);
      gl.uniform1f(gl.getUniformLocation(this.quad, "uDensity"), this.settings.density);
      gl.uniform2f(gl.getUniformLocation(this.quad, "uRange"), this.vmin ?? -4.0, this.vmax ?? 0.0);
      gl.uniform1f(gl.getUniformLocation(this.quad, "uAxis"), this.omegaAxis ?? 1.0);
      gl.uniform2f(gl.getUniformLocation(this.quad, "uExtent"), this.extent?.[0] ?? 0.5, this.extent?.[1] ?? 1.2);
      gl.uniform3f(gl.getUniformLocation(this.quad, "uCore"), 1.0, 0.72, 0.25);
      gl.uniform3f(gl.getUniformLocation(this.quad, "uMid"), 0.16, 0.72, 0.66);
      gl.uniform3f(gl.getUniformLocation(this.quad, "uOuter"), 0.22, 0.26, 0.75);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.tex);
      gl.uniform1i(gl.getUniformLocation(this.quad, "uField"), 0);
      gl.disable(gl.BLEND);
      gl.drawArrays(gl.TRIANGLES, 0, 3);

      // 2) 轨迹束（加法混合）
      if (this.settings.showTrails && this.trails) {
        const T = this.trails;
        gl.useProgram(this.lines);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.bindBuffer(gl.ARRAY_BUFFER, T.vbo);
        const la = gl.getAttribLocation(this.lines, "aPos");
        gl.enableVertexAttribArray(la);
        gl.vertexAttribPointer(la, 3, gl.FLOAT, false, 0, 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, T.tbo);
        const lt = gl.getAttribLocation(this.lines, "aT");
        gl.enableVertexAttribArray(lt);
        gl.vertexAttribPointer(lt, 1, gl.FLOAT, false, 0, 0);
        gl.uniformMatrix4fv(gl.getUniformLocation(this.lines, "uVP"), false, vp);
        gl.uniform1f(gl.getUniformLocation(this.lines, "uHead"), T.head);
        gl.uniform3f(gl.getUniformLocation(this.lines, "uColor"), 1.0, 0.55, 0.18);
        gl.drawArrays(gl.LINES, 0, T.steps * T.seeds);
      }

      // 3) 粒子（加法混合）
      if (this.settings.showParticles && this.particles) {
        const P = this.particles;
        gl.useProgram(this.points);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
        gl.bindBuffer(gl.ARRAY_BUFFER, P.vbo);
        const pa = gl.getAttribLocation(this.points, "aPos");
        gl.enableVertexAttribArray(pa);
        gl.vertexAttribPointer(pa, 3, gl.FLOAT, false, 0, 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, P.abo);
        const pg = gl.getAttribLocation(this.points, "aAge");
        gl.enableVertexAttribArray(pg);
        gl.vertexAttribPointer(pg, 1, gl.FLOAT, false, 0, 0);
        gl.uniformMatrix4fv(gl.getUniformLocation(this.points, "uVP"), false, vp);
        gl.uniform1f(gl.getUniformLocation(this.points, "uPointSize"), this.settings.pointSize * (h / 900));
        gl.uniform3f(gl.getUniformLocation(this.points, "uColor"), 1.0, 0.62, 0.22);
        gl.drawArrays(gl.POINTS, 0, P.count);
      }
      gl.disable(gl.BLEND);
      this._lastVP = vp;
    }
  }

  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      let t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  return { NSView };
})();
