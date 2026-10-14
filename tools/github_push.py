#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 GitHub 可用 IP → 落到 hosts → 提交并推送。

用法::

    py tools/github_push.py                  # 扫描 + 应用 + 提交 + 推送（出货后用这个）
    py tools/github_push.py --scan-only      # 只扫描并打印排行，不动任何东西
    py tools/github_push.py --no-push        # 扫描 + 应用 + 提交，但不推
    py tools/github_push.py --restore-hosts  # 把 hosts 里我们自己那段撤掉

为什么需要它：本机到 github.com:443 时通时不通 —— 系统 DNS 给的 20.205.243.166
经常 21 秒握手超时（`git ls-remote` 实测：`Could not connect to server`），
而换个边缘 IP 就秒过。这里把一批候选逐个做「TCP 443 + **带证书校验的** TLS 握手」，
挑最快的几条写进 hosts。改的是 hosts 里我们自己的标记段，`--restore-hosts` 随时撤掉。

不写死任何凭证：推送走 git 自己的配置（credential helper / 环境里的 token）。
"""

import argparse
import io
import os
import re
import socket
import ssl
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# 仓库与远程（从 readme / .github 里读出来的真实地址）
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE = 'origin'
REMOTE_URL = 'https://github.com/SevenZeroMeowTeam/apocalypse_zombies.git'
BRANCH = 'main'

HOSTS_PATH = r'C:\Windows\System32\drivers\etc\hosts'
MARK_BEGIN = '# >>> dsh-github-ip（自动生成；tools/github_push.py --restore-hosts 可撤）'
MARK_END = '# <<< dsh-github-ip'

# 要解析/测的域名：git 走前两个，release 下载走后三个
PROBE_HOSTS = ('github.com', 'api.github.com', 'codeload.github.com',
               'objects.githubusercontent.com', 'raw.githubusercontent.com')

# 社区长期在用的 GitHub 边缘 IP（github.com 的 A 记录池）。DNS 被污染时这些照样能打。
SEED_IPS = (
    '140.82.112.3', '140.82.113.3', '140.82.114.3', '140.82.116.3', '140.82.121.3',
    '20.205.243.166', '20.205.243.168', '20.27.177.113', '20.200.245.247',
    '20.233.83.145', '20.248.137.48', '20.207.73.82', '20.175.192.147',
    '20.87.245.0', '4.237.22.38', '20.26.156.215', '20.201.28.151',
)

# 用它们问 DNS（系统 DNS 可能被污染，所以直接问公共的）
DNS_SERVERS = ('223.5.5.5', '119.29.29.29', '8.8.8.8', '1.1.1.1')

IP_RE = re.compile(r'\b(\d{1,3}(?:\.\d{1,3}){3})\b')


def log(msg=''):
    print(msg, flush=True)


def dns_lookup(host, server, timeout=6):
    """问一个指定的 DNS 服务器。用 nslookup（Windows 自带），省得手写 DNS 报文。"""
    try:
        out = subprocess.run(['nslookup', host, server], capture_output=True, text=True,
                             timeout=timeout, errors='replace').stdout
    except Exception:
        return []
    ips = []
    for line in out.splitlines():
        # 只认 "Address:" / "Addresses:" 行，且要排掉服务器自己那个地址
        if 'Address' not in line:
            continue
        for ip in IP_RE.findall(line):
            if ip == server or ip.startswith('127.'):
                continue
            if ip not in ips:
                ips.append(ip)
    return ips


def probe(ip, host='github.com', timeout=3.0):
    """TCP 443 + 带证书校验的 TLS 握手。返回 (通不通, 毫秒)。

    只测 TCP 是不够的 —— 国内不少「可用 IP」其实是劫持节点，TCP 通、证书对不上。
    这里用 create_default_context() 走完握手并校验 SAN，能过的才敢写进 hosts。
    """
    t0 = time.monotonic()
    try:
        with socket.create_connection((ip, 443), timeout=timeout) as sock:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                tls.getpeercert()
    except Exception:
        return False, None
    return True, (time.monotonic() - t0) * 1000.0


def gather_candidates():
    """内置池 ∪ 各公共 DNS 解析出来的 IP。"""
    cands = {}
    for ip in SEED_IPS:
        cands.setdefault(ip, '内置')
    for server in DNS_SERVERS:
        for host in ('github.com',):
            for ip in dns_lookup(host, server):
                cands.setdefault(ip, 'DNS %s' % server)
    return cands


def scan(verbose=True):
    cands = gather_candidates()
    if verbose:
        log('候选 %d 个，开始逐个做 TLS 握手…' % len(cands))
    results = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(probe, ip): ip for ip in cands}
        for fut in futures:
            ip = futures[fut]
            try:
                ok, ms = fut.result()
            except Exception:
                ok, ms = False, None
            if ok:
                results.append((ms, ip, cands[ip]))
    results.sort()
    if verbose:
        if not results:
            log('  ✗ 一个都没过 —— 现在连 github.com 的 TLS 都握不上，先把网络弄好。')
        for ms, ip, src in results:
            log('  ✓ %-16s %6.0f ms   (%s)' % (ip, ms, src))
    return results


def read_hosts():
    try:
        with io.open(HOSTS_PATH, encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except Exception as exc:
        return None if not os.path.isfile(HOSTS_PATH) else str(exc)


def strip_our_block(text):
    lines = text.splitlines()
    out, skipping = [], False
    for line in lines:
        if line.strip().startswith(MARK_BEGIN.split('（')[0]):
            skipping = True
            continue
        if skipping and line.strip().startswith(MARK_END.split('（')[0]):
            skipping = False
            continue
        if not skipping:
            out.append(line)
    return '\n'.join(out) + ('\n' if out else '')


def apply_hosts(ips, dry=False):
    """把挑出来的 IP 写进 hosts 的标记段。返回 (成功?, 说明)。"""
    text = read_hosts()
    if text is None:
        return False, '读不到 %s' % HOSTS_PATH
    if isinstance(text, str) and text.startswith('[') and 'Errno' in text:
        return False, text

    block = [MARK_BEGIN]
    for host in PROBE_HOSTS:
        block.append('%-40s %s' % (ips[0], host))
    for extra in ips[1:3]:                       # 备用，防第一条忽然不灵
        block.append('# 备用: %s' % extra)
    block.append(MARK_END)

    new_text = strip_our_block(text).rstrip('\n') + '\n' + '\n'.join(block) + '\n'
    if dry:
        return True, new_text
    try:
        backup = HOSTS_PATH + '.dsh-bak'
        if not os.path.exists(backup):
            with io.open(backup, 'w', encoding='utf-8', errors='replace') as fh:
                fh.write(text)
        with io.open(HOSTS_PATH, 'w', encoding='utf-8', errors='replace') as fh:
            fh.write(new_text)
        subprocess.run(['ipconfig', '/flushdns'], capture_output=True)
        return True, '已写入 %s 并刷新 DNS 缓存（原文件备份在 %s.dsh-bak）' % (HOSTS_PATH, HOSTS_PATH)
    except PermissionError:
        return False, ('没有权限写 hosts（需要以管理员身份运行）。'
                       '挑出来的 IP 仍然可用：用管理员开一个终端再跑一次本脚本即可。')
    except Exception as exc:
        return False, '写 hosts 失败：%s' % exc


def restore_hosts():
    text = read_hosts()
    if isinstance(text, str) and text.startswith('['):
        log('读不到 hosts：%s' % text)
        return 1
    try:
        with io.open(HOSTS_PATH, 'w', encoding='utf-8', errors='replace') as fh:
            fh.write(strip_our_block(text))
        subprocess.run(['ipconfig', '/flushdns'], capture_output=True)
        log('已撤掉 hosts 里 github 那一段，DNS 缓存已刷新。')
        return 0
    except Exception as exc:
        log('撤不掉：%s' % exc)
        return 1


def git(args, check=True):
    proc = subprocess.run(['git', '-C', REPO] + args, capture_output=True, text=True,
                          errors='replace', env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
    if check and proc.returncode != 0:
        log('  ! git %s → %s' % (' '.join(args), (proc.stderr or proc.stdout).strip()[:300]))
    return proc


def ensure_repo():
    """本地必须是 git 仓库、且挂了远程，否则推不了。"""
    if not os.path.isdir(os.path.join(REPO, '.git')):
        return False, ('本地不是 git 仓库（没有 .git）。从 GitHub 下载的源码包就是这样：\n'
                       '    先 `git init && git remote add %s %s`，或者\n'
                       '    `git clone %s .` 到空目录里再覆盖 —— 二选一，别让脚本替你做主。'
                       % (REMOTE, REMOTE_URL, REMOTE_URL))
    remotes = git(['remote'], check=False).stdout.split()
    if REMOTE not in remotes:
        return False, '远程里没有 %s（现有：%s），先 git remote add %s %s' % (
            REMOTE, remotes or '无', REMOTE, REMOTE_URL)
    return True, 'ok'


def push(message):
    ok, why = ensure_repo()
    if not ok:
        log(why)
        return 2
    log('== 提交 ==')
    git(['add', '-A'])
    status = git(['status', '--porcelain'], check=False).stdout.strip()
    if not status:
        log('  工作区没有改动，跳过提交')
    else:
        changed = len(status.splitlines())
        log('  待提交 %d 个文件' % changed)
        if git(['commit', '-m', message], check=False).returncode != 0:
            log('  提交没成功（看上面的报错）')
            return 2
    log('== 推送 ==')
    proc = git(['push', REMOTE, BRANCH], check=False)
    if proc.returncode != 0:
        if 'Could not connect' in (proc.stderr or '') or 'timed out' in (proc.stderr or ''):
            log('  推送连不上 —— 先让本脚本把 hosts 换到能通的 IP 再试一次。')
        return 3
    log('  ✓ 已推到 %s/%s' % (REMOTE, BRANCH))
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    ap = argparse.ArgumentParser(description='扫描 GitHub 可用 IP 并推送')
    ap.add_argument('--scan-only', action='store_true', help='只扫描并打印排行，什么都不改')
    ap.add_argument('--apply-only', action='store_true', help='扫描 + 写 hosts，不碰 git')
    ap.add_argument('--no-push', action='store_true', help='扫描 + 应用 + 提交，但不推')
    ap.add_argument('--restore-hosts', action='store_true', help='撤掉 hosts 里 github 那段')
    ap.add_argument('-m', '--message', default='chore: 自动出货提交', help='提交信息')
    args = ap.parse_args()

    if args.restore_hosts:
        return restore_hosts()

    log('== 扫描 GitHub 可用 IP（TCP 443 + 证书校验）==')
    results = scan()

    if args.scan_only:
        return 0 if results else 1

    if not results:
        log('没有可用 IP：先别推，检查网络/代理。')
        return 1

    ips = [ip for _, ip, _ in results]
    ok, why = apply_hosts(ips)
    log('== 写入 hosts ==')
    log(('  ✓ ' if ok else '  ✗ ') + why)
    if not ok:
        log('  仍然继续尝试推送（也许本机本来就连得上）。')

    if args.apply_only or args.no_push:
        return 0
    return push(args.message)


if __name__ == '__main__':
    raise SystemExit(main())
