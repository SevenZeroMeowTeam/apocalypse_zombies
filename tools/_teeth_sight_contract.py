# -*- coding: utf-8 -*-
"""咬齿测试：1.1.36 新增的「透明镜契约」「观感同源」两类断言改坏时必须 FAIL。

每例只临时改一处、跑校验器、立刻还原，最后断言文件回到原样。
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path('F:/mcmod')
CE = ROOT / 'src/main/java/com/apocalypse/zombies/client/ClientEvents.java'
CB = ROOT / 'src/main/java/com/apocalypse/zombies/item/CrossbowItem.java'
MOCK = ROOT / 'tools/sight_mock.py'

CASES = [
    ('浅晕颜色与 mock 分家', CE, 'RETICLE_HALO_COLOUR = 0xF2F2F2', 'RETICLE_HALO_COLOUR = 0xE0E0E0', '观感不同源'),
    ('镜片透明度与 mock 分家', CE, 'CLEAR_LENS_ALPHA = 0.07F', 'CLEAR_LENS_ALPHA = 0.12F', '观感不同源'),
    ('mock 的暗芯被改', MOCK, 'CORE = (0x10, 0x10, 0x10)', 'CORE = (0x18, 0x18, 0x18)', '观感不同源'),
    ('关掉 hasScopeOverlay', CB, 'public boolean hasScopeOverlay() {\n        return true;',
     'public boolean hasScopeOverlay() {\n        return false;', 'hasScopeOverlay() = false'),
    ('sightStyle 退回望远镜', CB, 'GunItem.SightStyle.CLEAR_SIGHT;', 'GunItem.SightStyle.TELESCOPE;',
     'sightStyle() = TELESCOPE'),
    ('打开 hidesModelWhileAimed', CB, 'public boolean hidesModelWhileAimed() {\n        return false;',
     'public boolean hidesModelWhileAimed() {\n        return true;', 'hidesModelWhileAimed() = true'),
]

ok = True
for label, path, old, new, needle in CASES:
    orig = path.read_text(encoding='utf-8')
    assert old in orig, '找不到要改的片段: %s' % label
    path.write_text(orig.replace(old, new), encoding='utf-8')
    r = subprocess.run([sys.executable, str(ROOT / 'tools/check_crossbow_anim.py')], capture_output=True)
    out = (r.stdout + r.stderr).decode('utf-8', 'replace')
    path.write_text(orig, encoding='utf-8')
    assert path.read_text(encoding='utf-8') == orig, '还原失败: %s' % label
    bit = r.returncode != 0 and needle in out
    ok &= bit
    print('%-26s rc=%-3d 命中 %-28r %s' % (label, r.returncode, needle, 'OK' if bit else '!! 没咬住'))
print('咬齿测试', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
