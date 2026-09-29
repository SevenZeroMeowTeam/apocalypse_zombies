# -*- coding: utf-8 -*-
"""bride_zombie_scene.py —— 无头渲染「美女僵尸 / bride_zombie」预览，重点让新加的胸部补块看得见。

用法：
    D:/Blender/blender.exe --factory-startup -b -P F:/mcmod/art/bride/bride_zombie_scene.py

模型 = 原版人形 64×64 UV 布局的方块集合（与 BrideModel.createBodyLayer() 一致）：
    head / hat / body / rarm / larm / rleg / lleg + 新加的 bust_r / bust_l 两瓣胸部补块。
补块 2宽×3高×1深，盒子从 z=-3.02 伸到 z=-2.02 —— 相对躯干正面(z=-2)前伸 1px（躯干厚度的 25%）；
    两瓣 x 分别占 [-2.5,-0.5] 与 [0.5,2.5]，中间留 1px 中缝（x=-0.5..0.5）。

坐标：这里直接用 Java/原版的模型坐标 —— X=模型左，Y=向下，Z=远离正面，正面朝 -Z。
     Blender 侧用 (x,y,z)_mc -> (-x, -z, -y)_blender（det=+1 的纯旋转，不镜像）：
     MC -Z(正面) -> Blender +Y，MC -Y(上) -> Blender +Z。所以正面相机放在 Blender +Y 上，
     即「沿 MC -Z 看向模型」。

方块 UV 展开（texOffs=(u,v)，尺寸 w,h,d）严格照原版布局，不归一化：
    顶面(-y) (u+d, v)          w×d       底面(+y) (u+d+w, v)         w×d
    -x 面    (u, v+d)          d×h       +x 面   (u+d+w, v+d)       d×h
    正面(-z) (u+d, v+d)        w×h       背面(+z) (u+d+w+d, v+d)     w×h
    （与 tools/bride_zombie_skin.js 里逐像素画的区域一一对应，见报告里的 uv_rects 校验。）
    唯一例外：hat 是原版 8×8×8 的头部覆盖层加 CubeDeformation(0.5) —— UV 仍按 8×8×8 展开
    （texOffs 32,0），只有几何体膨胀到 9×9×9。照 9×9×9 展开会和贴图上画的对不上、+x 面还会
    跑出 64×64 之外，所以按原版语义来。

输出（全部落在 art/bride/ 下）：
    bride_front.png             正面（相机沿 -Z，正交）：两瓣补块同时可见
    bride_three_quarter.png     四分之三（半身，透视）：看得到前伸 1px 的侧面与 1px 中缝
    bride_bust_front.png        胸部特写（正面正交）
    bride_bust_three_quarter.png 胸部特写（四分之三）—— 凸出与中缝最清楚
    bride_side.png              侧视（正交）：1px 前伸在轮廓上的台阶
    *_cutout.png                同机位的 alpha 剔除版（= 游戏里 entityCutout 的样子）
    bride_zombie_scene.blend / bride_zombie_render_report.json
"""
import json
import math
import os

import bpy
from mathutils import Vector

BASE = 'F:/mcmod'
ART = BASE + '/art/bride'
TEX = BASE + '/src/main/resources/assets/apocalypse_zombies/textures/entity/bride_zombie.png'
BLEND = ART + '/bride_zombie_scene.blend'
REPORT = ART + '/bride_zombie_render_report.json'
TW = TH = 64.0
RESO = int(os.environ.get('BRIDE_RESO', '1000'))
SAMPLES = int(os.environ.get('BRIDE_SAMPLES', '32'))
# 只重渲指定视角（逗号分隔，名字见 views / 'bust_annotated'），留空 = 全部
ONLY = [s.strip() for s in os.environ.get('BRIDE_ONLY', '').split(',') if s.strip()]

