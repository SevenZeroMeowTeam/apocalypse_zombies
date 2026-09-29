# -*- coding: utf-8 -*-
"""bride_v2_scene.py —— 美女僵尸 Phase 2 预览渲染（Blender 无头）。

用法：
    /d/Blender/blender.exe --factory-startup -b -P F:/mcmod/tools/bride_v2_scene.py

做四件事：
  1) 读 art/bride/bride_zombie.geo.json + bride_zombie.animation.json + bride_zombie.png，
     逐面 UV 建 mesh（**同一份 JSON、同一张贴图**，不做手工摆拍、不换模型）
  2) 复核三个胸部数值（前伸 / 中缝 / 尺寸）——独立于生成器再算一遍
  3) 静置姿态出 全身正 / 侧 / 四分之三 + 胸部特写（正、侧剖面、俯视）
  4) 关键剪辑各出一帧：亡语魅惑前摇、血月选妃行礼、摄魂尖啸命中、行走中段、召唤
  最后存 art/bride/bride_v2.blend 与 art/bride/bride_v2_render_report.json

坐标约定：生成器内部空间 = 游戏/Bedrock 空间（-Z 正面、+Y 上、+X 右），本脚本不再取反；
Blender 侧只做一次刚体旋转 S(x,y,z)=(x,-z,y)（正面 → Blender +Y，上 → +Z）。
"""

import hashlib
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

BASE = 'F:/mcmod'
ART = BASE + '/art/bride'
GEO = ART + '/bride_zombie.geo.json'
ANIM = ART + '/bride_zombie.animation.json'
TEX = ART + '/bride_zombie.png'
SRC = BASE + '/src/main/resources/assets/apocalypse_zombies'
BLEND = ART + '/bride_v2.blend'
REPORT = ART + '/bride_v2_render_report.json'
RESO = 900

FACES = ('north', 'east', 'south', 'west', 'up', 'down')
FNORM = {'north': (0, 0, -1), 'south': (0, 0, 1), 'east': (1, 0, 0),
         'west': (-1, 0, 0), 'up': (0, 1, 0), 'down': (0, -1, 0)}
FACE_KEY = {'north': 'n', 'east': 'e', 'south': 's', 'west': 'w', 'up': 'u', 'down': 'd'}
S = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
report = {'blender': bpy.app.version_string, 'renders': [], 'errors': [], 'checks': []}


