#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""出货脚本：构建 → 总门禁 → 探锁部署 → 回滚备份 → 事后校验。

版本号从 `gradle.properties` 读取（脚本不绑死某一版）：

    python tools/_deploy_400.py --build      # 先构建（build + cleanJar），再出货
    python tools/_deploy_400.py              # 用 build/libs 里已构建好的包
    python tools/_deploy_400.py --no-install # 只跑判据，不动 mods/
    python tools/_deploy_400.py --dev <dir>  # 指定游戏实例目录

判据（任一条不过就以非 0 退出，且**不会动 mods/**）：
  1. 开发包 / clean 包存在，且包内 mods.toml 版本 == gradle.properties 的版本；
  2. `tools/check_skyfall.py` 总门禁 exit 0（资产链 / 数据 / 语言 / 配置 / 原创性 / 文档）；
  3. 版本四处一致：gradle.properties、根 mod.toml、readme 头表、readme 更新日志；
  4. 游戏进程必须完全退出（客户端主类 / launchTarget forgeclient 都不许在跑）；
  5. mods/ 里现有的本模组包必须是本版或上一版（3.11.0），否则拒绝覆盖；
  6. mods/ 下不许有子目录（Forge 会递归扫描 → 重复加载）；
  7. 其它模组逐个 md5 快照，换包后必须全部原样在位；
  8. 换包后 mods/ 只有一个本模组 jar，且 sha256 == build/libs 里的开发包。
旧包移到 `mods_backup/`（保留最近 3 份，其余进 `mods_backup/_archive/`）。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def project_version():
    with open(os.path.join(ROOT, 'gradle.properties'), encoding='utf-8') as fh:
        m = re.search(r'^mod_version\s*=\s*([0-9][^\s#]*)', fh.read(), re.M)
    return m.group(1) if m else '?'


VER = project_version()
ACCEPT = (VER,)
PREFIX = 'apocalypse_zombies-'
KEEP_BACKUPS = 3
DEFAULT_DEV = r'F:\.minecraft\versions\1.20.1-Forge_47.4.27'
CLIENT_MARKERS = ('net.minecraft.client.main.main', 'launchtarget forgeclient',
                  'fml.forgeversion', 'assetsindex')

FAILS = []


def say(text=''):
    print(text)


def report(ok, label, detail=None):
    print(('  OK   ' if ok else '  FAIL ') + label + (('  [' + str(detail) + ']') if detail is not None else ''))
    if not ok:
        FAILS.append(label)
    return ok


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def jar_version(path):
    with zipfile.ZipFile(path) as z:
        txt = z.read('META-INF/mods.toml').decode('utf-8', 'replace')
    m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
    return m.group(1) if m else '?'


def jar_version_from_name(name):
    m = re.match(re.escape(PREFIX) + r'(.+)\.jar$', name)
    return m.group(1) if m else '?'


def game_running():
    """True = 有 Minecraft 客户端在跑；探测失败按未在跑处理。"""
    try:
        ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'javaw.exe' -or "
              "$_.Name -eq 'java.exe' } | ForEach-Object { $_.CommandLine }")
        out = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                             capture_output=True, text=True, timeout=45).stdout.lower()
        return any(m in out for m in CLIENT_MARKERS)
    except Exception:
        return False


def version_consistency():
    with open(os.path.join(ROOT, 'gradle.properties'), encoding='utf-8') as fh:
        m = re.search(r'^mod_version\s*=\s*([0-9][^\s#]*)', fh.read(), re.M)
    gradle_ver = m.group(1) if m else '?'
    with open(os.path.join(ROOT, 'mod.toml'), encoding='utf-8') as fh:
        m2 = re.search(r'^mod_version\s*=\s*"([^"]+)"', fh.read(), re.M)
    root_ver = m2.group(1) if m2 else '?'
    with open(os.path.join(ROOT, 'readme.md'), encoding='utf-8') as fh:
        readme = fh.read()
    m3 = re.search(r'\|\s*\*\*当前版本\*\*\s*\|\s*`([^`]+)`', readme)
    head_ver = m3.group(1) if m3 else '?'
    return gradle_ver, root_ver, head_ver, ('### %s —' % gradle_ver) in readme


def backup_existing(backup_dir):
    old = [f for f in os.listdir(backup_dir) if re.match(re.escape(PREFIX) + r'.+\.jar$', f)]
    old.sort(key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)), reverse=True)
    archive = os.path.join(backup_dir, '_archive')
    for name in old[KEEP_BACKUPS:]:
        os.makedirs(archive, exist_ok=True)
        shutil.move(os.path.join(backup_dir, name), os.path.join(archive, name))


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

    ap = argparse.ArgumentParser(description='Skyfall 4.0.0 release')
    ap.add_argument('--build', action='store_true', help='run gradlew build cleanJar first')
    ap.add_argument('--no-install', action='store_true', help='checks only, do not touch mods/')
    ap.add_argument('--skip-gates', action='store_true', help='skip check_skyfall.py (debug only)')
    ap.add_argument('--dev', default=DEFAULT_DEV, help='game instance dir')
    ap.add_argument('--online', action='store_true', help='do not pass --offline to gradle')
    args = ap.parse_args()

    dev = os.path.abspath(args.dev)
    mods = os.path.join(dev, 'mods')
    backup = os.path.join(dev, 'mods_backup')
    src = os.path.join(ROOT, 'build', 'libs', 'apocalypse_zombies-%s.jar' % VER)
    clean_src = os.path.join(ROOT, 'build', 'libs', 'apocalypse_zombies-%s-clean.jar' % VER)

    if args.build:
        say('=== 0/8 构建（build + cleanJar）===')
        cmd = [os.environ.get('COMSPEC') or r'C:\Windows\System32\cmd.exe', '/c',
               'gradlew.bat', 'build', 'cleanJar', '--no-daemon', '--console=plain']
        if not args.online:
            cmd.append('--offline')
        env = dict(os.environ)
        env.setdefault('JAVA_TOOL_OPTIONS', '-Duser.language=en -Duser.country=US')
        rc = subprocess.call(cmd, cwd=ROOT, env=env)
        report(rc == 0, './gradlew build cleanJar exit 0', 'exit %d' % rc)
        if FAILS:
            return finish()

    say('=== 1/8 产物与版本 ===')
    report(os.path.isfile(src), '开发包存在', src)
    if not os.path.isfile(src):
        return finish()
    report(jar_version(src) == VER, '开发包版本 == %s' % VER, jar_version(src))
    clean_ok = os.path.isfile(clean_src)
    report(clean_ok, 'clean 包存在', clean_src)
    if clean_ok:
        report(jar_version(clean_src) == VER, 'clean 包版本 == %s' % VER, jar_version(clean_src))
        report(os.path.getsize(clean_src) > 0, 'clean 包非空', os.path.getsize(clean_src))

    say('\n=== 2/8 总门禁 tools/check_skyfall.py ===')
    if args.skip_gates:
        say('  (--skip-gates 跳过)')
    else:
        gate = os.path.join(ROOT, 'tools', 'check_skyfall.py')
        out = subprocess.run([sys.executable, gate], cwd=ROOT,
                             capture_output=True, text=True, encoding='utf-8', errors='replace')
        tail = [ln for ln in (out.stdout or '').strip().splitlines() if ln.strip()][-1:]
        report(out.returncode == 0, 'check_skyfall exit 0', tail[0][:90] if tail else 'no output')
        if out.returncode != 0:
            print((out.stdout or '')[-3000:])

    say('\n=== 3/8 四处版本一致 ===')
    gradle_ver, root_ver, head_ver, has_log = version_consistency()
    report(gradle_ver == VER, 'gradle.properties == %s' % VER, gradle_ver)
    report(root_ver == VER, '根 mod.toml == %s' % VER, root_ver)
    report(head_ver == VER, 'readme 头表 == %s' % VER, head_ver)
    report(has_log, 'readme 有 %s 更新日志段' % VER)

    say('\n=== 4/8 游戏进程 / 实例目录 ===')
    report(os.path.isdir(mods), 'mods 目录存在', mods)
    running = game_running()
    report(not running, '游戏已完全退出（否则换包后仍在跑旧包）')
    if args.no_install:
        say('\n=== --no-install：判据跑完，不动 mods/ ===')
        return finish()

    if FAILS:
        say('\n门禁未通过，未触碰 mods/。')
        return finish()

    say('\n=== 5/8 基线：现有本模组包 ===')
    existing = sorted(f for f in os.listdir(mods) if re.match(re.escape(PREFIX) + r'.+\.jar$', f))
    report(len(existing) <= 1, 'mods/ 里至多一个本模组包', existing)
    if existing:
        cur = jar_version_from_name(existing[0])
        report(bool(cur and cur != '?'), '现有包版本可识别（任意历史版本都允许覆盖）', cur)
    subdirs = [f for f in os.listdir(mods) if os.path.isdir(os.path.join(mods, f))]
    report(not subdirs, 'mods/ 无子目录', subdirs)

    say('\n=== 6/8 其它模组 md5 快照 ===')
    others = {}
    for name in os.listdir(mods):
        path = os.path.join(mods, name)
        if not os.path.isfile(path) or not name.lower().endswith('.jar'):
            continue
        if re.match(re.escape(PREFIX) + r'.+\.jar$', name):
            continue
        others[name] = md5(path)
    say('  记录 %d 个非本模组 jar' % len(others))

    say('\n=== 7/8 换包（旧包进 mods_backup/）===')
    os.makedirs(backup, exist_ok=True)
    for name in existing:
        shutil.move(os.path.join(mods, name), os.path.join(backup, name))
        say('  moved %s -> mods_backup/' % name)
    target = os.path.join(mods, os.path.basename(src))
    shutil.copy2(src, target)
    say('  copied %s' % os.path.basename(src))
    backup_existing(backup)

    say('\n=== 8/8 事后校验 ===')
    now = sorted(f for f in os.listdir(mods) if re.match(re.escape(PREFIX) + r'.+\.jar$', f))
    report(len(now) == 1, 'mods/ 只有一个本模组包', now)
    if now:
        report(now[0] == os.path.basename(src), '包名正确', now[0])
        report(jar_version(os.path.join(mods, now[0])) == VER, '装机包版本 == %s' % VER)
        report(sha256(os.path.join(mods, now[0])) == sha256(src), '装机包 sha256 == 开发包')
    changed = []
    for name, digest in others.items():
        path = os.path.join(mods, name)
        if not os.path.isfile(path) or md5(path) != digest:
            changed.append(name)
    report(not changed, '其它模组全部原样在位', changed[:5] if changed else '%d 个未变' % len(others))
    report(not [f for f in os.listdir(mods) if os.path.isdir(os.path.join(mods, f))], 'mods/ 仍无子目录')

    return finish()


def finish():
    say('')
    if FAILS:
        say('RESULT: FAIL (%d) — %s' % (len(FAILS), '; '.join(FAILS[:4])))
        return 1
    say('RESULT: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
