# -*- coding: utf-8 -*-
"""crossbow_bb_scene.py -- 在 Blender 里按 art/crossbow/crossbow.geo.json 建出十字弩场景。

用途（经 blender-mcp 调用）：
    exec(open('F:/mcmod/tools/crossbow_bb_scene.py', encoding='utf-8').read(), {'__name__': '__main__'})

做三件事：
  1) 清场 → 按 geo.json 的骨骼/方块建 mesh（MC 坐标 → Blender 坐标，逐面 UV，法线朝外）
  2) 套 crossbow.animation.json 的姿态（rest / draw 拉弦锁定 / reload_tactical 各阶段）出预览图
  3) 存 art/crossbow/crossbow.blend，并写 art/crossbow/blender_build_report.json

坐标铁律：MC 枪口 = -Z、上 = +Y、右 = +X；16u = 1 格。
Blender 侧：S(x,y,z) = (x, -z, y)  →  枪口指向 Blender +Y，上 = +Z。
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

BASE = 'F:/mcmod'
ART = BASE + '/art/crossbow'
# .geo.json / .animation.json 是 Bedrock/GeckoLib 的「取反约定」，而本脚本按右手系建模，
# 故读入后先转回内部表示。该转换是**对合**（做两次等于没做），复用生成器里的同一份实现，
# 避免两处漂移（生成器写出时用同一个函数；这里读入时再用一次即还原）。
if BASE + '/tools' not in sys.path:
    sys.path.insert(0, BASE + '/tools')
import crossbow_v1 as gen_convention          # noqa: E402
GEO = ART + '/crossbow.geo.json'
ANIM = ART + '/crossbow.animation.json'
TEX = ART + '/crossbow_geo.png'
BLEND = ART + '/crossbow.blend'
REPORT = ART + '/blender_build_report.json'
RESO = 900

FACES = ('north', 'east', 'south', 'west', 'up', 'down')
FNORM = {'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0),
         'west': (-1, 0, 0), 'up': (0, 1, 0), 'down': (0, -1, 0)}
# 每个面：UV 矩形左上角所在角点 + u/v 轴（MC 单位向量，符合 Bedrock/Blockbench 约定）
S = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
SI = S.inverted()
report = {'blender': bpy.app.version_string, 'renders': [], 'errors': []}


def layout(name, x0, y0, z0, x1, y1, z1):
    if name == 'north':
        return (x1, y1, z0), (-1, 0, 0), (0, -1, 0)
    if name == 'south':
        return (x0, y1, z1), (1, 0, 0), (0, -1, 0)
    if name == 'east':
        return (x1, y1, z1), (0, 0, -1), (0, -1, 0)
    if name == 'west':
        return (x0, y1, z0), (0, 0, 1), (0, -1, 0)
    if name == 'up':
        return (x0, y1, z0), (1, 0, 0), (0, 0, 1)
    return (x0, y0, z0), (1, 0, 0), (0, 0, 1)          # down


def rot_mc(deg, pivot):
    """MC 立方体旋转：绕自身 pivot，R = Rz @ Ry @ Rx。"""
    rx, ry, rz = [math.radians(a) for a in deg]
    m = (Matrix.Rotation(rz, 4, 'Z') @ Matrix.Rotation(ry, 4, 'Y')
         @ Matrix.Rotation(rx, 4, 'X'))
    return (Matrix.Translation(Vector(pivot)) @ m
            @ Matrix.Translation(-Vector(pivot)))


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)
    for ma in list(bpy.data.materials):
        bpy.data.materials.remove(ma)
    for co in list(bpy.data.collections):
        bpy.data.collections.remove(co)
    bpy.context.scene.frame_set(0)


def make_material():
    ma = bpy.data.materials.new('crossbow_atlas')
    ma.use_nodes = True
    nt = ma.node_tree
    bsdf = None
    for n in nt.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            bsdf = n
            break
    if bsdf is None:
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if out is None:
            out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Roughness'].default_value = 0.72
    bsdf.inputs['Metallic'].default_value = 0.15
    img = bpy.data.images.load(TEX, check_existing=True)
    img.colorspace_settings.name = 'sRGB'
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Closest'
    tex.location = (-420, 120)
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    return ma


def build_geometry():
    # 读入文件后立刻转回内部右手系（对合转换，见文件头说明）
    geo = gen_convention.game_convention_geo(json.load(open(GEO, encoding='utf-8')))
    g = geo['minecraft:geometry'][0]
    desc = g['description']
    tw = float(desc.get('texture_width', 512))
    th = float(desc.get('texture_height', 512))
    mat = make_material()
    col = bpy.data.collections.new('crossbow')
    bpy.context.scene.collection.children.link(col)
    bones = {}
    cubes_total = 0
    verts_total = 0
    faces_total = 0
    bb = [1e9, 1e9, 1e9, -1e9, -1e9, -1e9]
    for b in g['bones']:
        cs = b.get('cubes', [])
        verts, faces, uvs = [], [], []
        for c in cs:
            o = [float(v) for v in c['origin']]
            s = [float(v) for v in c['size']]
            infl = float(c.get('inflate', 0.0) or 0.0)
            x0, y0, z0 = [o[i] - infl for i in range(3)]
            x1, y1, z1 = [o[i] + s[i] + infl for i in range(3)]
            uvmap = c.get('uv')
            R = rot_mc(c['rotation'], c['pivot']) if c.get('rotation') else None
            cpiv = c.get('pivot') or [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]
            for name in FACES:
                P, U, V = layout(name, x0, y0, z0, x1, y1, z1)
                w = abs((x1 - x0) * U[0] + (y1 - y0) * U[1] + (z1 - z0) * U[2])
                h = abs((x1 - x0) * V[0] + (y1 - y0) * V[1] + (z1 - z0) * V[2])
                quad = [Vector(P), Vector([P[i] + U[i] * w for i in range(3)]),
                        Vector([P[i] + U[i] * w + V[i] * h for i in range(3)]),
                        Vector([P[i] + V[i] * h for i in range(3)])]
                if R is not None:
                    quad = [R @ q for q in quad]
                n = (quad[1] - quad[0]).cross(quad[2] - quad[0])
                if n.dot(Vector(FNORM[name])) < 0:
                    quad = list(reversed(quad))
                if isinstance(uvmap, dict) and name in uvmap:
                    fd = uvmap[name]
                    u0, v0 = fd['uv']
                    uw, uh = fd.get('uv_size', (w, h))
                elif isinstance(uvmap, dict):
                    fd = uvmap[FACES[0]]
                    u0, v0 = fd['uv']
                    uw, uh = fd.get('uv_size', (w, h))
                elif isinstance(uvmap, list) and len(uvmap) and isinstance(uvmap[0], (int, float)):
                    u0, v0 = uvmap[0], uvmap[1]
                    uw = uvmap[2] if len(uvmap) > 2 else w
                    uh = uvmap[3] if len(uvmap) > 3 else h
                else:
                    u0, v0, uw, uh = 0.0, 0.0, w, h
                r = [(u0, v0), (u0 + uw, v0), (u0 + uw, v0 + uh), (u0, v0 + uh)]
                base = len(verts)
                verts.extend([(q.x, q.y, q.z) for q in quad])
                faces.append((base, base + 1, base + 2, base + 3))
                uvs.append(r)
                for q in quad:
                    bb[0] = min(bb[0], q.x); bb[1] = min(bb[1], q.y); bb[2] = min(bb[2], q.z)
                    bb[3] = max(bb[3], q.x); bb[4] = max(bb[4], q.y); bb[5] = max(bb[5], q.z)
            cubes_total += 1
        if not verts:
            bones[b['name']] = None
            continue
        me = bpy.data.meshes.new(b['name'] + '_mesh')
        me.from_pydata(verts, [], [f for f in faces])
        me.update()
        lay = me.uv_layers.new(name='UVMap')
        for fi, r in enumerate(uvs):
            for i in range(4):
                u, v = r[i]
                lay.data[fi * 4 + i].uv = Vector((u / tw, 1.0 - v / th))
        me.materials.append(mat)
        ob = bpy.data.objects.new(b['name'], me)
        ob.data.materials.append(mat)
        col.objects.link(ob)
        bones[b['name']] = ob
        verts_total += len(verts)
        faces_total += len(faces)
    report['bones'] = len(g['bones'])
    report['cubes'] = cubes_total
    report['verts'] = verts_total
    report['faces'] = faces_total
    report['mc_bbox'] = [round(v, 3) for v in bb]
    return g, bones


# ---------------------------------------------------------------- 动画姿态
def chan_val(v):
    if isinstance(v, dict):
        v = v.get('post', v.get('pre', v))
        if isinstance(v, dict):
            v = v.get('vector', [0, 0, 0])
    if isinstance(v, (int, float)):
        v = [float(v)] * 3
    return [float(x) for x in v]


def sample(keys, t):
    ts = sorted(float(k) for k in keys)
    if t <= ts[0]:
        return chan_val(keys[str(ts[0]) if str(ts[0]) in keys else ts[0]])
    if t >= ts[-1]:
        return chan_val(keys[str(ts[-1]) if str(ts[-1]) in keys else ts[-1]])
    lo = max(x for x in ts if x <= t)
    hi = min(x for x in ts if x >= t)
    a = chan_val(keys[str(lo) if str(lo) in keys else lo])
    b = chan_val(keys[str(hi) if str(hi) in keys else hi])
    if hi == lo:
        return a
    f = (t - lo) / (hi - lo)
    return [a[i] + (b[i] - a[i]) * f for i in range(3)]


def pose_matrices(g, anim_name, t):
    """返回 {骨名: MC 空间世界矩阵}，含 position/rotation/scale 通道。"""
    piv = {b['name']: Vector([float(x) for x in b.get('pivot', (0, 0, 0))]) for b in g['bones']}
    par = {b['name']: b.get('parent') for b in g['bones']}
    if anim_name:
        # 动画文件同样是取反约定，读入后转回内部右手系（对合）
        anim_doc = gen_convention.game_convention_anims(json.load(open(ANIM, encoding='utf-8')))
        anim = anim_doc['animations'][anim_name]['bones']
    else:
        anim = {}
    out = {}

    def walk(name):
        if name in out:
            return out[name]
        ch = anim.get(name, {})
        pos = sample(ch['position'], t) if 'position' in ch else [0, 0, 0]
        rot = sample(ch['rotation'], t) if 'rotation' in ch else [0, 0, 0]
        scl = sample(ch['scale'], t) if 'scale' in ch else [1, 1, 1]
        m = (Matrix.Translation(Vector(pos))
             @ Matrix.Rotation(math.radians(rot[2]), 4, 'Z')
             @ Matrix.Rotation(math.radians(rot[1]), 4, 'Y')
             @ Matrix.Rotation(math.radians(rot[0]), 4, 'X')
             @ Matrix.Diagonal(Vector(scl).to_4d()))
        p = par.get(name)
        base = (Matrix.Translation(piv[name]) @ m @ Matrix.Translation(-piv[name]))
        world = (walk(p) @ base) if (p and p != name) else base
        out[name] = world
        return world

    for b in g['bones']:
        walk(b['name'])
    return out


def apply_pose(g, bones, anim_name, t):
    W = pose_matrices(g, anim_name, t)
    for name, ob in bones.items():
        if ob is None:
            continue
        ob.matrix_world = S @ W[name]     # 顶点在 MC 坐标下，先套姿态(W, MC 空间)，再转 Blender 空间
    bpy.context.view_layer.update()


# ---------------------------------------------------------------- 渲染
def setup_world():
    sc = bpy.context.scene
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'BLENDER_WORKBENCH'):
        try:
            sc.render.engine = eng
            break
        except Exception:
            continue
    report['engine'] = sc.render.engine
    sc.render.resolution_x = RESO
    sc.render.resolution_y = RESO
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = 'Standard'
    except Exception:
        pass
    if bpy.data.worlds.get('World') is None:
        bpy.data.worlds.new('World')
    w = bpy.data.worlds['World']
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    if bg:
        bg.inputs[0].default_value = (0.115, 0.125, 0.145, 1.0)
        bg.inputs[1].default_value = 1.2
    bpy.context.scene.world = w
    cam_data = bpy.data.cameras.new('Cam')
    cam = bpy.data.objects.new('Cam', cam_data)
    bpy.context.scene.collection.objects.link(cam)
    sc.camera = cam
    for nm, loc, rot, energy in (
            ('key', (6.5, 7.0, 9.5), (0.72, 0.05, 0.78), 6.5),
            ('fill', (-7.5, 4.0, 3.2), (1.25, 0.0, -1.05), 3.0),
            ('rim', (-2.0, -8.5, 5.5), (1.05, 0.0, -3.35), 3.5),
            ('front', (0.6, 11.0, 3.5), (1.32, 0.0, 0.05), 2.6)):
        ld = bpy.data.lights.new(nm, 'SUN')
        ld.energy = energy
        lo = bpy.data.objects.new(nm, ld)
        lo.location = loc
        lo.rotation_euler = rot
        bpy.context.scene.collection.objects.link(lo)
    return cam


def look_at(cam, loc, target, ortho=None):
    cam.location = Vector(loc)
    d = (Vector(target) - Vector(loc))
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        cam.data.ortho_scale = ortho


def shoot(name, cam, loc, target, ortho=None):
    look_at(cam, loc, target, ortho)
    path = ART + '/preview_' + name + '.png'
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    report['renders'].append([name, os.path.getsize(path) if os.path.exists(path) else 0])
    return path


def mean_brightness(path):
    try:
        img = bpy.data.images.load(path, check_existing=False)
        px = list(img.pixels[:4000])
        bpy.data.images.remove(img)
        return round(sum(px) / max(1, len(px)), 4)
    except Exception as e:
        report['errors'].append('brightness:' + repr(e))
        return -1.0


def main():
    clear_scene()
    g, bones = build_geometry()
    cam = setup_world()
    bb = report['mc_bbox']
    ctr = [round((bb[i] + bb[i + 3]) / 2.0, 3) for i in range(3)]
    # MC 中心 → Blender
    ctr_b = Vector((ctr[0], -ctr[2], ctr[1]))
    span = max(bb[3] - bb[0], bb[5] - bb[2], bb[4] - bb[1])
    report['center_bl'] = [round(v, 3) for v in ctr_b]
    report['span'] = round(span, 3)
    # rest 四视图（正交通用）
    apply_pose(g, bones, 'static_idle', 0.0)
    shoot('side', cam, (ctr_b.x + span * 2.2, ctr_b.y, ctr_b.z), ctr_b, ortho=span * 1.25)
    report['brightness_side'] = mean_brightness(ART + '/preview_side.png')
    shoot('front', cam, (ctr_b.x, ctr_b.y + span * 2.2, ctr_b.z), ctr_b, ortho=span * 1.25)
    shoot('three_quarter', cam, (ctr_b.x + span * 1.15, ctr_b.y - span * 1.2, ctr_b.z + span * 0.75), ctr_b)
    shoot('ads', cam, (ctr_b.x, ctr_b.y - span * 0.55, ctr_b.z + span * 0.12),
          (0.0, ctr_b.y - span * 0.5, 2.85))
    shoot('top', cam, (ctr_b.x, ctr_b.y, ctr_b.z + span * 2.2), ctr_b, ortho=span * 1.25)
    # draw：拉弦锁定
    ad = json.load(open(ANIM, encoding='utf-8'))['animations']
    dl = ad['draw']
    last = float(dl.get('animation_length') or max(float(k) for k in dl['bones']['string_l']['rotation']))
    apply_pose(g, bones, 'draw', last)
    shoot('draw_side', cam, (ctr_b.x + span * 2.2, ctr_b.y, ctr_b.z), ctr_b, ortho=span * 1.25)
    report['draw_t'] = last
    apply_pose(g, bones, 'draw', last * 0.5)
    shoot('draw_mid_three_quarter', cam, (ctr_b.x + span * 1.15, ctr_b.y - span * 1.2, ctr_b.z + span * 0.75), ctr_b)
    # reload：取箭 → 送入弹仓 → 入膛
    rl = ad['reload_tactical']
    dur = float(rl.get('animation_length') or max(float(k) for k in rl['bones']['round_hand']['position']))
    report['reload_t'] = dur
    for frac, tag in ((0.30, '1'), (0.62, '2'), (0.92, '3')):
        apply_pose(g, bones, 'reload_tactical', dur * frac)
        shoot('reload' + tag + '_three_quarter', cam,
              (ctr_b.x + span * 1.15, ctr_b.y - span * 1.2, ctr_b.z + span * 0.75), ctr_b)
    apply_pose(g, bones, 'static_idle', 0.0)
    shoot('mag_closeup', cam, (5.5, ctr_b.y + 5.0, 4.2), (0.0, ctr_b.y + 3.5, 1.9), ortho=8.6)
    # 弩机特写（郭 / 牙 / 望山 / 悬刀 / 两键）
    shoot('lock_closeup', cam, (6.2, ctr_b.y + 0.4, 2.6), (0.0, ctr_b.y + 0.35, 1.45), ortho=4.6)
    report['actions'] = [a.name for a in bpy.data.actions]
    try:
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
        report['blend'] = os.path.getsize(BLEND)
    except Exception as e:
        report['errors'].append('save:' + repr(e))
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print('BUILD_REPORT ' + json.dumps(report, ensure_ascii=False))


main()