# name, x0,y0,z0, x1,y1,z1, texu, texv, (uv_w, uv_h, uv_d) or None
BOXES = [
    ('head',   -4.0, -8.0, -4.0,   4.0,  0.0,  4.0,   0,  0, None),
    ('hat',    -4.5, -8.5, -4.5,   4.5,  0.5,  4.5,  32,  0, (8, 8, 8)),   # inflate .5，UV 仍是 8³
    ('body',   -4.0,  0.0, -2.0,   4.0, 12.0,  2.0,  16, 16, None),
    ('rarm',   -8.0,  0.0, -2.0,  -4.0, 12.0,  2.0,  40, 16, None),
    ('larm',    4.0,  0.0, -2.0,   8.0, 12.0,  2.0,  32, 48, None),
    ('rleg',   -3.9, 12.0, -2.0,   0.1, 24.0,  2.0,   0, 16, None),
    ('lleg',   -0.1, 12.0, -2.0,   3.9, 24.0,  2.0,  16, 48, None),
    ('bust_r', -2.5,  1.0, -3.02, -0.5,  4.0, -2.02,  0, 32, None),
    ('bust_l',  0.5,  1.0, -3.02,  2.5,  4.0, -2.02, 12, 32, None),
]
BUST_RECTS = {'bust_r': (0, 32, 6, 4), 'bust_l': (12, 32, 6, 4)}

FACES = ('top', 'bottom', 'right', 'left', 'front', 'back')
FNORM = {'top': (0, -1, 0), 'bottom': (0, 1, 0), 'right': (-1, 0, 0),
         'left': (1, 0, 0), 'front': (0, 0, -1), 'back': (0, 0, 1)}

report = {'blender': bpy.app.version_string, 'engine': None, 'renders': [],
          'errors': [], 'boxes': {}, 'uv_alpha': {}}


# ------------------------------------------------------------------ 工具
def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)
    for ma in list(bpy.data.materials):
        bpy.data.materials.remove(ma)
    for co in list(bpy.data.collections):
        bpy.data.collections.remove(co)


def B(p):
    """MC(x,y,z) -> Blender：MC -Z(正面)->+Y，MC -Y(上)->+Z，det=+1 不镜像。"""
    return Vector((-p[0], -p[2], -p[1]))


def face_layout(f, x0, y0, z0, x1, y1, z1, u, v, w, h, d):
    """返回 (P, U, V, rect_u0v0, (qw, qh))：U=贴图向右方向，V=贴图向下方向。"""
    if f == 'top':                                   # -y：顶面
        return (x0, y0, z0), (1, 0, 0), (0, 0, 1), (u + d, v), (w, d)
    if f == 'bottom':                                # +y：底面
        return (x1, y1, z0), (-1, 0, 0), (0, 0, 1), (u + d + w, v), (w, d)
    if f == 'right':                                 # -x 面
        return (x0, y0, z1), (0, 0, -1), (0, 1, 0), (u, v + d), (d, h)
    if f == 'left':                                  # +x 面
        return (x1, y0, z0), (0, 0, 1), (0, 1, 0), (u + d + w, v + d), (d, h)
    if f == 'front':                                 # -z 面（正面）
        return (x0, y0, z0), (1, 0, 0), (0, 1, 0), (u + d, v + d), (w, h)
    return (x1, y0, z1), (-1, 0, 0), (0, 1, 0), (u + d + w + d, v + d), (w, h)   # back


