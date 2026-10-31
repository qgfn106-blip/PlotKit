/* PlotKit 3D 视图（P15）：WebGL2 直接画，拖动只改矩阵，不经过服务端重绘。
 *
 * 数据来源：GET /api/xyz?x=&y=&z= → magic(4)+meta_len(4)+n(4)+json+float32(x,y,z)。
 * 交互：左键拖动旋转、滚轮缩放、Shift+左键平移。HUD 显示 fps 与点数。
 */
(function () {
  "use strict";

  const VS = `#version 300 es
  in vec3 aPos;
  in vec3 aNormal;
  uniform mat4 uMVP;
  uniform float uPointSize;
  out vec3 vNormal;
  void main() {
    gl_Position = uMVP * vec4(aPos, 1.0);
    gl_PointSize = uPointSize;
    vNormal = aNormal;
  }`;

  const FS = `#version 300 es
  precision mediump float;
  uniform vec4 uColor;
  uniform float uLit;       // 1 = 曲面着色（Lambert），0 = 纯色
  in vec3 vNormal;
  out vec4 outColor;
  void main() {
    if (uLit < 0.5) { outColor = uColor; return; }
    vec3 n = normalize(vNormal);
    vec3 L = normalize(vec3(0.45, -0.75, 0.9));   // 固定斜上方光，与视角无关
    float diff = max(dot(n, L), 0.0);
    float rim = 0.30 + 0.70 * diff;               // 30% 环境光，背面不至于全黑
    outColor = vec4(uColor.rgb * rim, uColor.a);
  }`;

  function mat4Mul(a, b) {
    const out = new Float32Array(16);
    for (let i = 0; i < 4; i++) {
      for (let j = 0; j < 4; j++) {
        let s = 0;
        for (let k = 0; k < 4; k++) s += a[k * 4 + j] * b[i * 4 + k];
        out[i * 4 + j] = s;
      }
    }
    return out;
  }

  function perspective(fovy, aspect, near, far) {
    const f = 1 / Math.tan(fovy / 2);
    const nf = 1 / (near - far);
    return new Float32Array([
      f / aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (far + near) * nf, -1,
      0, 0, 2 * far * near * nf, 0,
    ]);
  }

  function lookAt(eye, center, up) {
    const z = norm(sub(eye, center));
    const x = norm(cross(up, z));
    const y = cross(z, x);
    return new Float32Array([
      x[0], y[0], z[0], 0,
      x[1], y[1], z[1], 0,
      x[2], y[2], z[2], 0,
      -dot(x, eye), -dot(y, eye), -dot(z, eye), 1,
    ]);
  }

  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
  const norm = (a) => {
    const n = Math.hypot(a[0], a[1], a[2]) || 1;
    return [a[0] / n, a[1] / n, a[2] / n];
  };

  const PALETTE = ["#4ea1ff", "#ff8f5a", "#5ad19a", "#e6c15a", "#c98bff", "#ff6f91"];

  class View3D {
    constructor(canvas) {
      this.canvas = canvas;
      const gl = canvas.getContext("webgl2", {
        antialias: true, alpha: false, preserveDrawingBuffer: true,
      });
      if (!gl) throw new Error("当前环境不支持 WebGL2");
      this.gl = gl;
      this.layers = [];
      this.yaw = -0.9;
      this.pitch = 0.42;
      this.dist = 3.2;
      this.target = [0, 0, 0];
      this.center = [0, 0, 0];
      this.radius = 1;
      this.fps = 0;
      this._frames = 0;
      this._last = performance.now();
      this._build();
      this._bindInput();
      this._resize();
      requestAnimationFrame(() => this._loop());
    }

    _build() {
      const gl = this.gl;
      const compile = (type, src) => {
        const sh = gl.createShader(type);
        gl.shaderSource(sh, src);
        gl.compileShader(sh);
        if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
          throw new Error(gl.getShaderInfoLog(sh) || "shader 编译失败");
        }
        return sh;
      };
      const prog = gl.createProgram();
      gl.attachShader(prog, compile(gl.VERTEX_SHADER, VS));
      gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FS));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        throw new Error(gl.getProgramInfoLog(prog) || "程序链接失败");
      }
      this.prog = prog;
      this.aPos = gl.getAttribLocation(prog, "aPos");
      this.aNormal = gl.getAttribLocation(prog, "aNormal");
      this.uLit = gl.getUniformLocation(prog, "uLit");
      this.uMVP = gl.getUniformLocation(prog, "uMVP");
      this.uColor = gl.getUniformLocation(prog, "uColor");
      this.uPointSize = gl.getUniformLocation(prog, "uPointSize");
      gl.enable(gl.DEPTH_TEST);
      gl.clearColor(0.043, 0.055, 0.075, 1);
    }

    _resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.max(1, Math.round(this.canvas.clientWidth * dpr));
      const h = Math.max(1, Math.round(this.canvas.clientHeight * dpr));
      if (this.canvas.width !== w || this.canvas.height !== h) {
        this.canvas.width = w;
        this.canvas.height = h;
      }
    }

    _bindInput() {
      const c = this.canvas;
      let drag = null;
      c.addEventListener("pointerdown", (ev) => {
        drag = { x: ev.clientX, y: ev.clientY, shift: ev.shiftKey || ev.button === 1 };
        try { c.setPointerCapture(ev.pointerId); } catch (_) { /* 合成事件 */ }
      });
      c.addEventListener("pointermove", (ev) => {
        if (!drag) return;
        const dx = ev.clientX - drag.x;
        const dy = ev.clientY - drag.y;
        drag.x = ev.clientX;
        drag.y = ev.clientY;
        if (drag.shift) {
          const k = this.dist * 0.0016;
          const right = [Math.cos(this.yaw), -Math.sin(this.yaw), 0];
          const up = [0, 0, 1];
          this.target[0] -= (dx * right[0]) * k;
          this.target[1] -= (dx * right[1]) * k;
          this.target[2] += dy * k * up[2];
        } else {
          this.yaw -= dx * 0.006;
          this.pitch = Math.max(-1.45, Math.min(1.45, this.pitch + dy * 0.006));
        }
      });
      const stop = () => { drag = null; };
      c.addEventListener("pointerup", stop);
      c.addEventListener("pointercancel", stop);
      c.addEventListener("wheel", (ev) => {
        ev.preventDefault();
        this.dist = Math.max(this.radius * 0.15, Math.min(this.radius * 40, this.dist * Math.exp(ev.deltaY * 0.0012)));
      }, { passive: false });
      c.addEventListener("dblclick", () => this.resetView());
    }

    resetView() {
      this.yaw = -0.9;
      this.pitch = 0.42;
      this.target = this.center.slice();
      this.dist = this.radius * 3.2;
    }

    /** 用已经解好的 {name, color, mode, positions:Float32Array} 列表替换场景。 */
    setLayers(layers) {
      const gl = this.gl;
      for (const item of this.layers) {
        gl.deleteBuffer(item.buffer);
        if (item.normalBuffer) gl.deleteBuffer(item.normalBuffer);
        if (item.indexBuffer) gl.deleteBuffer(item.indexBuffer);
      }
      this.layers = [];
      const lo = [Infinity, Infinity, Infinity];
      const hi = [-Infinity, -Infinity, -Infinity];
      for (const item of layers) {
        const pos = item.positions;
        for (let i = 0; i < pos.length; i += 3) {
          for (let k = 0; k < 3; k++) {
            lo[k] = Math.min(lo[k], pos[i + k]);
            hi[k] = Math.max(hi[k], pos[i + k]);
          }
        }
        const buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(gl.ARRAY_BUFFER, pos, gl.STATIC_DRAW);
        const entry = { ...item, buffer, count: pos.length / 3 };
        if (item.normals) {
          entry.normalBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ARRAY_BUFFER, entry.normalBuffer);
          gl.bufferData(gl.ARRAY_BUFFER, item.normals, gl.STATIC_DRAW);
        }
        if (item.indices) {
          entry.indexBuffer = gl.createBuffer();
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, entry.indexBuffer);
          gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, item.indices, gl.STATIC_DRAW);
          entry.indexCount = item.indices.length;
        }
        this.layers.push(entry);
      }
      if (this.layers.length) {
        this.center = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2];
        this.radius = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], 1e-6) / 2;
        this.target = this.center.slice();
        this.dist = this.radius * 3.2;
      }
      return this.layers.reduce((n, l) => n + l.count, 0);
    }

    _loop() {
      this._resize();
      const gl = this.gl;
      const { width: w, height: h } = this.canvas;
      gl.viewport(0, 0, w, h);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.useProgram(this.prog);

      const cp = Math.cos(this.pitch);
      const eye = [
        this.target[0] + this.dist * cp * Math.cos(this.yaw),
        this.target[1] + this.dist * cp * Math.sin(this.yaw),
        this.target[2] + this.dist * Math.sin(this.pitch),
      ];
      const proj = perspective(Math.PI / 4, w / h, this.dist * 0.01, this.dist * 20);
      const view = lookAt(eye, this.target, [0, 0, 1]);
      const mvp = mat4Mul(proj, view);
      gl.uniformMatrix4fv(this.uMVP, false, mvp);

      for (const layer of this.layers) {
        gl.bindBuffer(gl.ARRAY_BUFFER, layer.buffer);
        gl.enableVertexAttribArray(this.aPos);
        gl.vertexAttribPointer(this.aPos, 3, gl.FLOAT, false, 0, 0);
        gl.uniform4fv(this.uColor, layer.color);
        if (layer.mode === "mesh" && layer.indexBuffer) {
          gl.uniform1f(this.uLit, 1.0);
          gl.uniform1f(this.uPointSize, 1);
          gl.bindBuffer(gl.ARRAY_BUFFER, layer.normalBuffer);
          gl.enableVertexAttribArray(this.aNormal);
          gl.vertexAttribPointer(this.aNormal, 3, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ARRAY_BUFFER, layer.buffer);
          gl.vertexAttribPointer(this.aPos, 3, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, layer.indexBuffer);
          gl.drawElements(gl.TRIANGLES, layer.indexCount, gl.UNSIGNED_INT, 0);
          gl.disableVertexAttribArray(this.aNormal);
          gl.uniform1f(this.uLit, 0.0);
          continue;
        }
        gl.uniform1f(this.uLit, 0.0);
        if (layer.mode === "lines") {
          gl.uniform1f(this.uPointSize, 1);
          gl.drawArrays(gl.LINE_STRIP, 0, layer.count);
        } else {
          gl.uniform1f(this.uPointSize, layer.size || 2.0 * (window.devicePixelRatio || 1));
          gl.drawArrays(gl.POINTS, 0, layer.count);
        }
      }

      this._frames += 1;
      const now = performance.now();
      if (now - this._last > 500) {
        this.fps = (this._frames * 1000) / (now - this._last);
        this._frames = 0;
        this._last = now;
        if (this.onStats) this.onStats({ fps: this.fps, points: this.layers.reduce((n, l) => n + l.count, 0) });
      }
      requestAnimationFrame(() => this._loop());
    }
  }

  function hexToRgba(hex, alpha = 1) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
    if (!m) return new Float32Array([0.3, 0.6, 1, alpha]);
    const v = parseInt(m[1], 16);
    return new Float32Array([((v >> 16) & 255) / 255, ((v >> 8) & 255) / 255, (v & 255) / 255, alpha]);
  }

  /** 解析 /api/xyz 的二进制帧。 */
  function parseFrame(buffer) {
    const view = new DataView(buffer);
    const metaLen = view.getUint32(4, true);
    const n = view.getUint32(8, true);
    const meta = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 12, metaLen)));
    const offset = 12 + metaLen;
    const positions = new Float32Array(buffer.slice(offset, offset + n * 12));
    return { meta, positions };
  }

  /** 解析 /api/mesh 的二进制帧：顶点 + 法线 + uint32 索引。 */
  function parseMesh(buffer) {
    const view = new DataView(buffer);
    const metaLen = view.getUint32(4, true);
    const nvert = view.getUint32(8, true);
    const ntri = view.getUint32(12, true);
    const meta = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 16, metaLen)));
    const base = 16 + metaLen;
    const positions = new Float32Array(buffer.slice(base, base + nvert * 12));
    const nOff = base + nvert * 12;
    const normals = new Float32Array(buffer.slice(nOff, nOff + nvert * 12));
    const iOff = nOff + nvert * 12;
    const indices = new Uint32Array(buffer.slice(iOff, iOff + ntri * 12));
    return { meta, positions, normals, indices };
  }

  window.PK3D = { View3D, hexToRgba, parseFrame, parseMesh, PALETTE };
})();
