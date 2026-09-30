"""网易 Java 版（中国版）出货：构建 → 包内自检 → 把「模组 jar + 依赖 jar」并列装进网易客户端 mods/。

⚠ 为什么依赖必须**并列装**、而不能内嵌（jar-in-jar）
------------------------------------------------------
网易中国版 Java 版 1.20 = **MC 1.20.1 + Forge 47.3.0**，ModLauncher 是魔改的
`MinecraftChina_10.1.40fc820b`；它的 mods/ 由平台分发，**没有 GeckoLib，玩家也装不了第三方库**。
mods.toml 里那条 `mandatory=true` 的 geckolib 依赖因此必须先解决，两条路的真机结果：

  ✗ 把 GeckoLib 打进 `META-INF/jarjar/`（jar-in-jar）→ 客户端**静默退出**：
    日志停在 oshi/JNA 初始化，**无异常栈 / 无 hs_err_pid / 无 Windows 崩溃事件**；
    把包移走即恢复正常（对照实验，见 docs/wiki/10-网易Java版适配.md）。
  ✓ mods/ 里并列一个顶层 `geckolib-forge-1.20.1-x.y.z.jar` → 正常加载并游玩。

而且顶层 jar 在的时候，Forge 的 JarSelector 会优先用它，连包里的内嵌副本都不碰：

    JarSelector: Attempted to select a dependency jar for JarJar which was passed in as source:
                 geckolib. Using Mod File: ...\\mods\\geckolib-forge-1.20.1-4.8.4.jar

所以本脚本同时装两个 jar，并把「本模组 jar 内不得含 jarjar」当作硬断言。

验收项（全部为硬断言，任一不过就退出码非 0）
--------------------------------------------
 1. 两个产物都存在：`apocalypse_zombies-<ver>-netease.jar`（`neteaseJar` 改名出的网易产物）
    与 `geckolib-forge-1.20.1-<glver>.jar`（`neteaseLibs` 导出的依赖），都在 build/netease/。
    `-netease.jar` 与 build/libs/ 的开发包**逐字节相同**（Copy 任务只改名），本脚本会核对 md5。
 2. 本模组 jar **不含** `META-INF/jarjar/`（含了就会静默退出）；其 `mods.toml` 仍声明
    `geckolib` 且 `mandatory=true` —— 这正是依赖必须并列装的理由。
 3. 依赖 jar 身份自洽：modId 是 `geckolib`、版本等于 `gradle.properties` 的 `geckolib_version`、
    抽样含 SRG 符号（证明拿的是线上生产版而不是开发编译版）、自带 `LICENSE`（MIT 随包义务）。
 4. 部署：网易 mods/ 里旧的 `apocalypse_zombies-*` / `geckolib-*` 全部挪到 **mods/ 同级**
    的 `mods_backup/`（保 3 份；**备份绝不放进 mods/** —— Forge 递归扫描会加载重复模组），
    拷入两个新包后逐字节复核 md5，最后断言只剩这一个模组 + 一个依赖。

用法
----
    python tools/deploy_netease.py              # 构建 + 自检 + 部署
    python tools/deploy_netease.py --no-build   # 只做出货与部署（复用已有产物）

装完由 MCStudio 启动一次 Java 版 1.20 客户端，再回读 **DEBUG 级**日志验收
（`logs/latest.log` 是 INFO 级，**永远没有**模组发现段 —— 拿它判断会误判成「模组没加载」）：

    logs/debug-N.log.gz      # 最新一份（客户端完全退出后才会写完整）

**通过标准（两条）**：`Found valid mod file apocalypse_zombies-<ver>-netease.jar`
+ `Found 0 mod requirements missing (0 mandatory, 0 optional)`；
反例是 `Missing or unsupported mandatory dependencies: ... 'geckolib'`。
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBS = os.path.join(ROOT, 'build', 'libs')          # 开发包（jar / reobfJar 产出，用来核对同源）
LIBS_DEP = os.path.join(ROOT, 'build', 'netease')   # 网易产物目录（neteaseJar + neteaseLibs 产出）

# 网易中国版 Java 版客户端（MCStudio 下载目录）；换机器只改这两行
NET_MC = 'F:/MCStudioDownload/game/.minecraft'
NET_MODS = NET_MC + '/mods'
LOG = NET_MC + '/logs/latest.log'

PREFIX = 'apocalypse_zombies-'
MOD_ID = 'apocalypse_zombies'
REQUIRED_DEP = 'geckolib'
SRG_RE = re.compile(r'[mfy]_\d{3,}_')

FAILURES = []
CHECKS = 0


def check(ok, label, detail=''):
    """记一次判定。判据是"全过"，所以失败只记账、最后统一汇总。"""
    global CHECKS
    CHECKS += 1
    mark = 'OK  ' if ok else 'FAIL'
    print('  [%s] %s%s' % (mark, label, ('  —— ' + detail) if detail else ''))
    if not ok:
        FAILURES.append(label)
    return ok


def md5(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def read_version():
    """版号只认 gradle.properties —— 与 jar 名同源，避免两处手写漂移。"""
    with open(os.path.join(ROOT, 'gradle.properties'), encoding='utf-8') as f:
        for line in f:
            m = re.match(r'\s*mod_version\s*=\s*(\S+)', line)
            if m:
                return m.group(1)
    raise SystemExit('gradle.properties 里找不到 mod_version')


def read_geckolib_version():
    with open(os.path.join(ROOT, 'gradle.properties'), encoding='utf-8') as f:
        for line in f:
            m = re.match(r'\s*geckolib_version\s*=\s*(\S+)', line)
            if m:
                return m.group(1)
    raise SystemExit('gradle.properties 里找不到 geckolib_version')


def build():
    print('== 1/4 构建 ==')
    gradlew = os.path.join(ROOT, 'gradlew.bat' if os.name == 'nt' else 'gradlew')
    # jar: 本模组（reobfJar 会跟着跑）；neteaseJar: 改名为 -netease.jar 落 build/netease/；
    # neteaseLibs: 把 GeckoLib 的**生产版**导出到 build/netease/
    # 先带 --offline：生产版一般已在 Gradle 缓存里。实测联网解析会挂在上游 CDN 的 443 上
    # （4 分钟零进展），缓存命中时只要 23 秒。离线失败（缓存里没有）才退回联网。
    cmd = [gradlew, 'jar', 'neteaseJar', 'neteaseLibs', '--console=plain', '--offline']
    print('  $ ' + ' '.join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        print('  !! 离线构建失败（多半是缓存里没有 GeckoLib 生产版）→ 退回联网重试，可能长时间卡在网络上')
        cmd = [c for c in cmd if c != '--offline']
        print('  $ ' + ' '.join(cmd))
        r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit('构建失败（退出码 %d）' % r.returncode)


def inspect(jar_path, dev_jar_path, dep_path, geckolib_version):
    """包内自检：本模组 jar 必须干净（无 jar-in-jar），依赖 jar 必须身份正确。"""
    print('== 2/4 包内自检 ==')
    if os.path.isfile(dev_jar_path):
        check(md5(jar_path) == md5(dev_jar_path), '-netease 产物与开发包逐字节相同',
              'neteaseJar 只改名不改内容（md5 %s）' % md5(jar_path)[:12])
    else:
        check(False, '开发包在场（用来核对 -netease 产物同源）', dev_jar_path)
    with zipfile.ZipFile(jar_path) as z:
        names = set(z.namelist())
        # 硬断言：网易客户端一旦真的去用包内 jarjar 就会静默退出
        jarjar = sorted(n for n in names if n.startswith('META-INF/jarjar/'))
        check(not jarjar, '本模组 jar 不含 jar-in-jar（网易客户端会静默退出）',
              ', '.join(jarjar[:3]) if jarjar else '干净')
        toml_out = z.read('META-INF/mods.toml').decode('utf-8', 'replace').replace(' ', '')
        check('modId="%s"' % MOD_ID in toml_out, '包内 mods.toml 的 modId == %s' % MOD_ID)
        check('modId="%s"' % REQUIRED_DEP in toml_out,
              'mods.toml 仍声明 %s 依赖（所以要并列装它）' % REQUIRED_DEP)
        check(re.search(r'modId="%s"\s*\n\s*mandatory=true' % REQUIRED_DEP, toml_out) is not None,
              '%s 依赖仍是 mandatory=true' % REQUIRED_DEP)

    if not check(os.path.isfile(dep_path), '依赖 jar 存在', dep_path):
        return
    with zipfile.ZipFile(dep_path) as z:
        names = set(z.namelist())
        has_toml = 'META-INF/mods.toml' in names
        check(has_toml, '依赖 jar 是有效 mod 包（含 mods.toml）', os.path.basename(dep_path))
        toml = z.read('META-INF/mods.toml').decode('utf-8', 'replace') if has_toml else ''
        mod_id = re.search(r'(?m)^\s*modId\s*=\s*"([^"]+)"', toml)
        ver_id = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', toml)
        check(bool(mod_id) and mod_id.group(1) == REQUIRED_DEP,
              '依赖 jar 的 modId == %s' % REQUIRED_DEP, mod_id.group(1) if mod_id else '读不到')
        check(bool(ver_id) and ver_id.group(1) == geckolib_version,
              '依赖 jar 版本 == gradle.properties 的 geckolib_version', geckolib_version)
        hits = 0
        for n in [x for x in names if x.endswith('.class')][:40]:
            if SRG_RE.search(z.read(n).decode('latin-1')):
                hits += 1
        check(hits > 0, '依赖 jar 是线上生产版（抽样含 SRG 符号）',
              '40 个 class 中 %d 个含 m_/f_/y_ 编号符号' % hits)
        check('LICENSE' in names, '依赖 jar 自带 LICENSE（MIT 随包义务随之满足）')
        # 依赖包的身份：**md5 不是稳定指纹** —— 上游 4.8.4 存在两个构建（443 条目逐字节相同，
        # 只有 manifest 的 Implementation-Timestamp 相差 47 秒）。核验认「条目数 + 时间戳 + modId/版本」。
        mf = z.read('META-INF/MANIFEST.MF').decode('utf-8', 'replace') if 'META-INF/MANIFEST.MF' in names else ''
        ts = re.search(r'Implementation-Timestamp:\s*(\S+)', mf)
        print('  依赖包身份：%d 条目 · %s · md5 %s'
              % (len(names), ts.group(1) if ts else '(无 Implementation-Timestamp)', md5(dep_path)))


def deploy(jar_paths):
    """装载到网易客户端：同名的旧包先挪到 **mods/ 同级** 的 mods_backup/（保 3 份）。
    备份绝不放进 mods/ —— Forge 会递归扫描该目录，重复模组直接崩。
    两个包必须**同时**在场：本模组是 mandatory 依赖 geckolib，缺一个就加载失败。"""
    print('== 3/4 部署到网易客户端 ==')
    if not os.path.isdir(NET_MODS):
        raise SystemExit('找不到网易客户端 mods/：%s' % NET_MODS)

    backup_dir = os.path.join(os.path.dirname(os.path.abspath(NET_MODS)), 'mods_backup')
    expected = {os.path.basename(p) for p in jar_paths}
    moved = []
    for name in sorted(os.listdir(NET_MODS)):
        if name.endswith('.jar') and (name.startswith(PREFIX) or name.startswith('geckolib-')):
            src = os.path.join(NET_MODS, name)
            if not os.path.isdir(backup_dir):
                os.makedirs(backup_dir)
            dst = os.path.join(backup_dir, name)
            if os.path.exists(dst):
                os.remove(dst)
            try:
                shutil.move(src, dst)
            except PermissionError:
                # 游戏没退出时 jar 被进程持久持有（禁删/改名，但允许写入）——
                # 此时绝不能继续拷新包：新旧同 modId 并存会让客户端重复 mod 直接崩
                check(False, '旧包挪不动（游戏可能还在运行）', name + ' —— 请完全退出客户端后重跑')
                return
            moved.append(name)
    # mods_backup/ 只保 3 份（按修改时间留最新）
    if os.path.isdir(backup_dir):
        olds = sorted((os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith('.jar')),
                      key=lambda p: os.path.getmtime(p), reverse=True)
        for p in olds[3:]:
            os.remove(p)
    print('  挪走旧包：%s%s' % (', '.join(moved) if moved else '（无）',
                            '   →  备份在 %s' % backup_dir if moved else ''))

    for p in jar_paths:
        dst = os.path.join(NET_MODS, os.path.basename(p))
        shutil.copy2(p, dst)
        check(md5(p) == md5(dst), '部署后 md5 一致', os.path.basename(dst))
        print('  装入：%s' % os.path.basename(dst))

    present = {n for n in os.listdir(NET_MODS)
               if n.endswith('.jar') and (n.startswith(PREFIX) or n.startswith('geckolib-'))}
    check(present == expected, 'mods/ 里恰好是这一个模组 + 一个依赖 jar',
          ', '.join(sorted(present)) or '（无）')


def main():
    print('网易 Java 版出货（中国版 1.20 = MC 1.20.1 + Forge 47.3.0）')
    version = read_version()
    geckolib_version = read_geckolib_version()
    jar_name = '%s%s-netease.jar' % (PREFIX, version)
    dev_jar = os.path.join(LIBS, '%s%s.jar' % (PREFIX, version))
    dep_name = 'geckolib-forge-1.20.1-%s.jar' % geckolib_version
    jar_path = os.path.join(LIBS_DEP, jar_name)
    dep_path = os.path.join(LIBS_DEP, dep_name)
    print('  两个产物：%s  +  %s' % (jar_name, dep_name))

    if '--no-build' not in sys.argv:
        build()
    else:
        print('== 1/4 构建 ==  （--no-build，跳过）')

    if not check(os.path.isfile(jar_path), '模组产物存在', jar_path):
        finish()
        return
    inspect(jar_path, dev_jar, dep_path, geckolib_version)
    if not os.path.isfile(dep_path):
        finish()
        return
    deploy([jar_path, dep_path])

    print('== 4/4 验收指引 ==')
    print('  1) MCStudio 里启动一次 Java 版 1.20 客户端（Forge 没有热重载，必须完全退出再开）')
    print('  2) 回读 **DEBUG 级**日志（latest.log 是 INFO 级，永远没有模组发现段）：')
    print('     %s/debug-N.log.gz（按修改时间取最新一份）' % os.path.dirname(LOG).replace('\\', '/'))
    print('     通过标准(两条)：Found valid mod file %s  +  Found 0 mod requirements missing' % jar_name)
    print('     反例 = Missing or unsupported mandatory dependencies ... \'geckolib\'')
    finish()


def finish():
    print('-' * 68)
    if FAILURES:
        print('结果：%d 项判定中 %d 项失败' % (CHECKS, len(FAILURES)))
        for f in FAILURES:
            print('  ✗ ' + f)
        sys.exit(1)
    print('结果：%d 项判定全过 ✓' % CHECKS)


if __name__ == '__main__':
    main()