def build_geometry():
    mats = make_materials()
    img = mats['image']
    col = bpy.data.collections.new('bride_zombie')
    bpy.context.scene.collection.children.link(col)
    bb = [1e9, 1e9, 1e9, -1e9, -1e9, -1e9]
    for (name, x0, y0, z0, x1, y1, z1, tu, tv, uvd) in BOXES:
        w, h, d = x1 - x0, y1 - y0, z1 - z0
        uw, uh, ud = uvd if uvd else (w, h, d)
        verts, faces, uvs, rects = [], [], [], {}
        for f in FACES:
            P, U, V, (u0, v0), (qw, qh) = face_layout(f, x0, y0, z0, x1, y1, z1,
                                                      tu, tv, uw, uh, ud)
            quad = [Vector(P),
                    Vector([P[i] + U[i] * qw for i in range(3)]),
                    Vector([P[i] + U[i] * qw + V[i] * qh for i in range(3)]),
                    Vector([P[i] + V[i] * qh for i in range(3)])]
            uv = [(u0, v0), (u0 + qw, v0), (u0 + qw, v0 + qh), (u0, v0 + qh)]
            n = (quad[1] - quad[0]).cross(quad[2] - quad[0])
            if n.dot(Vector(FNORM[f])) < 0:          # 卷绕反了就整体倒序（UV 跟着顶点走）
                quad = quad[::-1]
                uv = uv[::-1]
            base = len(verts)
            verts.extend([B(q) for q in quad])
            faces.append((base, base + 1, base + 2, base + 3))
            uvs.append(uv)
            rects[f] = [u0, v0, qw, qh]
            for q in quad:
                p = B(q)
                bb[0] = min(bb[0], p.x); bb[1] = min(bb[1], p.y); bb[2] = min(bb[2], p.z)
                bb[3] = max(bb[3], p.x); bb[4] = max(bb[4], p.y); bb[5] = max(bb[5], p.z)
        me = bpy.data.meshes.new(name + '_mesh')
        me.from_pydata([tuple(v) for v in verts], [], [f for f in faces])
        me.update()
        me.validate()
        if not me.uv_layers:
            me.uv_layers.new(name='UVMap')
        lay = me.uv_layers[0]
        for fi, rect in enumerate(uvs):
            for i in range(4):
                u, v = rect[i]
                lay.data[fi * 4 + i].uv = Vector((u / TW, 1.0 - v / TH))
        for m in (mats['opaque'], mats['cutout']):
            me.materials.append(m)
        ob = bpy.data.objects.new(name, me)
        col.objects.link(ob)
        report['boxes'][name] = {'mc': [x0, y0, z0, x1, y1, z1], 'dims': [w, h, d],
                                 'texOffs': [tu, tv], 'uv_dims': [uw, uh, ud],
                                 'uv_rects': rects}
        report['uv_alpha'][name] = uv_coverage(img, rects)
    report['blender_bbox'] = [round(v, 3) for v in bb]
    return col, mats, bb


def uv_coverage(img, rects):
    """每个面在贴图上被画了多少（alpha>0.5 的占比）：验证有没有露出透明黑洞。"""
    px = img.pixels[:]
    W, H = img.size
    out = {}
    for f, (u0, v0, w, h) in rects.items():
        tot = 0
        hit = 0
        for y in range(int(v0), int(v0 + h)):
            for x in range(int(u0), int(u0 + w)):
                if not (0 <= x < W and 0 <= y < H):
                    tot += 1
                    continue
                i = ((H - 1 - y) * W + x) * 4          # Blender 图像自下往上存
                tot += 1
                if px[i + 3] > 0.5:
                    hit += 1
        out[f] = round(hit / float(tot), 3) if tot else 0.0
    return out


def make_materials():
    img = bpy.data.images.load(TEX, check_existing=True)
    img.colorspace_settings.name = 'sRGB'
    report['image'] = [img.size[0], img.size[1], img.filepath]
    made = {}
    for key, use_alpha in (('opaque', False), ('cutout', True)):
        ma = bpy.data.materials.new('bride_' + key)
        ma.use_nodes = True
        nt = ma.node_tree
        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        tex.interpolation = 'Closest'
        tex.location = (-420, 120)
        nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        if use_alpha:
            nt.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
        bsdf.inputs['Roughness'].default_value = 0.85
        bsdf.inputs['Metallic'].default_value = 0.0
        for nm in ('Specular IOR Level', 'Specular'):
            if nm in bsdf.inputs:
                bsdf.inputs[nm].default_value = 0.25
                break
        made[key] = ma
    made['image'] = img
    return made


