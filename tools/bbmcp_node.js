#!/usr/bin/env node
/* 极简 Blockbench MCP 客户端（node 版）。
 * 本机 PATH 上没有 python（tools/bbmcp_call.py 因此跑不了），node 在 E:\nodejs\node.exe。
 * 协议同 bbmcp_call.py：POST initialize -> 从响应头拿 mcp-session-id -> 之后每次带上。
 *
 * 用法：
 *   node tools/bbmcp_node.js list
 *   node tools/bbmcp_node.js schema <tool> [...]
 *   node tools/bbmcp_node.js call <tool> '<json args>'
 *   node tools/bbmcp_node.js dump <tool> '<json args>' <out.json>   # 原始返回落盘（图片 base64 走这条）
 */
const http = require('http');
const fs = require('fs');

const HOST = '127.0.0.1', PORT = 3000, MCP_PATH = '/bb-mcp';

function post(payload, sid) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/event-stream',
      'Content-Length': Buffer.byteLength(body),
    };
    if (sid) headers['mcp-session-id'] = sid;
    const req = http.request({ host: HOST, port: PORT, path: MCP_PATH, method: 'POST', headers }, (res) => {
      let d = '';
      res.on('data', (c) => (d += c));
      res.on('end', () => {
        let parsed = {};
        for (const line of d.split(/\r?\n/)) {
          if (line.startsWith('data: ')) { parsed = JSON.parse(line.slice(6)); break; }
        }
        if (!parsed || !Object.keys(parsed).length) { try { parsed = JSON.parse(d); } catch { parsed = {}; } }
        resolve({ msg: parsed, sid: res.headers['mcp-session-id'], status: res.statusCode, raw: d });
      });
    });
    req.on('error', reject);
    req.setTimeout(900000, () => { req.destroy(new Error('timeout')); });
    req.write(body); req.end();
  });
}

const INIT = { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'hermes-node', version: '1.0' } } };

async function main() {
  const mode = process.argv[2] || 'list';
  let r = await post(INIT);
  let sid = r.sid;
  if (!sid) { r = await post(INIT); sid = r.sid; }
  if (!sid) { console.log('ERR 拿不到 mcp-session-id'); process.exit(3); }

  r = await post({ jsonrpc: '2.0', id: 9, method: 'tools/list' }, sid);
  const tools = {};
  for (const t of (r.msg.result?.tools || [])) tools[t.name] = t;

  if (mode === 'list') {
    for (const n of Object.keys(tools).sort()) console.log(n);
  } else if (mode === 'schema') {
    for (const n of process.argv.slice(3)) {
      const t = tools[n];
      if (!t) { console.log(n, '-> NOT FOUND'); continue; }
      console.log('==', n, '==');
      console.log(JSON.stringify(t.inputSchema?.properties || {}, null, 1));
    }
  } else if (mode === 'call' || mode === 'dump') {
    // 入参写法（PowerShell 会吃掉裸 JSON 里的双引号，所以都要规避）：
    //   call <tool> @args.json            —— 整个 JSON 从文件读
    //   call <tool> k=v k2=@file.js n=3   —— k=v 逐个给；值以 @ 开头则读该文件当字符串
    //   dump <tool> <同 call 的入参> <out.json>  —— 原始返回整体落盘（图片 base64 这条走）
    const rest = process.argv.slice(4);
    let outPath = null;
    if (mode === 'dump') { outPath = rest.pop(); }
    let args = {};
    if (rest.length === 1 && rest[0].startsWith('@')) {
      args = JSON.parse(fs.readFileSync(rest[0].slice(1), 'utf8'));
    } else if (rest.length === 1 && rest[0].trim().startsWith('{')) {
      args = JSON.parse(rest[0]);
    } else {
      for (const s of rest) {
        const i = s.indexOf('=');
        if (i < 0) continue;
        const k = s.slice(0, i);
        let v = s.slice(i + 1);
        if (v.startsWith('@')) v = fs.readFileSync(v.slice(1), 'utf8');
        else { try { v = JSON.parse(v); } catch { /* 保持字符串 */ } }
        args[k] = v;
      }
    }
    const res = await post({ jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: process.argv[3], arguments: args } }, sid);
    if (mode === 'dump') {
      fs.writeFileSync(outPath, JSON.stringify(res.msg, null, 1));
      console.log('written', outPath, JSON.stringify(res.msg).length, 'bytes');
      process.exit(0);
    }
    const blocks = res.msg.result?.content || [];
    const out = [];
    for (const b of blocks) {
      if (b.type === 'text') out.push(b.text);
      else if (b.type === 'image') out.push(`<image ${b.mimeType} ${(b.data || '').length} chars base64>`);
      else out.push(JSON.stringify(b).slice(0, 800));
    }
    if (res.msg.error) out.push('ERR ' + JSON.stringify(res.msg.error));
    console.log(out.join('\n') || JSON.stringify(res.msg).slice(0, 3000));
  } else {
    console.log('usage: list | schema <tool> [...] | call <tool> <json> | dump <tool> <json> <out>');
  }
}
main().catch((e) => { console.log('FATAL', e.message); process.exit(2); });
