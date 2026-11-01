"""给 view3d.js 加 volume（raymarch）与 particles（柔光点精灵）两个 pass。"""
import pathlib

p = pathlib.Path("src/plotkit/static/view3d.js")
s = p.read_text(encoding="utf-8")

NEW = r'''
    // ---------- 体积渲染（raymarch）：三维标量场，浏览器里直接画 ----------
    _initVolume() {
      const gl = this.gl;
      if (this.volProg) return;
      const vs = `#version 300 es
      in vec2 aNdc;
      out vec2 vNdc;
      void main() { vNdc = aNdc; gl_Position = vec4(aNdc, 0.0, 1.0); }`;
      const fs = `#version 300 es
      precision highp float;
      precision highp sampler3D;
      in vec2 vNdc;
      uniform sampler3D uField;   // R32F，x 变化最快
      uniform vec3 uLo, uHi, uEye;
      uniform mat4 uInvVP;
      uniform vec3 uVmin, uVmax;  // vmin/vmax 打包成两枚 vec3 的 .x
      uniform float uSteps;
      uniform float uGamma;
      uniform float uGain;
      out vec4 frag;
      vec3 ramp(float t) {
        // 简化 magma：黑 → 紫 → 橙 → 白
        vec3 c0 = vec3(0.02, 0.01, 0.08);
        vec3 c1 = vec3(0.35, 0.06, 0.42);
        vec3 c2 = vec3(0.95, 0.45, 0.10);
        vec3 c3 = vec3(1.00, 0.96, 0.82);
        if (t < 0.33) return mix(c0, c1, t / 0.33);
        if (t < 0.70) return mix(c1, c2, (t - 0.33) / 0.37);
        return mix(c2, c3, (t - 0.70) / 0.30);
      }
      float sampleField(vec3 p) {
        vec3 uvw = (p - uLo) / max(uHi - uLo, vec3(1e-6));
        if (any(lessThan(uvw, vec3(0.0))) || any(greaterThan(uvw, vec3(1.0)))) return 0.0;
        ivec3 dim = textureSize(uField, 0);
        vec3 c = uvw * vec3(dim - 1);
        ivec3 i0 = ivec3(floor(c));
        ivec3 i1 = min(i0 + 1, dim - 1);
        vec3 f = c - vec3(i0);
        float v000 = texelFetch(uField, ivec3(i0.x, i0.y, i0.z), 0).r;
        float v100 = texelFetch(uField, ivec3(i1.x, i0.y, i0.z), 0).r;
        float v010 = texelFetch(uField, ivec3(i0.x, i1.y, i0.z), 0).r;
        float v110 = texelFetch(uField, ivec3(i1.x, i1.y, i0.z), 0).r;
        float v001 = texelFetch(uField, ivec3(i0.x, i0.y, i1.z), 0).r;
        float v101 = texelFetch(uField, ivec3(i1.x, i0.y, i1.z), 0).r;
        float v011 = texelFetch(uField, ivec3(i0.x, i1.y, i1.z), 0).r;
        float v111 = texelFetch(uField, ivec3(i1.x, i1.y, i1.z), 0).r;
        float a = mix(mix(v000, v100, f.x), mix(v010, v110, f.x), f.y);
        float b = mix(mix(v001, v101, f.x), mix(v011, v111, f.x), f.y);
        return mix(a, b, f.z);
      }
      void main() {
        vec4 p0 = uInvVP * vec4(vNdc, -1.0, 1.0);
        vec4 p1 = uInvVP * vec4(vNdc, 1.0, 1.0);
        vec3 a = p0.xyz / p0.w, b = p1.xyz / p1.w;
        vec3 dir = normalize(b - a);
        float t0 = 0.0, t1 = 1e9;
        for (int k = 0; k < 3; k++) {
          float lo = (uLo[k] - uEye[k]) / (abs(dir[k]) < 1e-6 ? 1e-6 * sign(dir[k] + 1e-9) : dir[k]);
          float hi = (uHi[k] - uEye[k]) / (abs(dir[k]) < 1e-6 ? 1e-6 * sign(dir[k] + 1e-9) : dir[k]);
          t0 = max(t0, min(lo, hi));
          t1 = min(t1, max(lo, hi));
        }
        if (t1 <= t0) discard;
        float dt = (t1 - t0) / max(uSteps, 1.0);
        float vmin = uVmin.x, vmax = uVmax.x;
        vec4 acc = vec4(0.0);
        for (float t = t0; t < t1; t += dt) {
          vec3 p = uEye + dir * t;
          float raw = sampleField(p);
          float x = clamp((raw - vmin) / max(vmax - vmin, 1e-9), 0.0, 1.0);
          float dens = pow(x, uGamma) * uGain;
          if (dens > 0.001) {
            vec3 col = ramp(x);
            float alpha = 1.0 - exp(-dens * dt * 60.0);
            acc.rgb += (1.0 - acc.a) * col * alpha;
            acc.a += (1.0 - acc.a) * alpha;
            if (acc.a > 0.98) break;
          }
        }
        frag = vec4(acc.rgb, acc.a);
      }`;
      this.volProg = this._mkProgram(vs, fs);
      const quad = new Float32Array([-1, -1, 3, -1, -1, 3]);
      this.volQuad = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, this.volQuad);
      gl.bufferData(gl.ARRAY_BUFFER, quad, gl.STATIC_DRAW);
    }

    setVolume(meta, data) {
      this._initVolume();
      const gl = this.gl;
      if (this.volTex) gl.deleteTexture(this.volTex);
      const tex = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_3D, tex);
      gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
      gl.texImage3D(gl.TEXTURE_3D, 0, gl.R32F, meta.nx, meta.ny, meta.nz, 0,
                    gl.RED, gl.FLOAT, data);
      gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_WRAP_R, gl.CLAMP_TO_EDGE);
      this.volTex = tex;
      this.vol = meta;
      this._growBounds(meta.x[0], meta.y[0], meta.z[0]);
      this._growBounds(meta.x[1], meta.y[1], meta.z[1]);
      this._fitCamera();
      return meta.nx * meta.ny * meta.nz;
    }

    _drawVolume(mvp) {
      if (!this.vol || !this.volTex) return;
      const gl = this.gl;
      const { width: w, height: h } = this.canvas;
      const cp = Math.cos(this.pitch);
      const eye = [
        this.target[0] + this.dist * cp * Math.cos(this.yaw),
        this.target[1] + this.dist * cp * Math.sin(this.yaw),
        this.target[2] + this.dist * Math.sin(this.pitch),
      ];
      const proj = perspective(Math.PI / 4, w / h, this.dist * 0.01, this.dist * 20);
      const view = lookAt(eye, this.target, [0, 0, 1]);
      const inv = invert(mat4Mul(proj, view));
      if (!inv) return;
      gl.useProgram(this.volProg);
      gl.disable(gl.DEPTH_TEST);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.volQuad);
      const a = gl.getAttribLocation(this.volProg, "aNdc");
      gl.enableVertexAttribArray(a);
      gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
      gl.activeTexture(gl.TEXTURE6);
      gl.bindTexture(gl.TEXTURE_3D, this.volTex);
      gl.uniform1i(gl.getUniformLocation(this.volProg, "uField"), 6);
      gl.uniformMatrix4fv(gl.getUniformLocation(this.volProg, "uInvVP"), false, inv);
      gl.uniform3f(gl.getUniformLocation(this.volProg, "uEye"), eye[0], eye[1], eye[2]);
      gl.uniform3f(gl.getUniformLocation(this.volProg, "uLo"), this.vol.x[0], this.vol.y[0], this.vol.z[0]);
      gl.uniform3f(gl.getUniformLocation(this.volProg, "uHi"), this.vol.x[1], this.vol.y[1], this.vol.z[1]);
      gl.uniform3f(gl.getUniformLocation(this.volProg, "uVmin"), this.vol.vmin, 0, 0);
      gl.uniform3f(gl.getUniformLocation(this.volProg, "uVmax"), this.vol.vmax, 0, 0);
      gl.uniform1f(gl.getUniformLocation(this.volProg, "uSteps"), this.volSteps || 160);
      gl.uniform1f(gl.getUniformLocation(this.volProg, "uGamma"), this.volGamma || 1.6);
      gl.uniform1f(gl.getUniformLocation(this.volProg, "uGain"), this.volGain || 2.2);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      gl.enable(gl.DEPTH_TEST);
      gl.disableVertexAttribArray(a);
      gl.activeTexture(gl.TEXTURE0);
    }

    // ---------- 点云层：柔光点精灵（逐点标量着色） ----------
    _initParticles() {
      if (this.ptProg) return;
      const vs = `#version 300 es
      in vec3 aPos; in float aScalar;
      uniform mat4 uMVP; uniform float uSize;
      out float vS;
      void main() {
        vec4 c = uMVP * vec4(aPos, 1.0);
        gl_Position = c;
        gl_PointSize = uSize * (3.0 / max(c.w, 0.2));
        vS = aScalar;
      }`;
      const fs = `#version 300 es
      precision highp float;
      in float vS;
      uniform float uAlpha;
      out vec4 frag;
      vec3 ramp(float t) {
        vec3 c0 = vec3(0.35, 0.10, 0.65);
        vec3 c1 = vec3(0.15, 0.55, 0.85);
        vec3 c2 = vec3(1.00, 0.62, 0.15);
        vec3 c3 = vec3(1.00, 0.98, 0.85);
        if (t < 0.33) return mix(c0, c1, t / 0.33);
        if (t < 0.70) return mix(c1, c2, (t - 0.33) / 0.37);
        return mix(c2, c3, (t - 0.70) / 0.30);
      }
      void main() {
        float r = length(gl_PointCoord * 2.0 - 1.0);
        if (r > 1.0) discard;
        float core = exp(-r * r * 5.0);
        float halo = smoothstep(1.0, 0.1, r) * 0.25;
        frag = vec4(ramp(clamp(vS, 0.0, 1.0)) * (0.7 + 0.6 * core), (core + halo) * uAlpha);
      }`;
      this.ptProg = this._mkProgram(vs, fs);
    }

    setParticles(meta, xyz, scalar) {
      this._initParticles();
      const gl = this.gl;
      if (this.ptPos) gl.deleteBuffer(this.ptPos);
      if (this.ptScl) gl.deleteBuffer(this.ptScl);
      this.ptPos = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, this.ptPos);
      gl.bufferData(gl.ARRAY_BUFFER, xyz, gl.STATIC_DRAW);
      this.ptScl = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, this.ptScl);
      gl.bufferData(gl.ARRAY_BUFFER, scalar, gl.STATIC_DRAW);
      this.ptCount = meta.count;
      this.ptMeta = meta;
      this._growBounds(meta.x[0], meta.y[0], meta.z[0]);
      this._growBounds(meta.x[1], meta.y[1], meta.z[1]);
      this._fitCamera();
      return meta.count;
    }

    _drawParticles(mvp) {
      if (!this.ptCount) return;
      const gl = this.gl;
      gl.useProgram(this.ptProg);
      gl.disable(gl.DEPTH_TEST);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.ptPos);
      const a = gl.getAttribLocation(this.ptProg, "aPos");
      gl.enableVertexAttribArray(a);
      gl.vertexAttribPointer(a, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.ptScl);
      const sc = gl.getAttribLocation(this.ptProg, "aScalar");
      gl.enableVertexAttribArray(sc);
      gl.vertexAttribPointer(sc, 1, gl.FLOAT, false, 0, 0);
      gl.uniformMatrix4fv(gl.getUniformLocation(this.ptProg, "uMVP"), false, mvp);
      gl.uniform1f(gl.getUniformLocation(this.ptProg, "uSize"), (this.ptSize || 3.0) * (window.devicePixelRatio || 1));
      gl.uniform1f(gl.getUniformLocation(this.ptProg, "uAlpha"), this.ptAlpha || 0.35);
      gl.drawArrays(gl.POINTS, 0, this.ptCount);
      gl.enable(gl.DEPTH_TEST);
      gl.disableVertexAttribArray(a);
      gl.disableVertexAttribArray(sc);
    }

    _growBounds(x, y, z) {
      if (!this.lo) this.lo = [Infinity, Infinity, Infinity];
      if (!this.hi) this.hi = [-Infinity, -Infinity, -Infinity];
      this.lo = [Math.min(this.lo[0], x), Math.min(this.lo[1], y), Math.min(this.lo[2], z)];
      this.hi = [Math.max(this.hi[0], x), Math.max(this.hi[1], y), Math.max(this.hi[2], z)];
    }

    _fitCamera() {
      if (!this.lo || !this.hi) return;
      if (!isFinite(this.lo[0]) || !isFinite(this.hi[0])) return;
      this.center = [(this.lo[0] + this.hi[0]) / 2, (this.lo[1] + this.hi[1]) / 2,
                     (this.lo[2] + this.hi[2]) / 2];
      this.radius = Math.max(this.hi[0] - this.lo[0], this.hi[1] - this.lo[1],
                             this.hi[2] - this.lo[2], 1e-6) / 2;
      if (!this._userCamera) {
        this.target = this.center.slice();
        this.dist = this.radius * 4.4;
      }
    }

'''

anchor = "    _loop() {"
assert anchor in s
s = s.replace(anchor, NEW + anchor, 1)

# 在 _loop 里插入两个 pass：体积先画（背景），点云在普通图层之后
s = s.replace("""      for (const layer of this.layers) {
        gl.bindBuffer(gl.ARRAY_BUFFER, layer.buffer);""",
              """      this._drawVolume(mvp);
      gl.useProgram(this.prog);
      gl.uniformMatrix4fv(this.uMVP, false, mvp);
      for (const layer of this.layers) {
        gl.bindBuffer(gl.ARRAY_BUFFER, layer.buffer);""", 1)
s = s.replace("""      this._drawDynamic(gl);""",
              """      this._drawParticles(mvp);
      this._drawDynamic(gl);""", 1)
p.write_text(s, encoding="utf-8")
print("view3d: volume + particles passes added")
