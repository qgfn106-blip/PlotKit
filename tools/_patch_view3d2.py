"""给 view3d.js 加 /api/volume 与 /api/particles 的二进制解析器，并保护包围盒。"""
import pathlib

p = pathlib.Path("src/plotkit/static/view3d.js")
s = p.read_text(encoding="utf-8")

old_export = "  window.PK3D = { View3D, hexToRgba, parseFrame, parseMesh, PALETTE };"
new_export = '''  /** 解析 /api/volume：magic+meta_len+n+meta+float32 标量场（x 变化最快）。 */
  function parseVolume(buffer) {
    const view = new DataView(buffer);
    const metaLen = view.getUint32(4, true);
    const meta = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 12, metaLen)));
    const offset = 12 + metaLen;
    return { meta, field: new Float32Array(buffer.slice(offset)) };
  }

  /** 解析 /api/particles：magic+meta_len+n+meta+float32 xyz + float32 scalar。 */
  function parseParticles(buffer) {
    const view = new DataView(buffer);
    const metaLen = view.getUint32(4, true);
    const n = view.getUint32(8, true);
    const meta = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 12, metaLen)));
    const base = 12 + metaLen;
    return {
      meta,
      xyz: new Float32Array(buffer.slice(base, base + n * 12)),
      scalar: new Float32Array(buffer.slice(base + n * 12, base + n * 16)),
    };
  }

  window.PK3D = { View3D, hexToRgba, parseFrame, parseMesh, parseVolume, parseParticles, PALETTE };'''

assert old_export in s
s = s.replace(old_export, new_export, 1)

old_layers = """    setLayers(layers) {
      const gl = this.gl;"""
new_layers = """    setLayers(layers) {
      const gl = this.gl;
      if (!layers.length && this.lo && isFinite(this.lo[0])) { this._fitCamera(); return 0; }"""
assert old_layers in s
s = s.replace(old_layers, new_layers, 1)
p.write_text(s, encoding="utf-8")
print("parsers + bounds guard added")
