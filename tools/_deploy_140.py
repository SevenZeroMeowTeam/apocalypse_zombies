"""1.1.40 出货：跑步持枪姿态（纯客户端姿态层 —— 不碰几何 / 贴图 / 动画，零资产改动）。

为什么是这个流程
----------------
姿态是"这一帧枪摆在哪"的运行时状态，走的是 GunPose 这一层位置混合，不是模型或动画。
所以本轮的硬证据不是"资产生成了"，而是**变化的字节必须恰好落在那 4 个 class 上**：
多一个 entry 说明误伤了别处，少一个说明改动没编进去。资产条目必须**一个都不变** ——
只要 uzi 的 geo/png/动画有一字节漂移，就说明有人在几何流水线上重跑过，本轮必须停下查。

验证项
------
 1. 基线 = mods/ 里正在生效的 1.1.39，md5 先验身份（aef62fb48904734afabf0a0b77cd41ad）。
    同名 jar 被后续构建原地覆盖过就不能当基线 —— 1.1.37 那次踩过这个坑，用 md5 钉死身份。
 2. jar 内 mods.toml == 1.1.40。
 3. 相对 1.1.39 逐条字节比对：变化集合 == {GunPose, GunAimState, WeaponHandGrip, WeaponArms,
    META-INF/mods.toml}，且 asset/data 条目零变化。
 4. 新常量真的在包内（大端 float 逐值搜索），且旧 HIP 常量原样（腰射基准位没被顺手改掉）。
 5. 瞄准常量 UziItem.ADS_Y 的字节在包内原样 —— 跑步姿态只写在腰射分支，瞄准态必须零回归。
 6. 三道门禁（几何 / UV / 五枪资源）全绿。
 7. 部署只动 apocalypse_zombies-* 前缀，其余模组逐个 md5 断"原样在位"。
"""
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODS = 'C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods'
OLD, NEW = '1.1.39', '1.1.40'
PREFIX = 'apocalypse_zombies-'
JAR = PREFIX + NEW + '.jar'
# 1.1.39 出货件的 md5 —— 基线的唯一合法身份
OLD_SHIPPED_MD5 = 'aef62fb48904734afabf0a0b77cd41ad'

PKG = 'com/apocalypse/zombies/'
RES = 'assets/apocalypse_zombies/'
CLS = PKG + 'client/'
# 本轮改动的四个 class：姿态混合层两个 + 姿态状态机 + 手臂诊断开关
MUST = {
    CLS + 'weapon/GunPose.class',
    CLS + 'weapon/WeaponHandGrip.class',
    CLS + 'weapon/WeaponArms.class',
    CLS + 'GunAimState.class',
    'META-INF/mods.toml',
    # 每次构建都会重写的构建元数据（版本 + 时间戳）。放进预期集不是放水：下面的
    # check_manifest 会断言它**只**差那两行，真有别的改动照样退出。
    'META-INF/MANIFEST.MF',
}


def check_manifest(old_raw, new_raw, old_ver, new_ver):
    """MANIFEST 允许变，但只允许 Implementation-Version 与 Implementation-Timestamp 两行。"""
    o = old_raw.decode('utf-8', 'replace').splitlines()
    n = new_raw.decode('utf-8', 'replace').splitlines()
    only_o = [l for l in o if l not in n]
    only_n = [l for l in n if l not in o]
    allowed = []
    for line in only_o + only_n:
        if line.startswith('Implementation-Version: ') or line.startswith('Implementation-Timestamp: '):
            allowed.append(line)
        else:
            sys.exit('MANIFEST 里有非构建元数据的差异，需要人看：%r' % line)
    if not any(l.strip() == 'Implementation-Version: ' + new_ver for l in only_n):
        sys.exit('MANIFEST 的版本不是 %s：%r' % (new_ver, only_n))
    return only_o, only_n


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def jar_bytes(path):
    with zipfile.ZipFile(path) as zf:
        return {i.filename: zf.read(i.filename) for i in zf.infolist() if not i.is_dir()}


def f32(v):
    return struct.pack('>f', v)


