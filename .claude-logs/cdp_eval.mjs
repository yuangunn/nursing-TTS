const target = (await (await fetch("http://localhost:9222/json")).json()).find((t) => t.type === "page");
const expr = process.argv[2];
const ws = new WebSocket(target.webSocketDebuggerUrl);
ws.onopen = () => ws.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression: expr, returnByValue: true, awaitPromise: true } }));
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id === 1) { console.log(typeof d.result?.result?.value === "string" ? d.result.result.value : JSON.stringify(d.result ?? d)); ws.close(); process.exit(0); } };
setTimeout(() => { console.log("timeout"); process.exit(1); }, 8000);
