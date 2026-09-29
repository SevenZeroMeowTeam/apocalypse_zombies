# -*- coding: utf-8 -*-
"""十字弩 —— Blender 预览/建模场景（供 blender-mcp 执行，port 9877）.

读取 tools/crossbow_v1.py 生成的 crossbow.geo.json 与 crossbow_geo.png，
在 Blender 里重建方块格模型（骨 = 空物体层级，方块 = 网格，贴图镜像 UV），
用 EEVEE 出 4 张预览（侧视 / 斜视 / 前视 / 开镜）。
仅在 blender-mcp 的 execute 里运行才有意义（需要 bpy）。
"""
import json, math  # noqa: E402  (bpy imports below)
import os  # noqa: E402

# 供 blender-mcp exec 时 __file__ 不存在：优先用环境变量 CB_BASE，否则回退 __file__
_CB_BASE = os.environ.get('CB_BASE')
if not _CB_BASE:
    try:
        _CB_BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    except NameError:
        _CB_BASE = "C:/"
BASE = _CB_BASE
ART = os.path.join(BASE, "art", "crossbow")
GEO = os.path.join(ART, "crossbow.geo.json")
TEXPNG = os.path.join(ART, "crossbow_geo.png")

import bpy

RESULT = {}

# 清空场景（保留默认相机可忽略）
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for me in list(bpy.data.meshes):
    bpy.data.meshes.remove(me)

geo = json.load(open(GEO, encoding='utf-8'))['minecraft:geometry'][0]
img = bpy.data.images.load(TEXPNG)
TEXW = img.size[0]

def mc2bl(v):
    return (v[0], -v[2], v[1])

# 骨 -> 空物体，父级链接，位置 = pivot(转换后)
empties = {}
for b in geo['bones']:
    em = bpy.data.objects.new(b['name'], None)
    bpy.context.scene.collection.objects.link(em)
    em.empty_display_type = 'ARROWS'
    em.empty_display_size = 0.35
    em.location = mc2bl(b['pivot'])
    empties[b['name']] = em
for b in geo['bones']:
    if b.get('parent') and b['parent'] in empties:
        empties[b['name']].parent = empties[b['parent']]

def mc_rot(v):
    """MC 欧拉(rad) -> Blender 欧拉。MC (rx,ry,rz) 转 Blender：绕 Y 会镜像，近似同一正交旋转。"""
    rx, ry, rz = math.radians(v[0]), math.radians(v[1]), math.radians(v[2])
    return mathutils.Euler((rx, -rz, ry), 'XYZ') if False else mathutils.Euler((rx, rz, ry), 'XYZ')

import mathutils

def cube_bl_verts(o, s, pv, rot):
    local = [(o[0]+s[0]*kx, o[1]+s[1]*ky, o[2]+s[2]*kz)
             for kz in (0,1) for ky in (0,1) for kx in (0,1)]
    rx, ry, rz = (math.radians(a) for a in rot)
    out = []
    for v in local:
        x, y, z = v[0]-pv[0], v[1]-pv[1], v[2]-pv[2]
        y2 = y*math.cos(rx) - z*math.sin(rx); z2 = y*math.sin(rx) + z*math.cos(rx); y, z = y2, z2
        x3 = x*math.cos(ry) + z*math.sin(ry); z3 = -x*math.sin(ry) + z*math.cos(ry); x, z = x3, z3
        x4 = x*math.cos(rz) - y*math.sin(rz); y4 = x*math.sin(rz) + y*math.cos(rz); x, y = x4, y4
        out.append((x+pv[0], y+pv[1], z+pv[2]))
    return [mc2bl(v) for v in out]