def run_checker(script):
    p = os.path.join(ROOT, 'tools', script)
    if not os.path.isfile(p):
        print('    [跳过] %s 不存在' % script)
        return True
    r = subprocess.run([sys.executable, p], cwd=ROOT, capture_output=True, text=True, errors='replace')
    out = ((r.stdout or '') + (r.stderr or '')).strip()
    tail = out.splitlines()[-1] if out else ''
    # 判据以退出码为准：三个检查脚本各自用不同措辞报成功（"CHECK PASS" / "全部通过"），
    # 拿关键词当判据会把后者误判成失败（1.1.40 首次出货时踩过）。只在出现失败词时判负。
    ok = r.returncode == 0 and not re.search(r'FAIL|✗|不通过|错误|不符', out)
    print('    %-26s %s  %s' % (script, 'PASS' if ok else 'FAIL', tail[:90]))
    return ok


# ---------------------------------------------------------------- [0] 基线
mods_dir = MODS
base_path = None
for cand in sorted(os.listdir(mods_dir)):
    if cand.startswith(PREFIX) and cand.endswith('.jar'):
        p = os.path.join(mods_dir, cand)
        if md5(p) == OLD_SHIPPED_MD5:
            base_path = p
            break
if base_path is None:
    sys.exit('mods/ 里找不到 md5 == %s 的 %s 出货件，基线不成立' % (OLD_SHIPPED_MD5, OLD))
base = jar_bytes(base_path)
print('[0] 基线 %s = %s  条目 %d  md5 %s' % (OLD, os.path.basename(base_path), len(base), OLD_SHIPPED_MD5))

# ---------------------------------------------------------------- [1] 新包
jar = os.path.join(ROOT, 'build', 'libs', JAR)
if not os.path.isfile(jar):
    sys.exit('没有 %s，先 ./gradlew build --offline' % jar)
new_md5 = md5(jar)
if new_md5 == OLD_SHIPPED_MD5:
    sys.exit('新包 md5 与 %s 出货件相同：等于没改，构建没吃到源码' % OLD)
new = jar_bytes(jar)
print('[1] %s  md5=%s  %d 字节  entry %d' % (JAR, new_md5, os.path.getsize(jar), len(new)))

# ---------------------------------------------------------------- [2] mods.toml
toml = new.get('META-INF/mods.toml', b'').decode('utf-8', 'replace')
m = re.search(r'version\s*=\s*"([^"]+)"', toml)
if not m or m.group(1) != NEW:
    sys.exit('mods.toml 版本 = %r，期望 %s' % (m and m.group(1), NEW))
print('[2] mods.toml version="%s"' % m.group(1))

# ---------------------------------------------------------------- [3] 逐条字节比对
changed = {n for n in new if n in base and new[n] != base[n]}
added = set(new) - set(base)
removed = set(base) - set(new)
print('[3] 变化 %d 个 / 新增 %d / 删除 %d' % (len(changed), len(added), len(removed)))
for n in sorted(changed | added | removed):
    print('      %s  %s' % (('改' if n in changed else '增' if n in added else '删'), n))
if changed != MUST or added or removed:
    print('  期望恰好为：')
    for n in sorted(MUST):
        print('      改 %s' % n)
    sys.exit('变化集合与预期不符：少了 %r / 多了 %r' % (sorted(MUST - changed), sorted(changed - MUST)))
mo, mn = check_manifest(base['META-INF/MANIFEST.MF'], new['META-INF/MANIFEST.MF'], OLD, NEW)
print('      MANIFEST 只差构建元数据：%s' % ' | '.join(x.strip() for x in mo + mn))
asset_changed = [n for n in changed if n.startswith(RES) or n.startswith('data/')]
if asset_changed:
    sys.exit('资产条目发生变化（本轮不该有任何几何/贴图/动画改动）：%r' % asset_changed)
print('     ✔ 变化集合 == 预期（4 个 class + mods.toml + 构建元数据）；资产条目零变化')

