# -*- coding: utf-8 -*-
"""win94 建模（MCP 写入）—— 把 model.py 的骨骼表 / 方块表**通过 blockbench-mcp** 建进工程。

顺序：确保工程打开（GeckoLib 格式）→ 脱开 animate 模式 →
      清空（动画 / 贴图 / 方块 / 骨骼）→ add_groups → 按骨骼分批 add_cubes → 自校验。

所有写操作都走桥（127.0.0.1:8787 /command），不直接改 bbmodel 文件。

用法：
  python tools/win94/build.py            # 全量重建
  python tools/win94/build.py --no-clear # 只补方块（调试）
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools'))
import bbmcp  # noqa: E402
import spec as S  # noqa: E402

OUT = ROOT / 'build' / 'win94'

ENSURE_JS = """
if (!Project) { newProject(Format ? Format : 'geckolib_model'); }
if (Format && Format.id !== 'geckolib_model') { /* 保持当前格式 */ }
return { project: Project.name, format: Format.id };
"""

# 清空：先脱离 animate 模式（在那里删方块会触发 Blockbench 的 motion-trail bug，
# 'Cannot read properties of undefined (reading fix_rotation)'，删一半就抛错、工程变空壳）。
CLEAR_JS = """
const log = { steps: [] };
const mode = () => { try { return (Modes.selected && Modes.selected.id) || 'unknown'; } catch (e) { return 'unknown'; } };
log.mode_before = mode();
try { Animation.all.forEach((a) => { a.selected = false; }); } catch (e) { log.anim_sel_err = String(e && e.message); }
try { if (typeof Animator !== 'undefined' && Animator.preview) Animator.preview(); } catch (e) {}
try { if (Modes.edit && Modes.edit.select) Modes.edit.select(); } catch (e) {}
log.mode_after = mode();

const anims = Animation.all.slice();
anims.forEach((a) => { try { a.remove(true); } catch (e) { try { a.remove(); } catch (e2) { log.anim_err = String(e2 && e2.message); } } });
log.removed_anims = anims.length;
log.left_anims = Animation.all.length;

const texs = Texture.all.slice();
texs.forEach((t) => { try { t.remove(); } catch (e) { log.tex_err = String(e && e.message); } });
log.removed_textures = texs.length;
log.left_textures = Texture.all.length;

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

log.ok = (log.left_cubes === 0 && log.left_groups === 0 && log.left_anims === 0);
return log;
"""

VERIFY_JS = """
const want = params || {};
const missing = [];
for (const b of (want.bones || [])) { if (!Group.all.some((g) => g.name === b)) missing.push(b); }
const out = {
  cubes: Cube.all.length, groups: Group.all.length,
  textures: Texture.all.length, animations: Animation.all.length,
  missing_bones: missing,
  want_cubes: want.cubes || null, want_groups: want.groups || null,
};
out.ok = missing.length === 0
  && (want.cubes === undefined || Cube.all.length === want.cubes)
  && (want.groups === undefined || Group.all.length === want.groups);
return out;
"""

# 建模批次顺序：先主体，再小件（出问题时容易看出缺了什么）
ORDER = ['barrel', 'forearm', 'receiver', 'stock', 'bolt', 'hammer',
         'lever', 'carrier', 'cartridge', 'spent_shell', 'trigger', 'gate', 'scope']


def summarize(res):
    out = res.get('result')
    if isinstance(out, dict):
        if 'created' in out:
            extra = ''
            if isinstance(out.get('bounds'), dict):
                extra = ' bounds=' + str(out['bounds'].get('size'))
            if out.get('z_fight_pairs'):
                extra += f" ZFIGHT={out['z_fight_pairs']}"
            return f"created={out['created']}{extra}"
        if 'removed_cubes' in out:
            return (f"removed cubes={out['removed_cubes']} groups={out['removed_groups']} "
                    f"anims={out.get('removed_anims')} tex={out.get('removed_textures')} "
                    f"left={out['left_cubes']}/{out['left_groups']}/{out.get('left_anims')}")
        return json.dumps(out, ensure_ascii=False)[:260]
    return str(out)[:260]


def main():
    steps = [('ensure project', 'execute_script', {'code': ENSURE_JS})]
    if '--no-clear' not in sys.argv:
        steps.append(('clear', 'execute_script', {'code': CLEAR_JS}))

    groups = json.loads((OUT / 'groups.json').read_text(encoding='utf-8'))
    steps.append((f'groups x{len(groups["groups"])}', 'add_groups', groups))
    for bone in ORDER:
        p = OUT / f'cubes_{bone}.json'
        if not p.exists():
            print('!! 缺方块表', p.name)
            return 1
        cubes = json.loads(p.read_text(encoding='utf-8'))
        steps.append((f'cubes {bone} x{len(cubes["cubes"])}', 'add_cubes', cubes))

    total = sum(len(json.loads((OUT / f'cubes_{b}.json').read_text(encoding='utf-8'))['cubes'])
                for b in ORDER)
    steps.append(('verify', 'execute_script',
                  {'code': VERIFY_JS, 'params': {'cubes': total,
                                                 'groups': len(groups['groups']),
                                                 'bones': list(S.CONTRACT_BONES)}}))

    t_all = time.time()
    for label, action, params in steps:
        t0 = time.time()
        res = bbmcp.call(action, params, timeout=600)
        dt = time.time() - t0
        if not res.get('ok'):
            print(f'[{label}] FAIL {dt:.1f}s :: {json.dumps(res, ensure_ascii=False)[:900]}')
            return 1
        result = res.get('result')
        if isinstance(result, dict) and 'left_cubes' in result and not result.get('ok'):
            print(f'[{label}] FAIL 清空不彻底 :: {json.dumps(result, ensure_ascii=False)[:600]}')
            return 1
        if isinstance(result, dict) and result.get('ok') is False and 'missing_bones' in result:
            print(f'[{label}] FAIL 校验 :: {json.dumps(result, ensure_ascii=False)[:600]}')
            return 1
        print(f'[{label}] OK {dt:.1f}s :: {summarize(res)}')

    print(f'--- build done in {time.time() - t_all:.1f}s ---')
    st = bbmcp.call('get_status', {}, timeout=60)
    print(json.dumps(st.get('result', {}).get('project', st), ensure_ascii=False)[:400])
    return 0


if __name__ == '__main__':
    sys.exit(main())
