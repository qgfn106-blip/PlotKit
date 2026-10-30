// 一条 CDP 连接里跑一串动作，避免反复建 WS 把 headless 浏览器拖死。
// 用法: node tools/cdp_flow.mjs '<json>'
//   json = [{ "eval": "expr", "shot": "docs/x.png", "clip": "x,y,w,h,scale" }, ...]
// 环境变量 CDP 指调试端点（默认 http://127.0.0.1:9403），第一个参数后的 url 前缀可选。
const flow = JSON.parse(process.argv[2] || '[]');
const prefix = process.argv[3] || 'http://127.0.0.1';
const endpoint = process.env.CDP || 'http://127.0.0.1:9403';

const pages = await (await fetch(`${endpoint}/json/list`)).json();
const page = pages.find((p) => p.type === 'page' && p.url.startsWith(prefix));
if (!page) {
  console.error('page not found; have:', pages.map((p) => p.url));
  process.exit(3);
}
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => {
  socket.addEventListener('open', res, { once: true });
  socket.addEventListener('error', rej, { once: true });
});
let seq = 0;
const pending = new Map();
socket.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (!msg.id) return;
  const entry = pending.get(msg.id);
  if (!entry) return;
  pending.delete(msg.id);
  msg.error ? entry.reject(new Error(msg.error.message)) : entry.resolve(msg.result);
});
const send = (method, params) =>
  new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });

const fs = await import('node:fs');
for (const step of flow) {
  if (step.eval) {
    const out = await send('Runtime.evaluate', {
      expression: step.eval,
      returnByValue: true,
      awaitPromise: true,
    });
    console.log(JSON.stringify(out.result?.value ?? out.result).slice(0, 2000));
  }
  if (step.sleep) await new Promise((r) => setTimeout(r, step.sleep));
  if (step.shot) {
    const params = { format: 'png' };
    if (step.clip) {
      const [x, y, w, h, s] = step.clip.split(',').map(Number);
      params.clip = { x, y, width: w, height: h, scale: s || 1 };
    }
    const { data } = await send('Page.captureScreenshot', params);
    fs.writeFileSync(step.shot, Buffer.from(data, 'base64'));
    console.log(`saved ${step.shot}`);
  }
}
socket.close();
