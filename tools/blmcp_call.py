#!/usr/bin/env python3
"""极简 Blender MCP 客户端：不经 MCP stdio 客户端，直接跟 Blender 里的 socket 桥说话。

协议（Blender Lab 官方扩展 `bl_ext.user_default.mcp`，源码见 `D:/blender_mcp`）：
  TCP `localhost:9877`，发 `{"type":"execute","code":"<python>","strict_json":true}` + `"\\0"`，
  收 `JSON` + `"\\0"`。响应字段：`status`(ok|error) / `result` / `message` / `stdout` / `stderr`。
  送进去的代码**必须**在结尾给 `result` 赋一个 dict（addon 侧 `exec(code, {"result": {}})`，
  非 dict 直接报错 —— 见 `mcp_to_blender_server._execute_code`）。

前置：Blender 侧 MCP 桥已经起来。两种起法：
  1) GUI：Blender 里 Preferences → Add-ons → MCP → Auto Start（端口默认被改到 9877）。
  2) **无头（推荐，可复现）**：
     "D:/Blender/blender.exe" --background --online-mode --command blender_mcp --port 9877
     （`--background` 下 bpy.app.timers 不跳，官方走 `execute_blocking` 的 select 循环；
       没有 `--online-mode` 会直接报 "Online access must be enabled"。）

用法：
  python tools/blmcp_call.py ping                      # 活体探测（版本/场景/物体数）
  python tools/blmcp_call.py run tools/xxx.py          # 把整个 .py 当代码送进去执行
  python tools/blmcp_call.py run tools/xxx.py --json   # 额外把 result 原样打成 JSON
  python tools/blmcp_call.py eval "import bpy; ..."    # 送一小段代码
  python tools/blmcp_call.py shot out.png              # 让 Blender 把视口截图存盘（仅 GUI 模式）

环境变量：`BLENDER_MCP_HOST`（默认 localhost）、`BLENDER_MCP_PORT`（默认 9877）。
"""
import json
import os
import socket
import sys

HOST = os.environ.get('BLENDER_MCP_HOST', 'localhost')
PORT = int(os.environ.get('BLENDER_MCP_PORT', '9877'))
TIMEOUT = float(os.environ.get('BLENDER_MCP_TIMEOUT', '1800'))
BUF = 1 << 16

PING_CODE = (
    "import bpy\n"
    "result = {\n"
    "    'blender_version': bpy.app.version_string,\n"
    "    'background': bool(bpy.app.background),\n"
    "    'online_access': bool(bpy.app.online_access),\n"
    "    'scene': bpy.context.scene.name,\n"
    "    'object_count': len(bpy.data.objects),\n"
    "    'object_names': [o.name for o in bpy.data.objects][:20],\n"
    "}\n"
)

SHOT_CODE = (
    "import bpy\n"
    "bpy.context.scene.render.filepath = %r\n"
    "bpy.ops.render.render(write_still=True)\n"
    "result = {'saved': bpy.context.scene.render.filepath}\n"
)


def send(code):
    """把一段 python 代码发进 Blender，返回响应 dict。"""
    req = json.dumps({'type': 'execute', 'code': code, 'strict_json': True}) + '\0'
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(TIMEOUT)
            sock.connect((HOST, PORT))
            sock.sendall(req.encode('utf-8'))
            buf = bytearray()
            while True:
                chunk = sock.recv(BUF)
                if not chunk:
                    break
                buf.extend(chunk)
                if b'\0' in buf:
                    break
    except ConnectionRefusedError:
        raise SystemExit(
            '连不上 Blender MCP 桥 {:s}:{:d}。\n'
            '先把 Blender 桥起来（无头）：\n'
            '  "D:/Blender/blender.exe" --background --online-mode '
            '--command blender_mcp --port {:d}'.format(HOST, PORT, PORT))
    except socket.timeout:
        raise SystemExit('Blender MCP 桥 {:s}:{:d} 超时（{:.0f}s）；代码可能跑太久或死循环。'
                         .format(HOST, PORT, TIMEOUT))
    line, _sep, _rest = buf.partition(b'\0')
    if not line:
        raise SystemExit('Blender 返回空响应（桥在、但没执行结果）')
    return json.loads(line.decode('utf-8', 'replace'))


def show(res, dump_json=False):
    status = res.get('status')
    out = res.get('stdout') or ''
    err = res.get('stderr') or ''
    if out.strip():
        print(out.rstrip())
    if err.strip():
        sys.stderr.write(err.rstrip() + '\n')
    if status == 'ok':
        result = res.get('result')
        if dump_json:
            print(json.dumps(result, ensure_ascii=False, indent=1))
        elif isinstance(result, dict) and result:
            print('result = ' + json.dumps(result, ensure_ascii=False)[:4000])
    else:
        print('BLENDER ERROR: ' + str(res.get('message', ''))[:4000])
    return 0 if status == 'ok' else 1


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'ping'
    if mode == 'ping':
        return show(send(PING_CODE))
    if mode == 'eval':
        if len(sys.argv) < 3:
            raise SystemExit('用法：blmcp_call.py eval "<python 代码>"')
        return show(send(sys.argv[2]), '--json' in sys.argv)
    if mode == 'run':
        if len(sys.argv) < 3:
            raise SystemExit('用法：blmcp_call.py run <file.py>')
        with open(sys.argv[2], 'r', encoding='utf-8') as fp:
            code = fp.read()
        return show(send(code), '--json' in sys.argv)
    if mode == 'shot':
        out = sys.argv[2] if len(sys.argv) > 2 else 'blender_shot.png'
        return show(send(SHOT_CODE % out))
    raise SystemExit(__doc__)


if __name__ == '__main__':
    sys.exit(main())