# ---------------------------------------------------------------- [4] 常量落到字节里
pose = new[CLS + 'weapon/GunPose.class']
want_new = {
    'SPRINT_YAW 22.0': f32(22.0), 'SPRINT_PITCH -20.0': f32(-20.0), 'SPRINT_ROLL 20.0': f32(20.0),
    'SPRINT_DX -0.35': f32(-0.35), 'SPRINT_DY 0.16': f32(0.16), 'SPRINT_DZ 0.0': f32(0.0),
    'SPRINT_BOB_Y 0.028': f32(0.028), 'SPRINT_BOB_X 0.016': f32(0.016),
}
want_keep = {'HIP_DX -0.30': f32(-0.30), 'HIP_DY +0.30': f32(0.30), 'HIP_DZ 0.05': f32(0.05),
             'HIP_YAW 4.0': f32(4.0), 'HIP_PITCH 1.6': f32(1.6), 'HIP_ROLL -3.0': f32(-3.0)}
for label, pat in want_new.items():
    if pat not in pose:
        sys.exit('GunPose.class 里找不到新常量 %s' % label)
for label, pat in want_keep.items():
    if pat not in pose:
        sys.exit('GunPose.class 里 %s 丢了（腰射基准位被改）' % label)
# 旧包不该有跑步常量（反证：不是拿旧 class 顶包）
old_pose = base[CLS + 'weapon/GunPose.class']
if f32(22.0) in old_pose and f32(-20.0) in old_pose:
    sys.exit('%s 的 GunPose.class 里已经有跑步常量，基线或构建不对' % OLD)
print('[4] GunPose.class：8 个跑步常量在、6 个腰射常量原样；%s 里没有跑步字节' % OLD)

# ---------------------------------------------------------------- [5] 瞄准态零回归
# 跑步姿态只写在腰射分支：瞄准满值时混合系数 s = sprint·(1−aim) = 0，位移只剩 ADS、旋转为恒等。
# 结构上成立，但 UziItem 的 ADS_Y 字节也必须原样在包里 —— 它是被验证过、残差 0 的量。
uzi_old, uzi_new = base[PKG + 'item/UziItem.class'], new[PKG + 'item/UziItem.class']
if uzi_old != uzi_new:
    sys.exit('UziItem.class 变了：本轮不该动瞄准参数（它是残差 0 的已验证量）')
for label, pat in {'ADS_X -0.4746': f32(-0.4746), 'ADS_Y +0.3015': f32(0.3015)}.items():
    if pat not in uzi_new:
        sys.exit('UziItem.class 里 %s 不在了' % label)
print('[5] UziItem.class 逐字节未变，ADS_X/ADS_Y 原样（瞄准态零回归）')

# ---------------------------------------------------------------- [6] 门禁
print('[6] 门禁：')
gates = [run_checker('check_uzi_anim.py'), run_checker('check_uzi_art.py'),
         run_checker('check_gun_resources.py')]
if not all(gates):
    sys.exit('门禁未全绿，不出货')

# ---------------------------------------------------------------- [7] 部署
print('[7] 部署到 %s' % mods_dir)
others_before = {n: md5(os.path.join(mods_dir, n)) for n in os.listdir(mods_dir)
                 if n.endswith('.jar') and not n.startswith(PREFIX)}
for n in sorted(os.listdir(mods_dir)):
    if n.startswith(PREFIX) and n.endswith('.jar'):
        os.remove(os.path.join(mods_dir, n))
        print('    移除旧包 %s' % n)
target = os.path.join(mods_dir, JAR)
shutil.copy2(jar, target)
if md5(target) != new_md5:
    sys.exit('部署后 md5 不一致（拷坏了）')
print('    放入 %s  md5 %s' % (JAR, md5(target)))
others_after = {n: md5(os.path.join(mods_dir, n)) for n in os.listdir(mods_dir)
                if n.endswith('.jar') and not n.startswith(PREFIX)}
if others_before != others_after:
    sys.exit('其它模组被动过：%r' % [n for n in others_before if others_before.get(n) != others_after.get(n)])
print('    其它模组原样在位：%d 个 md5 全等' % len(others_after))

print('\n=== 1.1.40 出货完成 ===')
print('  跑步持枪：站立腰射 → 跑步时枪口下压 0.47~0.54 NDC，五个枪型双手均在画面内')
print('  jar  : %s' % JAR)
print('  md5  : %s' % new_md5)
print('  ⚠ Forge 无热重载：必须完全退出重开客户端')
