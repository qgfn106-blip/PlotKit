// 用 CDP 对已打开的页面截图（比 --screenshot 更可靠：页面已经跑完 JS）。
// 用法: node tools/cdp_shot2.mjs out.png [urlPrefix]
import fs from 'node:fs';

const out = process.argv[2] || 'docs/shot.png';
const prefix = process.argv[3] || 'http://127.0.0.1:8792';
const endpoint = process.env.CDP || 'http://127.0.0.1:9400';

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

await send('Page.enable');
const clipArg = process.env.CLIP; // "x,y,w,h,scale"
const clip = clipArg
  ? (() => {
      const [x, y, width, height, scale] = clipArg.split(',').map(Number);
      return { x, y, width, height, scale: scale || 2 };
    })()
  : undefined;
const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false, ...(clip ? { clip } : {}) });
fs.writeFileSync(out, Buffer.from(shot.data, 'base64'));
console.log(`saved ${out}`);
socket.close();