# 每个方块的 6 面（按 bedrock 标准顶点顺序；UV 取该面矩形四个角）
# 顶点 local 索引 (kz,ky,kx) -> idx = kz*4 + ky*2 + kx
def build_cube_mesh(bone, cube):
    o = cube['origin']; s = cube['size']
    pv = cube.get('pivot', [o[i]+s[i]/2 for i in range(3)])
    rot = cube.get('rotation', [0,0,0])
    bl = cube_bl_verts(o, s, pv, rot)
    me = bpy.data.meshes.new('cb')
    # 面顶点索引（quad list），朝向先不管正反（双面材质避免黑面）
    quads = [
        [0,1,3,2], [4,6,7,5], [0,2,6,4], [5,7,3,1], [1,5,4,0], [2,3,7,6]
    ]
    me.from_pydata(bl, [], quads)
    uv = cube.get('uv', {})
    uvlayer = me.uv_layers.new(name='UVMap')
    # 六个面的 uv 角（按 quads 顺序给每面 4 个角，近似朝向）
    face_uvs = []
    for fname in ('north','south','east','west','up','down'):
        r = uv.get(fname)
        if not r:
            r = {'uv':[0,0],'uv_size':[2,2]}
        xu, yu = r['uv']; wu, hu = r['uv_size']
        face_uvs.append([(xu, yu), (xu+wu,yu), (xu+wu,yu+hu), (xu, yu+hu)])
    nimpl = 0
    for fi in range(6):
        udata = uvlayer.data
        for i in range(4):
            idx_poly_vert = fi*4 + i
            if idx_poly_vert < len(udata):
                ux, uy = face_uvs[fi][i]
                udata[idx_poly_vert].uv = (ux/TEXW, 1.0-uy/TEXW)
    me.materials.append(mat)
    ob = bpy.data.objects.new(me.name, me)
    bpy.context.scene.collection.objects.link(ob)
    if bone in empties:
        ob.parent = empties[bone]

mat = bpy.data.materials.new('cb_mat')
mat.use_nodes = True
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
tex = nt.nodes.new('ShaderNodeTexImage')
tex.image = img
nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.55

cube_count = 0
for bone in geo['bones']:
    for cube in bone.get('cubes', []):
        build_cube_mesh(bone['name'], cube)
        cube_count += 1
RESULT['cubes'] = cube_count

# 渲染设置（EEVEE）
scene = bpy.context.scene
eng = next(e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items
           if e.identifier.startswith('BLENDER_EEVEE'))
scene.render.engine = eng
scene.render.resolution_x = 1000
scene.render.resolution_y = 600
scene.render.film_transparent = False
w = bpy.data.worlds.new('w'); scene.world = w
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type=='BACKGROUND')
bg.inputs[0].default_value = (0.055,0.055,0.058,1)

def add_light(name, rot_deg, energy):
    lo = bpy.data.objects.new(name, bpy.data.lights.new(name,'SUN'))
    bpy.context.scene.collection.objects.link(lo)
    lo.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    lo.data.energy = energy
    return lo
add_light('sun', (60,0,-135), 4.0)
add_light('sun2', (35,0,40), 2.2)

cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
bpy.context.scene.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 55

def look_at(pos_mc, target_mc):
    from mathutils import Vector
    p = Vector(mc2bl(pos_mc)); t = Vector(mc2bl(target_mc))
    cam.location = p
    cam.rotation_euler = (t - p).to_track_quat('-Z','Y').to_euler()

def render(name):
    scene.render.filepath = os.path.join(ART, name)
    bpy.ops.render.render(write_still=True)
    return os.path.join(ART, name)

outs = {}
look_at((30,1.1,0),(0,1.0,0)); outs['side']=render('preview_side.png')
look_at((26,-26,16),(0,1.1,0)); outs['three_quarter']=render('preview_three_quarter.png')
look_at((0,-34,1.2),(0,1.0,0)); outs['front']=render('preview_front.png')
# 开镜：从目镜后方 (0,3.4,2.85) 看镜像轴前
look_at((0,6.0,2.9),(0,-2.0,2.85)); outs['ads']=render('preview_ads.png')

RESULT['renders'] = outs
RESULT['status'] = 'ok'