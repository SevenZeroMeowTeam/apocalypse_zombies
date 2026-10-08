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
    req.on('error', reject);
    req.setTimeout(900000, () => req.destroy(new Error('mcp timeout')));
    req.write(body); req.end();
  });
}

class Bb {
  constructor(sid) { this.sid = sid; this.n = 2; }

  static async connect() {
    let r = await post(INIT);
    let sid = r.sid;
    if (!sid) { r = await post(INIT); sid = r.sid; }
    if (!sid) throw new Error('拿不到 mcp-session-id');
    return new Bb(sid);
  }

  async raw(tool, args) {
    const res = await post({ jsonrpc: '2.0', id: this.n++, method: 'tools/call', params: { name: tool, arguments: args || {} } }, this.sid);
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
    const r = await post({ jsonrpc: '2.0', id: 900, method: 'tools/list' }, this.sid);
    return (r.msg.result?.tools || []).map((x) => x.name);
  }
}

module.exports = { Bb, post, HOST, PORT, MCP_PATH };
