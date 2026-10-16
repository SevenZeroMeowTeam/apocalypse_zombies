#!/usr/bin/env python3
"""BlockbenchMCP 桥客户端（当前装的是 0.3.1 自定义命令协议版）。

协议（与 tools/bbmcp_call.py 记的老 JSON-RPC 版不同，别搞混）：
  POST http://127.0.0.1:8787/command
  body: {"action": "<命令>", "params": {...}, "id": <任意>}
  返回: {"ok": true, "result": ...} 或 {"ok": false, "error": "...", "stack": "..."}
约束：必须带 Host: 127.0.0.1 / localhost（插件拒绝非环回 Host），不能带 Origin。
另：GET /ping 是健康检查。

用法：
  python tools/bbmcp.py ping                      # 看桥是否活着
  python tools/bbmcp.py list                      # 列命令（直接 grep 插件源码）
  python tools/bbmcp.py guide [topic]             # get_guide
  python tools/bbmcp.py call <action> ['<json>']  # 调一个命令，params 为 JSON
  python tools/bbmcp.py script <file.js>          # execute_script，跑一段 JS（读文件）
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

PORT = int(os.environ.get('BB_MCP_PORT', '8787'))
URL = f'http://127.0.0.1:{PORT}/command'


def _plugin_path():
    """找 blockbench_mcp.js。注意 DSH 子进程里 APPDATA 被重定向到 eac-beta\\appdata，
    所以要走 USERPROFILE 拼真实 Roaming 路径。"""
    cands = [os.environ.get('BB_MCP_PLUGIN', '')]
    for root in (os.environ.get('APPDATA', ''), os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming')):
        if root:
            cands.append(os.path.join(root, 'Blockbench', 'plugins', 'blockbench_mcp.js'))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return cands[-1]


PLUGIN_JS = _plugin_path()
HDRS = {'Content-Type': 'application/json', 'Accept': 'application/json'}


def call(action, params=None, timeout=300, rid=1):
    body = json.dumps({'action': action, 'params': params or {}, 'id': rid}).encode()
    req = urllib.request.Request(URL, data=body, headers=HDRS, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': f'HTTP {e.code}: {e.read().decode("utf-8", "replace")[:400]}'}
    except Exception as e:
        return {'ok': False, 'error': f'{type(e).__name__}: {e}'}


def script(path, params=None, timeout=300):
    """跑一个 js 文件（等价于 CLI 的 `script <file.js>` 子命令）。
    apply 这类脚本要按步骤串 js 与 action，走函数比再拼一遍命令行干净。"""
    code = Path(path).read_text(encoding='utf-8')
    return call('execute_script', {'code': code, 'params': params or {}}, timeout=timeout)


def ping():
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/ping', headers=HDRS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


# --- 结果折叠：把 base64 图片落盘，字符串截断，避免刷屏 -----------------------
IMG_SIGS = ('iVBORw0KGgo', '/9j/', 'R0lGOD', 'UklGR', 'data:image')
_c = [0]


def _save_image(data, outdir, tag):
    if data.startswith('data:image'):
        data = data.split(',', 1)[-1]
    data = re.sub(r'\s+', '', data)
    try:
        raw = base64.b64decode(data + '=' * (-len(data) % 4))
    except Exception:
        return None
    if len(raw) < 64:
        return None
    ext = ('png' if raw[:4] == b'\x89PNG' else 'jpg' if raw[:2] == b'\xff\xd8'
           else 'gif' if raw[:3] == b'GIF' else 'webp' if raw[8:12] == b'WEBP' else 'bin')
    _c[0] += 1
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    p = outdir / f'{tag}-{_c[0]:02d}.{ext}'
    p.write_bytes(raw)
    return p


def collapse(obj, outdir, tag='img'):
    if isinstance(obj, dict):
        return {k: collapse(v, outdir, f'{tag}-{k}') for k, v in obj.items()}
    if isinstance(obj, list):
        return [collapse(v, outdir, f'{tag}{i}') for i, v in enumerate(obj)]
    if isinstance(obj, str):
        if len(obj) > 200 and any(obj.startswith(s) or s in obj[:60] for s in IMG_SIGS):
            p = _save_image(obj, outdir, tag)
            if p:
                return f'<image -> {p}>'
        if len(obj) > 600:
            return obj[:400] + f'...<{len(obj)} chars>'
    return obj


def list_commands():
    with open(PLUGIN_JS, encoding='utf-8', errors='replace') as f:
        src = f.read()
    names = re.findall(r'^\t(?:async )?([a-z][a-z0-9_]*)\(p\)\s*\{', src, re.M)
    return sorted(set(names))


def parse_params(raw):
    """params 支持内联 JSON 或 @文件路径。PowerShell 传参时会吞掉双引号，
    所以复杂 params 一律用 @file（文件里写 JSON）。"""
    if not raw:
        return {}
    if raw.startswith('@'):
        raw = Path(raw[1:]).read_text(encoding='utf-8')
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f'params JSON 解析失败（{e}）。PowerShell 会吞双引号，'
                         f'复杂参数请写成文件后用 @路径 传入。原文：{raw[:200]}')


def main():
    args = sys.argv[1:]
    mode = args[0] if args else 'ping'

    if mode == 'ping':
        print(json.dumps(ping(), ensure_ascii=False, indent=1))

    elif mode == 'list':
        for n in list_commands():
            print(n)

    elif mode == 'guide':
        res = call('get_guide', {'topic': args[1]} if len(args) > 1 else {})
        print(res.get('result') if res.get('ok') else json.dumps(res, ensure_ascii=False, indent=1))

    elif mode == 'call':
        if len(args) < 2:
            raise SystemExit('需要 action 名')
        params = parse_params(args[2] if len(args) > 2 else '')
        outdir = Path(args[3]) if len(args) > 3 and args[3] else Path('build/bbmcp')
        res = call(args[1], params)
        if res.get('ok'):
            out = collapse(res.get('result'), outdir, args[1])
            text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, indent=1)
            print(text if text is not None else '(no result)')
        else:
            print('ERR', json.dumps(res, ensure_ascii=False, indent=1))
            raise SystemExit(1)

    elif mode == 'script':
        if len(args) < 2:
            raise SystemExit('需要 js 文件路径')
        with open(args[1], encoding='utf-8') as f:
            code = f.read()
        params = parse_params(args[2] if len(args) > 2 else '')
        res = call('execute_script', {'code': code, 'params': params})
        if res.get('ok'):
            out = res.get('result')
            print(out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, indent=1)[:20000])
        else:
            print('ERR', json.dumps(res, ensure_ascii=False, indent=1))
            raise SystemExit(1)

    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