# ------------------------------------------------------------------ 灯光/相机
def setup_world():
    sc = bpy.context.scene
    try:
        sc.render.engine = 'CYCLES'
    except Exception as e:                              # 兜底：EEVEE
        report['errors'].append('cycles-unavailable:' + repr(e))
        sc.render.engine = 'BLENDER_EEVEE'
    report['engine'] = sc.render.engine
    try:
        if sc.render.engine == 'CYCLES':
            sc.cycles.device = 'CPU'
            sc.cycles.samples = SAMPLES
            sc.cycles.use_adaptive_sampling = True
            sc.cycles.adaptive_threshold = 0.02
            sc.cycles.use_denoising = True
            sc.cycles.max_bounces = 4
            sc.cycles.diffuse_bounces = 3
            sc.cycles.transmission_bounces = 2
        else:
            ee = sc.eevee
            ee.taa_render_samples = max(SAMPLES, 16)
            ee.use_shadows = True
            ee.use_raytracing = True
            ee.shadow_ray_count = 2
            ee.shadow_step_count = 12
            ee.use_fast_gi = True
            ee.fast_gi_method = 'AMBIENT_OCCLUSION_ONLY'
    except Exception as e:
        report['errors'].append('engine-setup:' + repr(e))
    sc.render.resolution_x = RESO
    sc.render.resolution_y = RESO
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
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
        bg.inputs[0].default_value = (0.10, 0.11, 0.13, 1.0)
        bg.inputs[1].default_value = 0.55
    sc.world = w
    cam_data = bpy.data.cameras.new('Cam')
    cam_data.lens = 50.0
    cam_data.sensor_width = 36.0
    cam = bpy.data.objects.new('Cam', cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    # 正面是 Blender +Y：key 从观察者左上（+x,+y）来，fill 右上，rim 背后
    for nm, frm, energy in (('key', (7.0, 8.5, 11.0), 3.2),
                            ('fill', (-8.0, 6.0, 3.0), 1.3),
                            ('rim', (-1.5, -9.0, 6.0), 2.2),
                            ('front', (0.8, 14.0, 2.0), 0.9)):
        ld = bpy.data.lights.new(nm, 'SUN')
        ld.energy = energy
        ld.angle = math.radians(3.0)
        lo = bpy.data.objects.new(nm, ld)
        aim(lo, frm, (0.0, 0.0, -6.0))
        sc.collection.objects.link(lo)
    return cam


def aim(ob, frm, to):
    d = Vector(to) - Vector(frm)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def look_at(cam, loc, target, ortho=None, lens=50.0):
    cam.location = Vector(loc)
    d = (Vector(target) - Vector(loc))
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        cam.data.ortho_scale = ortho
    else:
        cam.data.lens = lens


def shoot(name, cam, loc, target, ortho=None, lens=50.0):
    look_at(cam, loc, target, ortho, lens)
    path = '%s/bride_%s.png' % (ART, name)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    report['renders'].append([os.path.basename(path), size])
    print('RENDER %s %d bytes' % (path, size))
    return path


def orbit(target, az_deg, el_deg, dist):
    """target 周围的机位：az 从正面(+Y)往 +X 转，el 抬高。"""
    az, el = math.radians(az_deg), math.radians(el_deg)
    return (target[0] + dist * math.cos(el) * math.sin(az),
            target[1] + dist * math.cos(el) * math.cos(az),
            target[2] + dist * math.sin(el))


def set_material_slot(slot):
    for ob in bpy.data.objects:
        if ob.type == 'MESH':
            for i in range(len(ob.material_slots)):
                ob.material_slots[i].material = ob.data.materials[slot]


# ------------------------------------------------- 标注（只在 *_annotated 里用）
def emissive(name, rgb, strength=2.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs[0].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    em.inputs[1].default_value = strength
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def mk_box_obj(name, mc0, mc1, mat, wire=False, thickness=0.07):
    """MC 轴对齐盒 -> Blender 立方体（Blender 轴 = MC(x, z, y)）。"""
    c = [(mc0[i] + mc1[i]) / 2.0 for i in range(3)]
    d = [abs(mc1[i] - mc0[i]) / 2.0 for i in range(3)]
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=tuple(B(c)))
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (d[0], d[2], d[1])
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    if wire:
        md = ob.modifiers.new('wire', 'WIREFRAME')
        md.thickness = thickness
        md.use_replace = True
        md.use_boundary = True
    return ob


FONT_CANDIDATES = ('C:/Windows/Fonts/simhei.ttf', 'C:/Windows/Fonts/msyh.ttc',
                   'C:/Windows/Fonts/Deng.ttf')


def mk_label(name, text, loc, rot, size, mat):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = text
    cu.size = size
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                cu.font = bpy.data.fonts.load(p)
                break
            except Exception as e:
                report['errors'].append('font:' + p + repr(e))
    ob = bpy.data.objects.new(name, cu)
    ob.location = Vector(loc)
    ob.rotation_euler = rot
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def mk_backer(name, loc, rot, text, size):
    """标签后面的深色底板（相机朝向），保证任何背景下都能看清字。"""
    cjk = sum(1 for ch in text if ord(ch) > 0x2E80)
    w = size * (cjk * 1.05 + (len(text) - cjk) * 0.62) * 1.14 + size * 0.3
    h = size * 1.7
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=tuple(loc))
    ob = bpy.context.active_object
    ob.name = name
    ob.rotation_euler = rot
    ob.scale = (w / 2.0, h / 2.0, 0.03)
    mat = emissive('anno_backer_mat', (0.02, 0.02, 0.03), 1.0)
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return ob


