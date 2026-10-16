#!/usr/bin/env python3
"""把 tools/win94_gen2.py 产出的骨骼表 / 方块表**通过 blockbench-mcp** 建进当前工程。

顺序：脱开 animate 模式（tools/_bb_pre_edit.js）→ 清空旧方块与旧骨骼 →
add_groups（16 根骨骼）→ 按骨骼分批 add_cubes（208 块）。
所有写操作都走 MCP 桥（127.0.0.1:8787 /command），不直接改 bbmodel 文件。

用法：
  python tools/win94_apply.py            # 全量重建
  python tools/win94_apply.py --no-clear # 只补方块（调试用）
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import bbmcp  # noqa: E402

OUT = ROOT / 'build' / 'bbmcp'

CLEAR_JS = """
// 重写版清空脚本（2026-10-16）。旧版就三行 remove()，没有任何保护：
//   · Blockbench 停在 **animate 模式**时删方块会触发渲染层的 motion-trail bug
//     （'Cannot read properties of undefined (reading fix_rotation)'），
//     remove() 半途抛错 —— 方块被删了一部分、新的一个也没建上，工程直接变成空壳，
//     导出的 geo 只剩 181 B / 0 bones（踩过一次，整份模型靠生成器重建才恢复）。
//   · 也没有校验，清不干净也照样往下走。
// 这一版：先脱开动画 → 逐个 try 删除（单个失败不中断）→ 逐项校验 → 自报 ok。
const log = { steps: [] };
const readMode = () => {
  try { return (typeof Modes !== 'undefined' && Modes.selected && Modes.selected.id) || 'unknown'; }
  catch (e) { return 'unknown'; }
};
log.mode_before = readMode();
try { Animation.all.forEach((a) => { a.selected = false; }); } catch (e) { log.anim_err = String(e && e.message); }
try { if (typeof Animator !== 'undefined' && Animator.preview) Animator.preview(); } catch (e) {}
try { if (typeof Modes !== 'undefined' && Modes.edit && Modes.edit.select) Modes.edit.select(); } catch (e) {}
log.mode_after = readMode();

const cubes = Cube.all.slice();
let cubeErr = null;
for (const c of cubes) { try { c.remove(); } catch (e) { cubeErr = String(e && e.message); } }
log.removed_cubes = cubes.length;
log.left_cubes = Cube.all.length;
if (cubeErr) log.cube_err = cubeErr;

const groups = Group.all.slice();
let groupErr = null;
for (const g of groups) { try { g.remove(); } catch (e) { groupErr = String(e && e.message); } }
log.removed_groups = groups.length;
log.left_groups = Group.all.length;
if (groupErr) log.group_err = groupErr;

log.ok = (log.left_cubes === 0 && log.left_groups === 0);
return log;
"""

# 方块批次顺序：先容器/主体，再小件
ORDER = ['receiver', 'barrel', 'forearm', 'stock', 'bolt', 'hammer',
         'lever', 'carrier', 'cartridge', 'spent_shell', 'trigger', 'gate', 'scope']

# Java 契约：这些骨骼名 / 动画名不许丢（Java 侧按名字取骨骼、按名字播动画）
CONTRACT_BONES = ('root', 'move', 'body', 'barrel', 'forearm', 'receiver', 'bolt', 'hammer',
                  'lever', 'carrier', 'cartridge', 'spent_shell', 'trigger', 'scope', 'stock')
CONTRACT_ANIMS = ('static_idle', 'draw', 'shoot', 'bolt', 'reload_tactical', 'reload_empty', 'inspect')


def summarize(res):
    out = res.get('result')
    if isinstance(out, dict):
        if 'created' in out:
            extra = ''
            if 'bounds' in out and isinstance(out['bounds'], dict):
                extra = ' bounds=' + str(out['bounds'].get('size'))
            if out.get('z_fight_pairs'):
                extra += f" ZFIGHT={out['z_fight_pairs']}"
            return f"created={out['created']}{extra}"
        if 'removed_cubes' in out:
            return f"removed cubes={out['removed_cubes']} groups={out['removed_groups']}, left={out['left_cubes']}/{out['left_groups']}"
        if 'left_cubes' in out:
            return f"left={out['left_cubes']} cubes / {out['left_groups']} groups"
        return json.dumps(out, ensure_ascii=False)[:220]
    return str(out)[:220]


def main():
    steps = []
    # 0) 先确保有工程：Blockbench 里工程被关掉后所有命令都会回 "No project is open."
    ensure = ROOT / 'tools' / '_bb_ensure_project.js'
    if ensure.exists():
        steps.append(('ensure project open (GeckoLib)', 'script', str(ensure)))
    # 1) 清空之前必须先脱开 animate 模式：动画模式下删方块会触发 Blockbench 的 motion-trail
    #    bug（'reading fix_rotation' of undefined），clear 会半途失败并把工程清成空壳。
    pre = ROOT / 'tools' / '_bb_pre_edit.js'
    if pre.exists():
        steps.append(('pre: stop preview & switch to edit mode', 'script', str(pre)))
    if '--no-clear' not in sys.argv:
        steps.append(('clear', 'execute_script', {'code': CLEAR_JS}))

    groups = json.loads((OUT / 'win94_groups.json').read_text(encoding='utf-8'))
    steps.append((f'groups x{len(groups["groups"])}', 'add_groups', groups))

    for bone in ORDER:
        p = OUT / f'win94_cubes_{bone}.json'
        if not p.exists():
            print(f'!! 缺方块表 {p.name}')
            return 1
        cubes = json.loads(p.read_text(encoding='utf-8'))
        steps.append((f'cubes {bone} x{len(cubes["cubes"])}', 'add_cubes', cubes))

    # 建完自己核一遍：数量、契约骨骼名、贴图、动画。不符就 throw，apply 直接失败。
    total = sum(len(json.loads((OUT / f'win94_cubes_{b}.json').read_text(encoding='utf-8'))['cubes'])
                for b in ORDER)
    verify = ROOT / 'tools' / '_bb_verify.js'
    if verify.exists():
        steps.append(('verify: cubes / groups / bones', 'script',
                      {'path': str(verify),
                       'params': {'cubes': total, 'groups': len(groups['groups']),
                                  'bones': list(CONTRACT_BONES)}}))

    t_all = time.time()
    for label, action, params in steps:
        t0 = time.time()
        if action == 'script':
            if isinstance(params, dict) and 'path' in params:
                res = bbmcp.script(params['path'], params.get('params'), timeout=300)
            else:
                res = bbmcp.script(params, timeout=300)
        else:
            res = bbmcp.call(action, params, timeout=300)
        dt = time.time() - t0
        if not res.get('ok'):
            print(f'[{label}] FAIL {dt:.1f}s :: {json.dumps(res, ensure_ascii=False)[:900]}')
            return 1
        # 清空脚本自己会报 ok：清不干净就停在这里，绝不再往下建
        result = res.get('result')
        if isinstance(result, dict) and 'left_cubes' in result and not result.get('ok'):
            print(f'[{label}] FAIL {dt:.1f}s :: 清空不彻底 {json.dumps(result, ensure_ascii=False)[:600]}')
            return 1
        print(f'[{label}] OK {dt:.1f}s :: {summarize(res)}')

    print(f'--- all done in {time.time() - t_all:.1f}s ---')
    st = bbmcp.call('get_status', {}, timeout=60)
    print(json.dumps(st.get('result', {}).get('project', st), ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
