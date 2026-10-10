"""cat_girl v4 spec → 装机 geo.json

为什么要逐面 UV（uv/uv_size）：v4 的贴图是「分件密度装箱」(每块 k 不同) + 脸层
用一个 28x20 专用矩形。盒式 UV 只能给一个 [u,v] 起点、面大小由方块尺寸决定，
表达不了 k 也表达不了专用矩形 —— 所以导出必须用逐面形式（MC 1.12 也支持）。

用法：
    py tools/cat_girl_geo.py            # 写装机 geo（自动 .bak）
    py tools/cat_girl_geo.py --check    # 只校验不写
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cat_girl_bbmodel import box_uv  # noqa: E402

ROOT = Path(r"F:/mcmod")
SPEC = ROOT / "art/cat_girl/cat_girl_spec.json"
OUT = ROOT / "src/main/resources/assets/apocalypse_zombies/geo/cat_girl.geo.json"


def build(spec):
    ts = spec["texture_size"]
    if isinstance(ts, (list, tuple)):
        ts = ts[0]
    by_bone = {}
    for c in spec["cubes"]:
        by_bone.setdefault(c["bone"], []).append(c)
    bones = []
    for b in spec["bones"]:
        e = {"name": b["name"]}
        if b.get("parent"):
            e["parent"] = b["parent"]
        e["pivot"] = [round(v, 4) for v in b["pivot"]]
        cubes = []
        for c in by_bone.get(b["name"], []):
            k = c.get("k", 1.0)
            px = [int(round(v * k)) for v in c["size"]]
            rects = box_uv(*(c.get("uv") or [0, 0]), *px)
            if c.get("uvn"):
                x, y, w, h = c["uvn"]
                rects = dict(rects)
                rects["north"] = [x, y, x + w, y + h]
            cu = {
                "origin": [round(v, 4) for v in c["from"]],
                "size": [round(v, 4) for v in c["size"]],
                "uv": {f: {"uv": [r[0], r[1]], "uv_size": [r[2] - r[0], r[3] - r[1]]}
                       for f, r in rects.items()},
            }
            if c.get("rot"):
                cu["rotation"] = [round(v, 4) for v in c["rot"]]
                cu["pivot"] = [round(v, 4) for v in (c["pivot"] or [0, 0, 0])]
            cubes.append(cu)
        if cubes:
            e["cubes"] = cubes
        bones.append(e)
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": "geometry.cat_girl",
                "texture_width": ts, "texture_height": ts,
                "visible_bounds_width": 3,
                "visible_bounds_height": 3.5,
                "visible_bounds_offset": [0, 1.25, 0],
            },
            "bones": bones,
        }],
    }


def main():
    check = "--check" in sys.argv
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    ts = spec["texture_size"]
    ts = ts[0] if isinstance(ts, (list, tuple)) else ts
    geo = build(spec)
    bones = geo["minecraft:geometry"][0]["bones"]
    ncubes = sum(len(b.get("cubes", [])) for b in bones)
    # 不变量：块数/骨骼数一致、UV 不越 128、旋转块都带 pivot
    assert ncubes == len(spec["cubes"]), f"块数不符 {ncubes} != {len(spec['cubes'])}"
    assert len(bones) == len(spec["bones"]), "骨骼数不符"
    bad = []
    for b in bones:
        for c in b.get("cubes", []):
            for f, d in c["uv"].items():
                u, v = d["uv"]
                w, h = d["uv_size"]
                if u < 0 or v < 0 or u + w > ts or v + h > ts:
                    bad.append((b["name"], f, d))
            if "rotation" in c and "pivot" not in c:
                bad.append((b["name"], "旋转缺 pivot", c))
    assert not bad, f"越界/缺 pivot: {bad[:4]}"
    print(f"geo: {len(bones)} 骨骼 / {ncubes} 块，UV 全部在 {ts}x{ts} 内")
    if check:
        print("--check 通过（未写入）")
        return
    if OUT.exists():
        shutil.copy2(OUT, OUT.with_suffix(".json.bak"))
    OUT.write_text(json.dumps(geo, ensure_ascii=False), encoding="utf-8")
    print(f"已写 {OUT.relative_to(ROOT)}（旧版备份 cat_girl.geo.json.bak）")


if __name__ == "__main__":
    main()