def annotated_shot(cam, chest, mats):
    """胸部特写 + 尺寸标注：青=两块轮廓、品红=1px 中缝、绿=1px 前伸。"""
    cyan = emissive('anno_cyan', (0.10, 0.85, 1.00), 2.0)
    mag = emissive('anno_magenta', (1.00, 0.05, 0.55), 2.5)
    grn = emissive('anno_green', (0.35, 1.00, 0.20), 2.2)
    lbl = emissive('anno_label', (1.00, 1.00, 1.00), 2.0)
    for nm, (x0, y0, z0, x1, y1, z1, tu, tv, uvd) in ((b[0], b[1:]) for b in
                                                     [bo for bo in BOXES]):
        if nm in ('bust_r', 'bust_l'):
            mk_box_obj('anno_out_' + nm, (x0, y0, z0), (x1, y1, z1), cyan, wire=True)
    mk_box_obj('anno_gap', (-0.5, 1.0, -3.02), (0.5, 4.0, -2.02), mag)          # 1px 中缝
    mk_box_obj('anno_depth', (-2.5, 4.35, -3.02), (2.5, 4.75, -2.02), grn)      # 1px 前伸

    tgt = Vector((chest.x, chest.y, chest.z))
    loc = Vector(orbit(tgt, 40.0, 20.0, 14.0))
    q = (tgt - loc).to_track_quat('-Z', 'Y')
    m = q.to_matrix()
    right = m @ Vector((1, 0, 0))
    up = m @ Vector((0, 1, 0))
    fwd = m @ Vector((0, 0, -1))
    rot = q.to_euler()
    # 标签朝相机方向前移 3 个单位（免得被头/帽子挡住），同时按透视比例缩小平面偏移，
    # 这样屏幕上的落点不变：(R-p)/R = 11/14
    k = 11.0 / 14.0
    for nm, txt, rx, ry, col in (('l1', '新加胸块 ×2（青框）', -1.4, 4.30, cyan),
                                 ('l2', '前伸 1px（绿条长度）', -1.4, -4.20, grn),
                                 ('l3', '中缝 1px（品红）', 2.6, -2.90, mag)):
        p = tgt + (right * rx + up * ry) * k - fwd * 3.0
        mk_backer('anno_bg_' + nm, tuple(p + fwd * 0.14), rot, txt, 0.50)
        mk_label('anno_' + nm, txt, tuple(p), rot, 0.50, col)
    return shoot('bust_annotated', cam, tuple(loc), tuple(tgt), None, 50.0)


