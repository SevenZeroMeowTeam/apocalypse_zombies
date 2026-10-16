# -*- coding: utf-8 -*-
"""win94 导出 —— 把 Blockbench 里的工程落成 Java 侧要的资源文件。

  1) save_project   把内存里的最新工程写回 win94.bbmodel（也是动画的原始数据来源）
  2) execute_script 设 identifier（Bedrock 侧导出成 geometry.win94，与 Java 侧一致）
  3) export_model   bedrock codec 导出 geo/win94.geo.json
  4) 本地转换       bbmodel 的 animations → GeckoLib 的 animation.json：
                    {format_version, animations:{<clip>:{loop, animation_length, bones:{...}}}}
                    每个关键帧写成 {"post":{"vector":[x,y,z]},"lerp_mode":...}
                    每个通道的键按时间升序（零时间戳在首）—— GeckoLib 的硬约束，
                    违反会令客户端在资源加载阶段崩溃（2026-10-16 事故）。

GeckoLib 的动画 codec 在 MCP 里调不到（export 会弹保存对话框），而 bbmodel 本来就存着完整关键帧，
所以这一步在本地做 —— 数据来源仍是 Blockbench 写出的 bbmodel，没有手改。

⚠ 坐标空间（几何与动画**必须用同一条换算**，取自 GeckoLib 4.8.4 源码）：
  bbmodel / Blockbench 是**作者空间 B**（+X = 射手右侧；Blockbench 预览里看到什么，
  游戏里就该是什么 —— 这是这套管线的目标不变量）。GeckoLib 在加载落盘文件时会对
  F（落盘空间）做一次"预烹饪"把它变回 B（渲染空间 R）：
    · 几何          `BakedModelFactory.constructBone/constructCube`：
                    骨骼 pivot x → −x；cube origin x → −(x+w)（= X 镜像）；
                    骨骼与方块旋转 (rx,ry,rz) → (−rx, −ry, rz)
    · 动画·位置     `RenderUtils.translateMatrixToBone`：posX → −posX（y/z 原样）
    · 动画·旋转     `BakedAnimationsAdapter.buildKeyframeStack(isForRotation=true)`：
                    (rx,ry,rz) → (−rx, −ry, rz)（并转成弧度）
  所以**落盘文件 F 必须写"烹饪的逆"**（同一映射，自逆）：
    位置 (x,y,z) → (−x, y, z)；旋转 (rx,ry,rz) → (−rx, −ry, rz)；scale 原样 ⇒ 渲染 = 作者意图。
  这正是莫辛/AWM 等已出货枪的文件规则（莫辛 casing：bbmodel (60,−160,−40)/+0.5 →
  落盘 (−60,+160,−40)/−0.5），也是 geo 导出要把 X 取反的**全部原因**。
  **写错方向的后果**（1.1.105/106 实测）：文件 +62° 的 lever 在游戏里被烹成 −62° ——
  杠杆向上翻（用户报「应该向下拉」）；装弹/抛壳的**位置**方向同理会反（这就是「装弹方向反了」）。
  check_cooked() 逐键校验落盘值 == 本函数(bbmodel 值)，漏翻 / 翻错方向都会当场报错。

用法：python tools/win94/export.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools'))
import bbmcp  # noqa: E402
import spec as S  # noqa: E402

BBMODEL = S.BBMODEL
ASSETS = S.ASSETS
GEO_OUT = ASSETS / 'geo' / 'win94.geo.json'
ANIM_OUT = ASSETS / 'animations' / 'win94.animation.json'

SET_ID_JS = """
Project.model_identifier = 'win94';
if (Project.geckolib_model_identifier !== undefined) Project.geckolib_model_identifier = 'win94';
Project.name = 'win94';
return { identifier: Project.model_identifier, name: Project.name, format: Format.id };
"""

LERP = {'catmullrom': 'catmullrom', 'linear': 'linear', 'step': 'step', 'bezier': 'catmullrom'}
LOOP = {'loop': True, 'once': False, 'hold': 'hold'}


def tkey(t):
    s = f'{float(t):.4f}'.rstrip('0').rstrip('.')
    return s if s else '0'


def cook_for_export(channel, vec):
    """作者空间 B（bbmodel）→ 落盘空间 F 的换算：GeckoLib 加载预烹饪的逆，见文件头「坐标空间」。

    位置 x 取反；旋转否定 rx / ry、保留 rz；scale 原样。取反产生的 −0.0 归一回 +0.0 ——
    数值等价，但别让"每个 0 都被翻了一下"混进 diff。
    """
    x, y, z = float(vec[0]), float(vec[1]), float(vec[2])

    def neg(v):
        v = -v
        return 0.0 if v == 0.0 else v

    if channel == 'position':
        return [neg(x), y, z]
    if channel == 'rotation':
        return [neg(x), neg(y), z]
    return [x, y, z]


def convert_animations(data):
    out = {}
    for anim in data.get('animations', []):
        name = (anim.get('name') or '').replace('animation.', '')
        bones = {}
        for _uuid, an in (anim.get('animators') or {}).items():
            bone = an.get('name')
            if not bone:
                continue
            for k in an.get('keyframes', []):
                dps = k.get('data_points') or []
                if not dps:
                    continue
                d0 = dps[0]
                vec = cook_for_export(k['channel'],
                                        [float(d0.get('x', 0)), float(d0.get('y', 0)), float(d0.get('z', 0))])
                ch = bones.setdefault(bone, {}).setdefault(k['channel'], {})
                ch[tkey(k['time'])] = {
                    'post': {'vector': vec},
                    'lerp_mode': LERP.get(k.get('interpolation'), 'catmullrom'),
                }
        out[name] = {
            'loop': LOOP.get(anim.get('loop'), False),
            'animation_length': round(float(anim.get('length') or 0), 4),
            'bones': bones,
        }
    # GeckoLib 契约：每个通道的键必须按时间升序（零时间戳在首）。
    # 违反时 BakedAnimationsAdapter 抛 "multiple starting keyframes"，
    # 整包动画解析失败 → 客户端在资源加载阶段崩溃（bbmodel 里的数组顺序不保证）。
    for a in out.values():
        for chans in a['bones'].values():
            for chan, ks in chans.items():
                chans[chan] = {k: ks[k] for k in sorted(ks, key=float)}
    return out


def check_geckolib(anims):
    """复刻 GeckoLib BakedAnimationsAdapter.getKeyframes 的硬约束，返回问题列表。"""
    problems = []
    for name, a in anims.items():
        for bone, chans in a['bones'].items():
            for chan, ks in chans.items():
                for i, k in enumerate(ks):
                    try:
                        t = float(k)
                    except ValueError:
                        t = 0.0
                    if t == 0 and i > 0:
                        problems.append(f'{name}/{bone}.{chan}: 零时间戳键 "{k}" 不在首位')
    return problems


def check_cooked(anims, data):
    """逐键校验落盘值 == cook_for_export(bbmodel 值)（见文件头「坐标空间」）。

    1.1.105 之前转换器整层缺失（位置反向 →「装弹方向反了」）；1.1.106 位置翻对了，
    但旋转用了错误的"精确镜像"规则 → 文件 +62° 的 lever 被 GeckoLib 烹成 −62°（杠杆向上翻）。
    漏翻 / 翻错方向都会在这里当场报错。
    """
    problems = []
    raw = {}
    for anim in data.get('animations', []):
        name = (anim.get('name') or '').replace('animation.', '')
        for _uuid, an in (anim.get('animators') or {}).items():
            bone = an.get('name')
            if not bone:
                continue
            for k in an.get('keyframes', []):
                dps = k.get('data_points') or []
                if not dps:
                    continue
                d0 = dps[0]
                raw[(name, bone, k['channel'], tkey(k['time']))] = [
                    float(d0.get('x', 0)), float(d0.get('y', 0)), float(d0.get('z', 0))]
    for name, a in anims.items():
        for bone, chans in a['bones'].items():
            for chan, ks in chans.items():
                for t, k in ks.items():
                    src = raw.get((name, bone, chan, t))
                    if src is None:
                        problems.append(f'{name}/{bone}.{chan}@{t}: 落盘帧在 bbmodel 里找不到')
                        continue
                    want = cook_for_export(chan, src)
                    got = k['post']['vector']
                    if any(abs(g - w) > 1e-6 for g, w in zip(got, want)):
                        problems.append(f'{name}/{bone}.{chan}@{t}: 落盘 {got} ≠ 镜像({src}) = {want}')
    return problems


def main():
    r = bbmcp.call('save_project', {'path': str(BBMODEL)}, timeout=300)
    if not r.get('ok'):
        print('save_project FAIL', json.dumps(r, ensure_ascii=False)[:400])
        return 1
    print('[save_project]', json.dumps(r.get('result'), ensure_ascii=False)[:180])

    r = bbmcp.call('execute_script', {'code': SET_ID_JS}, timeout=120)
    print('[identifier]', json.dumps(r.get('result'), ensure_ascii=False)[:180])

    GEO_OUT.parent.mkdir(parents=True, exist_ok=True)
    r = bbmcp.call('export_model', {'codec': 'bedrock', 'path': str(GEO_OUT)}, timeout=600)
    if not r.get('ok'):
        print('export_model FAIL', json.dumps(r, ensure_ascii=False)[:400])
        return 1
    print('[geo]', json.dumps(r.get('result'), ensure_ascii=False)[:180])

    geo = json.loads(GEO_OUT.read_text(encoding='utf-8'))
    g0 = geo['minecraft:geometry'][0]
    desc = g0['description']
    print(f"  identifier={desc.get('identifier')} tex={desc.get('texture_width')}x"
          f"{desc.get('texture_height')} bones={len(g0.get('bones', []))} "
          f"cubes={sum(len(b.get('cubes', [])) for b in g0.get('bones', []))}")

    data = json.loads(BBMODEL.read_text(encoding='utf-8'))
    anims = convert_animations(data)
    gecko_bad = check_geckolib(anims)
    if gecko_bad:
        print('!! GeckoLib 关键帧契约不通过（写出会让客户端启动崩溃）：')
        for b in gecko_bad[:10]:
            print('   [x]', b)
        return 1
    cook_bad = check_cooked(anims, data)
    if cook_bad:
        print('!! 落盘动画没有按 GeckoLib 预烹饪的逆换算（几何与动画不在同一坐标空间 —— 动作方向会反）：')
        for b in cook_bad[:10]:
            print('   [x]', b)
        return 1
    payload = {'format_version': '1.8.0', 'animations': anims}
    ANIM_OUT.parent.mkdir(parents=True, exist_ok=True)
    ANIM_OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    print(f'[anim] {ANIM_OUT.name}: {len(anims)} clips')
    print('[cook] 落盘动画 == bbmodel 经预烹饪逆换算（位置 x 取反；旋转 −rx/−ry/+rz）')
    missing = [a for a in S.CONTRACT_ANIMS if a not in anims]
    for name, a in anims.items():
        nk = sum(len(ks) for chn in a['bones'].values() for ks in chn.values())
        mark = '' if name in S.CONTRACT_ANIMS else '  <-- 契约外的 clip'
        print(f'  {name:18s} loop={str(a["loop"]):5s} len={a["animation_length"]:4} '
              f'ticks={int(a["animation_length"] * 20 + 0.999):3d} '
              f'bones={len(a["bones"]):2d} kf={nk:3d}{mark}')
    if missing:
        print('!! 缺契约 clip:', missing)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
