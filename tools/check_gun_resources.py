#!/usr/bin/env python3
"""枪械资源接线自检：Java 里声明的每一个资源路径，磁盘上必须真的有对应文件。

编译器只管类型，管不了资源路径 —— 而拼错一个字符的表现是"枪在游戏里不显示"，
既没有报错也没有堆栈。这个脚本把 Java 源码当成配置来读，逐条对照磁盘：

  1. registry/ModItems.java 里注册的每把枪
  2. 它 client/model/*GeoModel.java 里声明的 geo / texture / animation 三个路径
  3. geo.json 的骨名必须覆盖 animation.json 里所有被驱动的骨
  4. 贴图必须是 512x512（美术规范 四）
  5. 源码里引用的 damage_type json 必须存在
  6. models/item/<id>.json 必须存在
  7. 两套 lang 里 item.<mod>.<id> 与 death.attack.<damage_type> 必须齐
  8. ModSounds.java 注册的每个 SoundEvent 都要有 sounds.json 键，且引用的 .ogg 真的在磁盘上
  9. 非枪物品（刷怪蛋）也要有 models/item/<id>.json（刷怪蛋的 parent 必须是原版 template_spawn_egg）与两套 lang

退出码 0 = 全部对上。用法：python tools/check_gun_resources.py
"""

from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JAVA = ROOT / "src/main/java/com/apocalypse/zombies"
RES = ROOT / "src/main/resources"
ASSETS = RES / "assets/apocalypse_zombies"
MOD_ID = "apocalypse_zombies"