def main():
    clear_scene()
    col, mats, bb = build_geometry()
    cam = setup_world()
    ctr = Vector(((bb[0] + bb[3]) / 2.0, (bb[1] + bb[4]) / 2.0, (bb[2] + bb[5]) / 2.0))
    span = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
    report['blender_center'] = [round(v, 3) for v in ctr]
    report['span'] = round(span, 3)
    print('BBOX %s center %s span %.2f' % (report['blender_bbox'], list(ctr), span))

    # 胸部（MC y 1..4, z -3.02..-2.02, x -2.5..2.5）在 Blender 里的位置
    chest = B((0.0, 2.5, -3.02))
    print('CHEST_BL %s' % list(chest))

    ortho_full = span * 1.06
    front_loc = (ctr.x, ctr.y + span * 1.9, ctr.z)
    side_loc = (ctr.x + span * 1.9, ctr.y, ctr.z)
    # 半身四分之三：MC y=-8.5(头顶)..13(大腿) -> Blender z -13..8.5
    half_t = Vector((0.0, 0.0, -2.2))
    half_d = 30.0

    views = [
        ('front', front_loc, tuple(ctr), ortho_full, 50.0),
        ('side', side_loc, tuple(ctr), ortho_full, 50.0),
        ('three_quarter', orbit(half_t, 38.0, 15.0, half_d), tuple(half_t), None, 50.0),
        ('three_quarter_full', orbit(ctr, 38.0, 12.0, 88.0), tuple(ctr), None, 85.0),
        ('bust_front', (chest.x, chest.y + 16.0, chest.z + 0.2), tuple(chest), 7.4, 50.0),
        ('bust_three_quarter', orbit((chest.x, chest.y - 0.4, chest.z), 46.0, 12.0, 12.0),
         (chest.x, chest.y - 0.4, chest.z), None, 55.0),
    ]
    ok = []
    want = ONLY
    for name, loc, tgt, ortho, lens in views:
        if want and name not in want:
            continue
        ok.append(shoot(name, cam, loc, tgt, ortho, lens))
    report['front_view'] = (ART + '/bride_front.png').replace('\\', '/')
    report['three_quarter_view'] = (ART + '/bride_three_quarter.png').replace('\\', '/')

    # alpha 剔除版（= 游戏 entityCutout 的样子：刘海之间的透明像素不挡脸）
    set_material_slot(1)
    for name, loc, tgt, ortho, lens in (views[0], views[2], views[3], views[5]):
        if want and (name + '_cutout') not in want:
            continue
        ok.append(shoot(name + '_cutout', cam, loc, tgt, ortho, lens))
    set_material_slot(0)

    # ---- 带尺寸标注的胸部特写（自发光标记 + 文字，仅此一张）------------
    if not want or 'bust_annotated' in want:
        try:
            ok.append(annotated_shot(cam, chest, mats))
        except Exception as e:
            report['errors'].append('annotated:' + repr(e))

    # 交付清单 = 目录里实际存在的全部 bride_*.png（含只重渲部分时的既有产物）
    expected = [os.path.join(ART, 'bride_%s.png' % n) for n, _, _, _, _ in views]
    expected += [os.path.join(ART, 'bride_%s_cutout.png' % n)
                 for n, _, _, _, _ in (views[0], views[2], views[3], views[5])]
    expected.append(os.path.join(ART, 'bride_bust_annotated.png'))
    report['files'] = [p.replace('\\', '/') for p in expected if os.path.exists(p)]
    report['rendered_now'] = [p.replace('\\', '/') for p in ok]

    try:
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
        report['blend'] = os.path.getsize(BLEND)
    except Exception as e:
        report['errors'].append('save:' + repr(e))
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print('BUILD_REPORT ' + json.dumps({k: v for k, v in report.items()
                                        if k not in ('boxes', 'uv_alpha')},
                                       ensure_ascii=False))


if __name__ == '__main__':
    main()