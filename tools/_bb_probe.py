#!/usr/bin/env python3
"""临时探针：看看某个端口上到底是不是 BlockbenchMCP 桥，并打印原始响应。"""
import json
import socket
import sys
import urllib.request

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
path = sys.argv[2] if len(sys.argv) > 2 else '/bb-mcp'
print('target:', f'http://127.0.0.1:{port}{path}')

try:
    with socket.create_connection(('127.0.0.1', port), timeout=5):
        print('tcp: open')
except Exception as e:
    print('tcp: FAIL', e)
    raise SystemExit(1)

body = json.dumps({
    'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
    'params': {'protocolVersion': '2024-11-05', 'capabilities': {},
               'clientInfo': {'name': 'hermes', 'version': '1.0'}},
}).encode()
req = urllib.request.Request(
    f'http://127.0.0.1:{port}{path}', data=body, method='POST',
    headers={'Content-Type': 'application/json',
             'Accept': 'application/json, text/event-stream'})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print('status:', r.status)
        print('headers:', dict(r.headers))
        print('body:', r.read().decode('utf-8', 'replace')[:1500])
except urllib.error.HTTPError as e:
    print('HTTPError:', e.code)
    print('headers:', dict(e.headers))
    print('body:', e.read().decode('utf-8', 'replace')[:1500])
except Exception as e:
    print('FAIL:', type(e).__name__, e)
