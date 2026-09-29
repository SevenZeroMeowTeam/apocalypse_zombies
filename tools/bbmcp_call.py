#!/usr/bin/env python3
"""极简 MCP 客户端：直接调 Blockbench MCP 里那些没进 Hermes 连接器目录的工具。

握手顺序（skill: blockbench-mcp-plugin 记的坑）：
  POST initialize → 从 **响应头** 拿 mcp-session-id → 之后每次带这个头。
裸 tools/call 会被拒：Bad Request: Mcp-Session-Id header is required。

用法：
  python tools/bbmcp_call.py list                      # 列出所有工具名
  python tools/bbmcp_call.py schema <tool> [...]       # 看某几个工具的入参 schema
  python tools/bbmcp_call.py call <tool> '<json args>' # 调一个工具
"""
import json
import sys
import urllib.request

URL = 'http://localhost:3000/bb-mcp'
HDRS = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}


def _post(payload, sid=None):
    h = dict(HDRS)
    if sid:
        h['mcp-session-id'] = sid
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers=h, method='POST')
    with urllib.request.urlopen(req, timeout=180) as r:
        sid_out = r.headers.get('mcp-session-id')
        raw = r.read().decode('utf-8', 'replace')
    for line in raw.splitlines():                 # SSE 帧：只取 data: 行
        if line.startswith('data: '):
            return json.loads(line[6:]), sid_out
    return (json.loads(raw) if raw.strip() else {}), sid_out


def handshake():
    init, sid = _post({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                       'params': {'protocolVersion': '2024-11-05', 'capabilities': {},
                                  'clientInfo': {'name': 'hermes', 'version': '1.0'}}})
    if not sid:
        init2, sid = _post({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                            'params': {'protocolVersion': '2024-11-05', 'capabilities': {},
                                       'clientInfo': {'name': 'hermes', 'version': '1.0'}}})
    if not sid:
        raise SystemExit('拿不到 mcp-session-id')
    return sid


def call(sid, tool, args, rid=2):
    res, _ = _post({'jsonrpc': '2.0', 'id': rid, 'method': 'tools/call',
                    'params': {'name': tool, 'arguments': args}}, sid)
    return res


def text_of(res):
    out = []
    for c in (res.get('result', {}) or {}).get('content', []) or []:
        out.append(c.get('text', ''))
    if 'error' in res:
        out.append('ERR ' + json.dumps(res['error'], ensure_ascii=False))
    return '\n'.join(out)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'list'
    sid = handshake()
    res, _ = _post({'jsonrpc': '2.0', 'id': 9, 'method': 'tools/list'}, sid)
    tools = {t['name']: t for t in res['result']['tools']}

    if mode == 'list':
        for n, t in sorted(tools.items()):
            print(n)
    elif mode == 'schema':
        for n in sys.argv[2:]:
            t = tools.get(n)
            if not t:
                print(n, '-> NOT FOUND')
                continue
            print('==', n, '==')
            print(json.dumps(t.get('inputSchema', {}).get('properties', {}), ensure_ascii=False, indent=1))
    elif mode == 'call':
        tool = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        res = call(sid, tool, args)
        txt = text_of(res)
        if txt:
            print(txt)
        else:
            # 纯图片返回：base64 打成文字既没用又会被截断，只给摘要。
            # 要图就读 Result.content[...]["data"] 自己解码（见 tools/bb_shot.py）。
            blocks = (res.get('result', {}) or {}).get('content', []) or []
            summary = [{k: (f"<{len(v)} chars base64>"
                            if k == 'data' and isinstance(v, str) else v)
                        for k, v in b.items()} for b in blocks]
            print(json.dumps({'content': summary} if blocks else res,
                             ensure_ascii=False)[:2000])
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
