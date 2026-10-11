'use strict';
/* Blockbench MCP 客户端库（node 版）—— 供 tools/ 下的构建脚本 require。
 * 协议同 tools/bbmcp_call.py：POST initialize -> 从响应头拿 mcp-session-id -> 之后每次带上。 */
const http = require('http');

const HOST = '127.0.0.1', PORT = 3000, MCP_PATH = '/bb-mcp';
const INIT = {
  jsonrpc: '2.0', id: 1, method: 'initialize',
  params: { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'hermes-node', version: '1.0' } },
};

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
    req.on('error', (e) => reject(e));
    req.setTimeout(75000, () => req.destroy(new Error('mcp timeout 75s: ' + (payload.params?.name || payload.method))));
    req.write(body); req.end();
  });
}

/* 带重试的 post：MCP 桥偶尔会在某个 tools/call 上无限期挂住（2026-10-11 实测 500+ 次调用后发生），
 * 没有超时的话整条构建就卡死。75s 超时 + 最多 3 次重试，把偶发挂住变成一次可恢复的重试。 */
async function postR(payload, sid, tries = 3) {
  let last;
  for (let i = 1; i <= tries; i++) {
    try { return await post(payload, sid); } catch (e) {
      last = e;
      if (i < tries) { console.error(`[mcp] ${e.message} -> 重试 ${i}/${tries - 1}`); await new Promise((r) => setTimeout(r, 1500)); }
    }
  }
  throw last;
}

class Bb {
  constructor(sid) { this.sid = sid; this.n = 2; }

  static async connect() {
    let r = await postR(INIT);
    let sid = r.sid;
    if (!sid) { r = await postR(INIT); sid = r.sid; }
    if (!sid) throw new Error('拿不到 mcp-session-id');
    return new Bb(sid);
  }

  async raw(tool, args) {
    const res = await postR({ jsonrpc: '2.0', id: this.n++, method: 'tools/call', params: { name: tool, arguments: args || {} } }, this.sid);
    return res.msg;
  }

  /** 返回 { text, images: [{mimeType, data}], error } */
  async call(tool, args) {
    const msg = await this.raw(tool, args);
    const blocks = msg.result?.content || [];
    const text = blocks.filter((b) => b.type === 'text').map((b) => b.text).join('\n');
    const images = blocks.filter((b) => b.type === 'image').map((b) => ({ mimeType: b.mimeType, data: b.data }));
    return { text, images, error: msg.error, isError: msg.result?.isError === true, msg };
  }

  /** 只取文本；isError / error 时抛出 */
  async t(tool, args) {
    const r = await this.call(tool, args);
    if (r.error) throw new Error(`${tool}: ${JSON.stringify(r.error)}`);
    if (r.isError) throw new Error(`${tool}: ${r.text}`);
    return r;
  }

  async listTools() {
    const r = await postR({ jsonrpc: '2.0', id: 900, method: 'tools/list' }, this.sid);
    return (r.msg.result?.tools || []).map((x) => x.name);
  }
}

module.exports = { Bb, post, postR, HOST, PORT, MCP_PATH };