fails: list[str] = []
notes: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        fails.append(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def png_size(path: Path) -> tuple[int, int] | None:
    """贴图宽高，直接读 PNG 头 —— 不装 Pillow 也能验。"""
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", header[16:24])


def png_pixels(path: Path) -> tuple[int, int, bytes] | None:
    """解出 8 位 RGB/RGBA PNG 的像素（同样不装 Pillow）。

    只支持无交错的 8 位色深、颜色类型 2/6 —— 本项目的导出图都属这一类；
    其它情况返回 None，调用方跳过像素级检查而不是误报。返回 (w, h, rgba)。
    """
    import zlib

    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, width, height, depth, color = 8, 0, 0, 0, 0
    idat = bytearray()
    while pos + 8 <= len(raw):
        (length,) = struct.unpack(">I", raw[pos : pos + 4])
        kind = raw[pos + 4 : pos + 8]
        data = raw[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", data[:10])
        elif kind == b"IDAT":
            idat += data
        elif kind == b"IEND":
            break
        pos += 12 + length
    if not width or depth != 8 or color not in (2, 6):
        return None
    channels = 4 if color == 6 else 3
    stride = width * channels
    buf = zlib.decompress(bytes(idat))
    out = bytearray(width * height * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(height):
        filt = buf[p]
        p += 1
        line = bytearray(buf[p : p + stride])
        p += stride
        if filt == 1:  # Sub
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filt == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filt == 3:  # Average
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filt == 4:  # Paeth
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up = prev[i]
                upleft = prev[i - channels] if i >= channels else 0
                pa, pb, pc = abs(up - upleft), abs(left - upleft), abs(left + up - 2 * upleft)
                pred = left if (pa <= pb and pa <= pc) else (up if pb <= pc else upleft)
                line[i] = (line[i] + pred) & 0xFF
        elif filt != 0:
            return None
        row = y * width * 4
        for x in range(width):
            src = x * channels
            out[row + x * 4 : row + x * 4 + 3] = line[src : src + 3]
            out[row + x * 4 + 3] = line[src + 3] if channels == 4 else 255
        prev = line
    return width, height, bytes(out)


# --- 1. 注册了哪些枪 ------------------------------------------------------
registry = read(JAVA / "registry/ModItems.java")
# 刷怪蛋同样是 ITEMS.register(...) -> new ForgeSpawnEggItem(...)，但它们没有 GeoModel，
# 不是本脚本的检查对象 —— 不过滤掉会稳定报 4 条假失败，把真问题淹没掉。
guns = [
    entry
    for entry in re.findall(r'ITEMS\.register\("([a-z0-9_]+)",\s*\(\)\s*->\s*new\s+(\w+Item)\(', registry)
    if entry[1] != "ForgeSpawnEggItem"
]
check(bool(guns), "ModItems.java 里没解析到任何枪械注册")
notes.append(f"注册的枪：{', '.join(f'{i}({c})' for i, c in guns)}")

for item_id, item_class in guns:
    # --- 2. 模型绑定的三个路径 ---
    model_file = JAVA / f"client/model/{item_class.removesuffix('Item')}GeoModel.java"
    check(model_file.exists(), f"{item_class}: 找不到模型绑定 {model_file.name}")
    if not model_file.exists():
        continue
    source = read(model_file)
    declared = re.findall(r'RESOURCE\s*=\s*\n?\s*new\s+ResourceLocation\([^,]+,\s*"([^"]+)"', source)
    declared += re.findall(r'new\s+ResourceLocation\(ApocalypseZombies\.MOD_ID,\s*"([^"]+)"\)', source)
    check(len(declared) >= 3, f"{item_id}: 模型绑定里只解析到 {len(declared)} 个资源路径（应有 geo/texture/animation）")
    for rel in declared:
        target = ASSETS / rel
        check(target.exists(), f"{item_id}: 声明的资源不存在 -> {rel}")
        notes.append(f"  {item_id}: {rel} {'OK' if target.exists() else '缺失'}")

    geo_rel = next((r for r in declared if r.endswith(".geo.json")), None)
    anim_rel = next((r for r in declared if r.endswith(".animation.json")), None)
    tex_rel = next((r for r in declared if r.endswith(".png")), None)

    # --- 3. 骨名对齐 ---
    if geo_rel and anim_rel and (ASSETS / geo_rel).exists() and (ASSETS / anim_rel).exists():
        geo = json.loads((ASSETS / geo_rel).read_text(encoding="utf-8"))
        anim = json.loads((ASSETS / anim_rel).read_text(encoding="utf-8"))
        bones: set[str] = set()
        for geometry in geo.get("minecraft:geometry", []):
            for bone in geometry.get("bones", []):
                bones.add(bone["name"])
        driven: set[str] = set()
        clips: list[str] = []
        for clip_name, clip in anim.get("animations", {}).items():
            clips.append(clip_name)
            driven.update(clip.get("bones", {}).keys())
        missing = driven - bones
        check(not missing, f"{item_id}: 动画驱动的骨在 geo 里不存在 -> {sorted(missing)}")
        check(len(clips) >= 4, f"{item_id}: 动画只有 {len(clips)} 条，偏少")
        notes.append(f"  {item_id}: {len(bones)} 骨 / {len(clips)} 条动画 {clips}，驱动骨全部对齐")
        # 静止动画名要与 Java 常量对得上
        item_source = read(JAVA / f"item/{item_class}.java")
        for const in re.findall(r'String ANIM_\w+\s*=\s*"([^"]+)"', item_source):
            check(const in clips, f"{item_id}: Java 引用了动画 {const!r}，但文件里没有")
        for const in re.findall(r'String TRIGGER_\w+\s*=\s*"([^"]+)"', item_source):
            check(const in clips, f"{item_id}: Java 的 trigger {const!r} 在动画文件里没有同名 clip")

    # --- 4. 贴图必须 512 ---
    if tex_rel and (ASSETS / tex_rel).exists():
        size = png_size(ASSETS / tex_rel)
        check(size == (512, 512), f"{item_id}: 贴图是 {size}，美术规范要求 512x512")

    # --- 4b. 逐面 UV 必须落在真正涂绘过的像素上 ---
    # 尺寸对、文件在，不代表内容完整：生成器把图集写到 art/m1garand/，资源目录那份靠手工拷贝，
    # 一旦漏拷，大量面会采到全透明区 → 游戏里渲染成纯黑。M1 加兰德就是这样漏掉的
    # （旧图只画到 V=237，而模型 UV 用到 V=322，1514/2076 个面全黑）。
    if tex_rel and geo_rel and (ASSETS / tex_rel).exists() and (ASSETS / geo_rel).exists():
        pixels = png_pixels(ASSETS / tex_rel)
        if pixels is None:
            notes.append(f"  {item_id}: 贴图非 8 位 RGB/RGBA，跳过逐面 UV 涂绘检查")
        else:
            width, height, rgba = pixels
            geometry = json.loads((ASSETS / geo_rel).read_text(encoding="utf-8"))
            blank: list[str] = []
            faces_total = 0
            for bone in geometry.get("minecraft:geometry", [{}])[0].get("bones", []):
                for cube in bone.get("cubes", []):
                    for face, rect in (cube.get("uv") or {}).items():
                        if not isinstance(rect, dict):
                            continue
                        u, v = rect["uv"]
                        rw, rh = rect["uv_size"]
                        u0, u1 = sorted((int(u), int(u + rw)))
                        v0, v1 = sorted((int(v), int(v + rh)))
                        u0, u1 = max(0, u0), min(width, u1)
                        v0, v1 = max(0, v0), min(height, v1)
                        if u0 >= u1 or v0 >= v1:
                            continue
                        faces_total += 1
                        if not any(
                            rgba[((y * width) + x) * 4 + 3] > 8
                            for y in range(v0, v1)
                            for x in range(u0, u1)
                        ):
                            blank.append(f"{bone['name']}.{face}")
            ratio = 100 * len(blank) / max(faces_total, 1)
            check(
                not blank,
                f"{item_id}: {len(blank)}/{faces_total} 个面（{ratio:.0f}%）的 UV 落在全透明区，"
                f"多半是贴图被截断/过期（旧导出），例：{blank[:6]}",
            )
            notes.append(f"  {item_id}: {faces_total} 个面的 UV 均落在涂绘区（空白 {len(blank)} 个）")

    # --- 5. damage_type ---
    item_source = read(JAVA / f"item/{item_class}.java")
    damage = re.search(r'ResourceLocation\(ApocalypseZombies\.MOD_ID,\s*"(\w+_bullet)"\)', item_source)
    if damage:
        damage_id = damage.group(1)
        dtype = RES / f"data/{MOD_ID}/damage_type/{damage_id}.json"
        check(dtype.exists(), f"{item_id}: damage_type 文件缺失 -> {dtype.name}")
        if dtype.exists():
            check(json.loads(dtype.read_text(encoding="utf-8")).get("message_id") == damage_id,
                  f"{item_id}: {dtype.name} 的 message_id 与文件名不一致")
    else:
        fails.append(f"{item_id}: 源码里没解析到 damage_type id")

    # --- 8. 动作时长契约：Java 的 *_TICKS 必须等于动画片段长度 ---
    if anim_rel and (ASSETS / anim_rel).exists():
        clips = json.loads((ASSETS / anim_rel).read_text(encoding="utf-8")).get("animations", {})
        wanted = {
            "SHOOT_TICKS": "shoot",
            "BOLT_TICKS": "bolt",
            "RELOAD_TACTICAL_TICKS": "reload_tactical",
            "RELOAD_EMPTY_TICKS": "reload_empty",
            "DRAW_TICKS": "draw",
            "AUTO_CYCLE_TICKS": "shoot_auto",
        }
        for const, clip in wanted.items():
            found = re.search(rf"int {const}\s*=\s*(\d+);", item_source)
            if not found or clip not in clips:
                continue
            # 契约是"clip 长度 x 20 向上取整"（见 art/awm/README.md）：
            # bolt 1.2667s -> 25.33 -> 26；reload_empty 3.7167s -> 74.33 -> 75
            declared_ticks = int(found.group(1))
            real_ticks = -(-int(round(clips[clip]["animation_length"] * 20 * 1000)) // 1000)
            check(declared_ticks == real_ticks,
                  f"{item_id}: {const}={declared_ticks} 与动画 {clip} 的 {real_ticks} ticks 不一致")
        notes.append(f"  {item_id}: 动作时长常量与动画片段长度一致")

    # --- 9. 开镜姿态契约：GunItem.adsPitch()/adsYaw() 必须等于模型的 display 旋转 ---
    # GunPose 在瞄准时抵消的就是这个旋转：display 的旋转绕在姿态层**内侧**，不抵消的话瞄具线
    # 只能是“平行但偏轴”，任何 ADS_X/ADS_Y 都调不出共线。两者漂开 = 右键打不准。见 GunItem#adsPitch()。
    model_json = ASSETS / f"models/item/{item_id}.json"
    if model_json.exists():
        display = json.loads(model_json.read_text(encoding="utf-8")).get("display", {})
        right = display.get("firstperson_righthand", {})
        rot = right.get("rotation")
        if rot:
            pitch = re.search(r"float DISPLAY_PITCH\s*=\s*(-?[\d.]+)F;", item_source)
            yaw = re.search(r"float DISPLAY_YAW\s*=\s*(-?[\d.]+)F;", item_source)
            check(pitch is not None and yaw is not None,
                  f"{item_id}: 源码里没解析到 DISPLAY_PITCH/DISPLAY_YAW（瞄准时要抵消的 display 旋转）")
            if pitch and yaw:
                check(abs(float(pitch.group(1)) - rot[0]) < 1e-6
                      and abs(float(yaw.group(1)) - rot[1]) < 1e-6,
                      f"{item_id}: DISPLAY_PITCH/YAW={pitch.group(1)}/{yaw.group(1)} 与 "
                      f"models/item/{item_id}.json 的 firstperson rotation {rot[:2]} 不一致")
                check(abs(rot[2]) < 1e-6,
                      f"{item_id}: firstperson righthand rotation 的 roll={rot[2]} 不为 0 —— "
                      f"GunPose 只抵消 pitch/yaw")
                left = display.get("firstperson_lefthand", {}).get("rotation")
                if left:
                    check(abs(left[0] - rot[0]) < 1e-6 and abs(left[1] - rot[1]) < 1e-6,
                          f"{item_id}: firstperson_lefthand 的 rotation 应与 righthand 相同"
                          f"（左右手镜像由 vanilla 在运行时做）")
                notes.append(f"  {item_id}: display 旋转 {rot[:2]} 与 DISPLAY_PITCH/YAW 一致"
                             f"（瞄准时由 GunPose 精确抵消）")
        # ADS 位移必须与量算一致（工具会自动比对；这里只防"填了但明显不对"）
        ads = re.search(r"float ADS_X\s*=\s*(-?[\d.]+)F;[\s\S]{0,80}?float ADS_Y\s*=\s*(-?[\d.]+)F;",
                        item_source)
        if ads and rot:
            ax, ay = float(ads.group(1)), float(ads.group(2))
            check(-0.60 < ax < -0.35 and 0.25 < ay < 0.45,
                  f"{item_id}: ADS_X/ADS_Y={ax}/{ay} 不在量算区间（约 −0.475 / 0.346）——"
                  f"跑 tools/pose_measure.py 重新量")
            notes.append(f"  {item_id}: ADS 位移 ({ax}, {ay}) 在量算区间内")

    # --- 6. 物品模型 ---
    check((ASSETS / f"models/item/{item_id}.json").exists(), f"{item_id}: models/item/{item_id}.json 缺失")

    # --- 7. lang ---
    for lang in ("lang/zh_cn.json", "lang/en_us.json"):
        table = json.loads((ASSETS / lang).read_text(encoding="utf-8"))
        check(f"item.{MOD_ID}.{item_id}" in table, f"{item_id}: {lang} 缺 item.{MOD_ID}.{item_id}")
        if damage:
            check(f"death.attack.{damage.group(1)}" in table, f"{item_id}: {lang} 缺 death.attack.{damage.group(1)}")

# --- 8. 音效接线 ----------------------------------------------------------
# 注册了 SoundEvent 而 sounds.json 里没有同名键，客户端启动时会逐条刷
# "Missing sound for event: <id>"：不崩，但那个声音永远不会响（ammo_clip_pop 就是这样漏的）。
sound_source = read(JAVA / "registry/ModSounds.java")
sound_ids = re.findall(r'sound\("([a-z0-9_]+)"\)', sound_source)
check(bool(sound_ids), "ModSounds.java 里没解析到任何 SoundEvent 注册")
sound_table = json.loads((ASSETS / "sounds.json").read_text(encoding="utf-8"))
check(not [s for s in sound_ids if s not in sound_table],
      f"sounds.json 缺事件键（客户端会刷 Missing sound）：{[s for s in sound_ids if s not in sound_table]}")
check(not [s for s in sound_table if s not in sound_ids],
      f"sounds.json 里有没注册过的死键：{[s for s in sound_table if s not in sound_ids]}")
for sound_id, entry in sound_table.items():
    for sample in entry.get("sounds", []):
        name = sample["name"] if isinstance(sample, dict) else sample
        rel = name.split(":", 1)[1]
        check((ASSETS / "sounds" / f"{rel}.ogg").exists(),
              f"sounds.json 的 {sound_id} 指向不存在的文件 -> sounds/{rel}.ogg")
notes.append(f"  {len(sound_ids)} 个 SoundEvent：sounds.json 键与 .ogg 文件全部对上")

# --- 9. 其余物品（刷怪蛋）的模型与 lang -----------------------------------
# 枪已由上面覆盖；刷怪蛋最容易漏 —— Forge 只为 ForgeSpawnEggItem 自动注册染色，
# 模型仍得自己写，漏了就是物品栏里一个紫黑 missing 方块加一行 Unable to load model。
gun_ids = {item_id for item_id, _ in guns}
other_items = [
    entry
    for entry in re.findall(r'ITEMS\.register\("([a-z0-9_]+)",\s*\(\)\s*->\s*new\s+(\w+Item)\(', registry)
    if entry[0] not in gun_ids
]
check(bool(other_items), "ModItems.java 里没解析到刷怪蛋之类的非枪物品注册")
for item_id, item_class in other_items:
    model_file = ASSETS / f"models/item/{item_id}.json"
    check(model_file.exists(),
          f"{item_id}: models/item/{item_id}.json 缺失（物品栏里会渲染成紫黑 missing 模型）")
    if item_class == "ForgeSpawnEggItem" and model_file.exists():
        parent = json.loads(model_file.read_text(encoding="utf-8")).get("parent")
        check(parent == "minecraft:item/template_spawn_egg",
              f"{item_id}: 刷怪蛋模型 parent={parent!r}，应为 'minecraft:item/template_spawn_egg'")
    for lang in ("lang/zh_cn.json", "lang/en_us.json"):
        table = json.loads((ASSETS / lang).read_text(encoding="utf-8"))
        check(f"item.{MOD_ID}.{item_id}" in table, f"{item_id}: {lang} 缺 item.{MOD_ID}.{item_id}")
notes.append(f"其他物品：{', '.join(i for i, _ in other_items)} —— model json 与两套 lang 齐")

print("=== 枪械资源接线自检 ===")
for line in notes:
    print(line)
print()
if fails:
    print(f"{len(fails)} 条不通过：")
    for line in fails:
        print("  ✗", line)
    sys.exit(1)
print(f"全部通过（{len(guns)} 把枪 + {len(other_items)} 个其他物品 + {len(sound_ids)} 个音效）")
