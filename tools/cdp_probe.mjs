// 通用 CDP 探针：连到 --remote-debugging-port 的浏览器，对指定 URL 页面执行表达式。
// 用法: node tools/cdp_probe.mjs <urlPrefix> "<expression>"
const prefix = process.argv[2] || 'http://127.0.0.1:8792';
const expression = process.argv[3] || 'document.title';
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
const out = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
console.log(JSON.stringify(out.result?.value ?? out.result, null, 2));
socket.close();
