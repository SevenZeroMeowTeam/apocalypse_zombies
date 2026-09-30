#!/usr/bin/env python3
"""M1 加兰德：补上真机的**漏夹卡榫**（clip latch pin）—— 参考现实换弹的第 2 步机构。

真机依据（TACOM/ARDEC 手册 + 常见拆装资料）：
  · 打空后最后一发击发，空漏夹由抛夹弹簧顶出去（"ping"）——这是**自动**的。
  · 但半满的漏夹**不会自己掉出来**：它被卡榫扣住，必须一边把导气杆拉到底并**保持按住**，
    一边用左手按下机匣**左侧**的卡榫销（clip latch pin），夹才脱出。
    手册原话：「Do not relax the rearward pressure on the operating rod handle until after the
    clip has been removed.」
  模型原来的战术换弹是"旧夹自己弹飞"，缺了这一步机构；本脚本把卡榫销补进几何，
  动作由 tools/m1_reload_real.py 写进 reload_tactical。

落点（模型坐标，全部量过周围方块确认无干涉）：
  · 真机卡榫销在左侧 ⇒ 模型里导气杆/折柄在 −X（真机右侧），卡榫必须放 **+X**，与真机左右一致。
  · x 0.32…0.41（机匣下侧壁实测 x=0.32，外凸 0.09u ≈ 5.6mm，真机销子外凸量级一致）
  · y 1.62…1.78（扳机护圈前上方——真机卡榫销就在这个高度；上方 1.788 起是机匣另一块侧壁）
  · z −2.46…−2.26（漏夹井后壁 700mm 之后，不占井口；枪机方块最低 y=1.88，不干涉）
  · 贴图：直接克隆相邻机匣钢面方块的 uv（0.09u 的小件，用同一块钢面即视觉正确）

用法：
  python tools/m1_garand_latch_geo.py --check   # 预演 + 不变量校验，不写盘
  python tools/m1_garand_latch_geo.py           # 写入 art/ 并同步 src/
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art/m1garand"
SRC = ROOT / "src/main/resources/assets/apocalypse_zombies"
GEO_ART, GEO_SRC = ART / "m1_garand.geo.json", SRC / "geo/m1_garand.geo.json"

BONE = "clip_latch"
PARENT = "body"
# pivot = 销子内端面中心（贴着机匣壁）；动作是沿 x 的纯平移，pivot 只影响旋转中心
PIVOT = [0.32, 1.72, -2.36]
CUBE_ORIGIN = [0.32, 1.62, -2.46]
CUBE_SIZE = [0.09, 0.16, 0.20]
UV_FROM = [-0.270, 1.420, -3.040, 0.270, 1.852, 0.352]   # 相邻机匣下侧体（克隆其 uv）
PRESS_DEPTH = 0.06                                        # 按入深度 0.06u = 3.75mm

fails: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


def cube_bbox(c: dict) -> list[float]:
    o, s = c.get("origin", [0, 0, 0]), c.get("size", [0, 0, 0])
    return [o[0], o[1], o[2], o[0] + s[0], o[1] + s[1], o[2] + s[2]]


def overlap(a: list[float], b: list[float], pad: float = 0.005) -> bool:
    return all(a[i] < b[i + 3] - pad and b[i] < a[i + 3] - pad for i in range(3))


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def dump(p: Path, d: dict) -> None:
    """与 tools/m1_well_shift.py 同款：紧凑 JSON（geo 在盘上就是这个格式）。"""
    p.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只预演与校验，不写盘")
    args = ap.parse_args()

    geo = load(GEO_ART)
    bones = geo["minecraft:geometry"][0]["bones"]
    by_name = {b["name"]: b for b in bones}
    already = BONE in by_name

    pin_bbox = [CUBE_ORIGIN[0], CUBE_ORIGIN[1], CUBE_ORIGIN[2],
                CUBE_ORIGIN[0] + CUBE_SIZE[0], CUBE_ORIGIN[1] + CUBE_SIZE[1], CUBE_ORIGIN[2] + CUBE_SIZE[2]]

    # ---- 不变量：落点合法性（无论是否已应用都要过）-------------------------------
    check(pin_bbox[0] > 0, "卡榫销不在 +X 侧（真机在左，而模型导气杆在 −X）")
    check(pin_bbox[2] >= -2.50, f"卡榫销伸进漏夹井口（z {pin_bbox[2]:.3f} < −2.50）")
    for b in bones:
        if b["name"] in ("body", "bolt", "clip_in", "cover", "casing"):
            for c in b.get("cubes", []):
                if bone_cube_conflict(b["name"], c, pin_bbox):
                    fails.append(f"卡榫销与 {b['name']} 的方块干涉：{cube_bbox(c)}")
    # 贴图源方块必须找得到
    src = [c for c in by_name["body"].get("cubes", [])
           if all(abs(cube_bbox(c)[i] - UV_FROM[i]) < 0.01 for i in range(6))]
    check(len(src) == 1, f"找不到唯一的 uv 克隆源（机匣下侧体 {UV_FROM}）")

    if already:
        got = by_name[BONE]
        same = (all(abs(a - b) < 1e-9 for a, b in zip(got["pivot"], PIVOT))
                and len(got.get("cubes", [])) == 1)
        print(f"几何里已有 {BONE}（cubes={len(got.get('cubes', []))}，pivot={got['pivot']}）"
              f"{'，数值一致' if same else '，★数值与脚本不一致'}")
    else:
        print(f"将新增骨骼 {BONE}（parent={PARENT}，pivot={PIVOT}，1 个方块）")

    if fails:
        print("\n不通过：")
        for f in fails:
            print("  ✗", f)
        return 1

    if not already and not args.check:
        pin = {"origin": list(CUBE_ORIGIN), "size": list(CUBE_SIZE), "uv": json.loads(json.dumps(src[0]["uv"]))}
        new_bone = {"name": BONE, "parent": PARENT, "pivot": list(PIVOT), "cubes": [pin]}
        # 插在 body 之后（只在首次应用时插入，位置稳定 => 幂等）
        idx = [i for i, b in enumerate(bones) if b["name"] == PARENT][0]
        bones.insert(idx + 1, new_bone)
        for art, srcp in ((GEO_ART, GEO_SRC),):
            if not art.with_suffix(art.suffix + ".bak").exists():
                shutil.copy2(art, art.with_suffix(art.suffix + ".bak"))
        dump(GEO_ART, geo)
        shutil.copy2(GEO_ART, GEO_SRC)
        print(f"已写入 {GEO_ART.name} 并同步 src/（原件备份 *.bak）")
    elif not already and args.check:
        print("（--check：未写盘）")
    else:
        print("已存在，无改动")

    print(f"\n卡榫销 bbox x {pin_bbox[0]:.3f}…{pin_bbox[3]:.3f} "
          f"y {pin_bbox[1]:.3f}…{pin_bbox[4]:.3f} z {pin_bbox[2]:.3f}…{pin_bbox[5]:.3f}"
          f"   按入深度 {PRESS_DEPTH}u = {PRESS_DEPTH * 62.5:.1f}mm")
    print("全部通过")
    return 0


def bone_cube_conflict(bone: str, c: dict, pin: list[float]) -> bool:
    """枪机在电池位时的干涉检查；枪机方块只可能在它后退路径上碰，故只查电池位。

    例外：body 自己的方块与销子相邻是正常的（销子贴壁），只禁止真穿透。
    """
    return overlap(cube_bbox(c), pin, pad=0.01)


if __name__ == "__main__":
    sys.exit(main())