def sha256(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def layout(name, x0, y0, z0, x1, y1, z1):
    """每个面的「贴图左上角顶点 + u 方向 + v 方向」（与 Blockbench/Bedrock 一致）。"""
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
    ma = bpy.data.materials.new('bride_atlas')
    ma.use_nodes = True
    nt = ma.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if out is None:
            out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Roughness'].default_value = 0.62
    bsdf.inputs['Metallic'].default_value = 0.05
    img = bpy.data.images.load(TEX, check_existing=True)
    img.colorspace_settings.name = 'sRGB'
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Closest'          # 像素风：不做插值，边缘干净
    tex.location = (-460, 120)
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    # 面纱是 alpha 镂空蕾丝，必须把 alpha 也接进去并按 alpha clip 抠洞
    if 'Alpha' in bsdf.inputs:
        nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
        try:
            ma.blend_method = 'CLIP'
            ma.alpha_threshold = 0.5
        except Exception:
            pass
        try:
            ma.surface_render_method = 'DITHERED'
        except Exception:
            pass
    return ma


def build_geometry():
    geo = json.load(open(GEO, encoding='utf-8'))
    g = geo['minecraft:geometry'][0]
    desc = g['description']
    tw = float(desc.get('texture_width', 512))
    th = float(desc.get('texture_height', 512))
    mat = make_material()
    col = bpy.data.collections.new('bride_v2')
    bpy.context.scene.collection.children.link(col)
    bones = {}
    cubes_total = verts_total = faces_total = 0
    bb = [1e9, 1e9, 1e9, -1e9, -1e9, -1e9]
    for b in g['bones']:
        verts, faces, uvs = [], [], []
        for c in b.get('cubes', []):
            o = [float(v) for v in c['origin']]
            s = [float(v) for v in c['size']]
            x0, y0, z0 = o
            x1, y1, z1 = o[0] + s[0], o[1] + s[1], o[2] + s[2]
            if y0 > y1:                     # Bedrock 允许负尺寸，这里归一
                y0, y1 = y1, y0
            uvmap = c.get('uv') or {}
            for name in FACES:
                P, U, V = layout(name, x0, y0, z0, x1, y1, z1)
                w = abs((x1 - x0) * U[0] + (y1 - y0) * U[1] + (z1 - z0) * U[2])
                h = abs((x1 - x0) * V[0] + (y1 - y0) * V[1] + (z1 - z0) * V[2])
                quad = [Vector(P), Vector([P[i] + U[i] * w for i in range(3)]),
                        Vector([P[i] + U[i] * w + V[i] * h for i in range(3)]),
                        Vector([P[i] + V[i] * h for i in range(3)])]
                n = (quad[1] - quad[0]).cross(quad[2] - quad[0])
                if n.dot(Vector(FNORM[name])) < 0:
                    quad = list(reversed(quad))
                fd = uvmap.get(FACE_KEY[name])
                if fd:
                    u0, v0 = fd['uv']
                    uw, uh = fd.get('uv_size', (w, h))
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
    report['geo_sha256'] = sha256(GEO)
    report['tex_sha256'] = sha256(TEX)
    report['anim_sha256'] = sha256(ANIM)
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


def _catmull(p0, p1, p2, p3, f):
    """与 Bedrock/GeckoLib 的 lerp_mode=catmullrom 同形的均匀 Catmull-Rom。"""
    return [0.5 * ((2 * p1[i]) + (-p0[i] + p2[i]) * f
                   + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * f * f
                   + (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * f * f * f)
            for i in range(3)]


def sample(keys, t):
    ts = sorted(float(k) for k in keys)
    get = lambda x: chan_val(keys[str(x)])
    if t <= ts[0]:
        return get(ts[0])
    if t >= ts[-1]:
        return get(ts[-1])
    lo = max(x for x in ts if x <= t)
    hi = min(x for x in ts if x >= t)
    if hi == lo:
        return get(lo)
    f = (t - lo) / (hi - lo)
    i = ts.index(lo)
    p1, p2 = get(lo), get(hi)
    p0 = get(ts[i - 1]) if i > 0 else p1
    p3 = get(ts[i + 2]) if i + 2 < len(ts) else p2
    return _catmull(p0, p1, p2, p3, f)


def pose_matrices(g, anim_name, t):
    piv = {b['name']: Vector([float(x) for x in b.get('pivot', (0, 0, 0))]) for b in g['bones']}
    par = {b['name']: b.get('parent') for b in g['bones']}
    anim = json.load(open(ANIM, encoding='utf-8'))['animations']
    ch_all = anim[anim_name]['bones'] if anim_name else {}
    out = {}

    def walk(name):
        if name in out:
            return out[name]
        ch = ch_all.get(name, {})
        pos = sample(ch['position'], t) if 'position' in ch else [0, 0, 0]
        rot = sample(ch['rotation'], t) if 'rotation' in ch else [0, 0, 0]
        scl = sample(ch['scale'], t) if 'scale' in ch else [1, 1, 1]
        if 'scale' in ch:
            report['errors'].append('剪辑里出现 scale 通道: ' + name)
        m = (Matrix.Translation(Vector(pos))
             @ Matrix.Rotation(math.radians(rot[2]), 4, 'Z')
             @ Matrix.Rotation(math.radians(rot[1]), 4, 'Y')
             @ Matrix.Rotation(math.radians(rot[0]), 4, 'X')
             @ Matrix.Diagonal(Vector(scl).to_4d()))
        p = par.get(name)
        base = Matrix.Translation(piv[name]) @ m @ Matrix.Translation(-piv[name])
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
        ob.matrix_world = S @ W[name]
    bpy.context.view_layer.update()


# ---------------------------------------------------------------- 胸部数值复核
def check_bust(g):
    def boxes(bone_name, pred=None):
        out = []
        for b in g['bones']:
            if b['name'] != bone_name:
                continue
            for c in b.get('cubes', []):
                o = [float(v) for v in c['origin']]
                s = [float(v) for v in c['size']]
                out.append((o, s))
        return out

    def chest_front_z():
        """躯干正面平面：在「胸瓣所在的高度/宽度」上，最靠前的那张非胸瓣表面。"""
        zs = []
        for b in g['bones']:
            if b['name'].startswith('bust_'):
                continue
            for c in b.get('cubes', []):
                o = [float(v) for v in c['origin']]
                s = [float(v) for v in c['size']]
                if o[1] <= 20.7 <= o[1] + s[1] and o[0] <= 2.4 and o[0] + s[0] >= 0.6:
                    zs.append(o[2])
        return min(zs)

    br = [x for x in boxes('bust_r') if abs(x[1][1] - 3.0) < 1e-6]
    bl = [x for x in boxes('bust_l') if abs(x[1][1] - 3.0) < 1e-6]
    front = chest_front_z()
    if not br or not bl:
        report['checks'].append({'name': '胸瓣主块存在', 'pass': False})
        return
    obr, sbr = br[0]
    obl, sbl = bl[0]
    protrusion = round(front - obr[2], 3)
    gap = round(obr[0] - (obl[0] + sbl[0]), 3)
    report['bust_check'] = {
        'chest_front_z': round(front, 3),
        'bust_r_origin': [round(v, 3) for v in obr], 'bust_r_size': [round(v, 3) for v in sbr],
        'bust_l_origin': [round(v, 3) for v in obl], 'bust_l_size': [round(v, 3) for v in sbl],
        'protrusion': protrusion, 'gap': gap,
    }
    for nm, ok, det in (
            ('胸瓣宽 2.00u', abs(sbr[0] - 2.0) < 1e-6, sbr[0]),
            ('胸瓣高 3.00u', abs(sbr[1] - 3.0) < 1e-6, sbr[1]),
            ('前伸 1.00u', abs(protrusion - 1.0) < 1e-6, protrusion),
            ('中缝 1.00u', abs(gap - 1.0) < 1e-6, gap),
            ('左右对称', abs(obr[0] + (obl[0] + sbl[0])) < 1e-6, (obr[0], obl[0]))):
        report['checks'].append({'name': nm, 'pass': bool(ok), 'detail': str(det)})


# ---------------------------------------------------------------- 渲染
def setup_world():
    sc = bpy.context.scene
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE', 'CYCLES', 'BLENDER_WORKBENCH'):
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
        bg.inputs[0].default_value = (0.135, 0.145, 0.17, 1.0)
        bg.inputs[1].default_value = 1.1
    bpy.context.scene.world = w
    cam_data = bpy.data.cameras.new('Cam')
    cam = bpy.data.objects.new('Cam', cam_data)
    bpy.context.scene.collection.objects.link(cam)
    sc.camera = cam
    for nm, loc, rot, energy in (
            ('key', (6.5, 8.0, 10.5), (0.70, 0.05, 0.68), 6.0),
            ('fill', (-8.0, 4.5, 3.0), (1.30, 0.0, -1.05), 3.2),
            ('rim', (-2.5, -8.5, 6.0), (1.02, 0.0, -3.35), 4.0),
            ('front', (0.6, 11.5, 4.0), (1.28, 0.0, 0.05), 2.8)):
        ld = bpy.data.lights.new(nm, 'SUN')
        ld.energy = energy
        lo = bpy.data.objects.new(nm, ld)
        lo.location = loc
        lo.rotation_euler = rot
        bpy.context.scene.collection.objects.link(lo)
    return cam


def look_at(cam, loc, target, ortho=None):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        cam.data.ortho_scale = ortho


def shoot(name, cam, loc, target, ortho=None):
    look_at(cam, loc, target, ortho)
    path = ART + '/bride_v2_' + name + '.png'
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    report['renders'].append([os.path.basename(path),
                              os.path.getsize(path) if os.path.exists(path) else 0])
    return path


def mean_brightness(path):
    try:
        img = bpy.data.images.load(path, check_existing=False)
        px = list(img.pixels[:6000])
        bpy.data.images.remove(img)
        return round(sum(px) / max(1, len(px)), 4)
    except Exception as e:
        report['errors'].append('brightness:' + repr(e))
        return -1.0


def main():
    clear_scene()
    g, bones = build_geometry()
    check_bust(g)
    # 「同一份」证明：art 下的三个文件必须与 src 下的一致
    for nm, a, b in (('geo', GEO, SRC + '/geo/bride_zombie.geo.json'),
                     ('anim', ANIM, SRC + '/animations/bride_zombie.animation.json'),
                     ('tex', TEX, SRC + '/textures/entity/bride/bride_zombie.png')):
        same = sha256(a) == sha256(b)
        report['checks'].append({'name': f'art↔src {nm} 一致', 'pass': same,
                                 'detail': sha256(a)[:16]})
    cam = setup_world()
    bb = report['mc_bbox']
    ctr = [round((bb[i] + bb[i + 3]) / 2.0, 3) for i in range(3)]
    ctr_b = Vector((ctr[0], -ctr[2], ctr[1]))
    span = max(bb[3] - bb[0], bb[5] - bb[2], bb[4] - bb[1])
    report['center_bl'] = [round(v, 3) for v in ctr_b]
    report['span'] = round(span, 3)
    q3 = (ctr_b.x + span * 1.05, ctr_b.y + span * 1.15, ctr_b.z + span * 0.55)
    q3b = (ctr_b.x + span * 1.05, ctr_b.y - span * 1.15, ctr_b.z + span * 0.55)
    o = span * 1.28

    # ---- 静置姿态：全身正 / 侧 / 四分之三 ----
    apply_pose(g, bones, 'idle', 0.0)
    shoot('front', cam, (ctr_b.x, ctr_b.y + span * 2.4, ctr_b.z), ctr_b, ortho=o)
    report['brightness_front'] = mean_brightness(ART + '/bride_v2_front.png')
    shoot('side', cam, (ctr_b.x + span * 2.4, ctr_b.y, ctr_b.z), ctr_b, ortho=o)
    shoot('three_quarter', cam, q3, ctr_b)
    shoot('back_three_quarter', cam, q3b, ctr_b)

    # ---- 胸部特写：正面 / 侧面剖面（看 1px 前伸）/ 俯视（看中缝）----
    bust_t = Vector((0.0, 2.40, 20.7))          # MC(0, 20.7, -2.40) → Blender
    shoot('bust_front', cam, (bust_t.x, bust_t.y + 3.2, bust_t.z), bust_t, ortho=5.6)
    shoot('bust_profile', cam, (bust_t.x + 3.2, bust_t.y, bust_t.z), bust_t, ortho=5.0)
    shoot('bust_top', cam, (bust_t.x, bust_t.y + 1.2, bust_t.z + 3.0), bust_t, ortho=5.6)

    # ---- 关键剪辑各一帧（同一份 animation.json）----
    poses = (
        ('death_chime_windup', 'skill_death_chime', 0.90),
        ('death_chime_burst', 'skill_death_chime', 1.00),
        ('consort_curtsy', 'skill_consort', 1.50),
        ('shriek_impact', 'skill_soul_shriek', 1.10),
        ('walk_mid', 'walk', 0.40),
        ('summon_burst', 'summon', 0.45),
    )
    for tag, clip, t in poses:
        apply_pose(g, bones, clip, t)
        shoot('pose_' + tag, cam, q3, ctr_b)
    apply_pose(g, bones, 'idle', 0.0)

    report['actions'] = [a.name for a in bpy.data.actions]
    try:
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
        report['blend'] = os.path.getsize(BLEND)
    except Exception as e:
        report['errors'].append('save:' + repr(e))
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print('BUILD_REPORT ' + json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()