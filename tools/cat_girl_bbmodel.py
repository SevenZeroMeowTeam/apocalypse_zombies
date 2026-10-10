"""猫耳娘：spec → 标准 .bbmodel（给 Blockbench 原生打开，视口必定有模型）。

背景：用 MCP 程序化建工程时方块没走 `.init()`，不进 `Cube.all`、不生成 mesh，
视口是空的（"blockbench 里根本没有模型"）。改走这条路：直接写合法 .bbmodel，
Blockbench 自己加载 → 元素/mesh/贴图/UV/动画全由它建。

模板 = 现有 art/cat_girl/cat_girl.bbmodel：只替换 elements / groups / outliner /
贴图元信息，保留 meta、resolution、visible_box、animations 与其他页字段。

用法:
  py tools/cat_girl_bbmodel.py            # 写 art/cat_girl/cat_girl.bbmodel
  py tools/cat_girl_bbmodel.py --check    # 只校验，不写
"""
import argparse
import base64
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "art/cat_girl/cat_girl_spec.json"
BB = ROOT / "art/cat_girl/cat_girl.bbmodel"
TEX = ROOT / "src/main/resources/assets/apocalypse_zombies/textures/entity/cat_girl.png"
NS = uuid.UUID("6f1d4a2e-0f3b-4a55-9d21-1c6b7e5a0d10")  # 稳定 uuid 命名空间


def uid(kind: str, name: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{name}"))


def box_uv(u, v, w, h, d):
    return {
        "north": [u + d, v + d, u + d + w, v + d + h],
        "east": [u, v + d, u + d, v + d + h],
        "south": [u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h],
        "west": [u + d + w, v + d, u + d + w + d, v + d + h],
        "up": [u + d, v, u + d + w, v + d],
        "down": [u + d + w, v, u + d + w + w, v + d],
    }


def build(spec, template):
    elements = []
    el_uuid = {}
    for i, c in enumerate(spec["cubes"]):
        el_uuid[i] = uid("cube", f"{i}:{c['name']}")
    for i, c in enumerate(spec["cubes"]):
        f, s = list(c["from"]), list(c["size"])
        to = [f[i] + s[i] for i in range(3)]
        k = c.get("k", 1.0)
        uv = box_uv(*(c.get("uv") or [0, 0]), *[int(round(v * k)) for v in s])
        if c.get("uvn"):
            x, y, w, h = c["uvn"]
            uv["north"] = [x, y, x + w, y + h]
        el = {
            "name": c["name"], "box_uv": True, "render_order": "default", "locked": False,
            "export": True, "scope": 0, "allow_mirror_modeling": True,
            "from": f, "to": to, "autouv": 0, "color": 9,
            "origin": list(c.get("pivot") or f),
            "faces": {fk: {"uv": [round(x, 4) for x in v], "texture": 0} for fk, v in uv.items()},
            "type": "cube", "uuid": el_uuid[i],
        }
        if c.get("rot"):
            el["rotation"] = list(c["rot"])
        elements.append(el)

    bones = spec["bones"]
    groups = []
    for b in bones:
        groups.append({
            "name": b["name"], "uuid": uid("group", b["name"]), "export": True, "locked": False,
            "scope": 0, "selected": False, "visibility": True,
            "_static": {"properties": {}, "temp_data": {}},
            "origin": list(b["pivot"]), "rotation": [0, 0, 0], "color": 0, "children": [],
            "reset": False, "shade": True, "mirror_uv": False, "autouv": 0,
            "isOpen": False, "primary_selected": False,
        })

    # 骨骼树 → outliner
    kids = {b["name"]: [] for b in bones}
    parents = {b["name"]: b.get("parent") for b in bones}
    for b in bones:
        p = b.get("parent")
        if p in kids:
            kids[p].append(b["name"])
    for i, c in enumerate(spec["cubes"]):
        kids[c["bone"]].append(el_uuid[i])

    def node(name):
        ch = [node(k) if k in kids else k for k in kids[name]]
        return {"uuid": uid("group", name), "isOpen": name == "root", "children": ch}

    roots = [b["name"] for b in bones if b.get("parent") not in kids]
    outliner = [node(r) for r in roots]

    out = dict(template)
    out["name"] = "cat_girl"
    out["model_identifier"] = "cat_girl"
    out["resolution"] = {"width": spec["texture_size"], "height": spec["texture_size"]}
    out["elements"] = elements
    out["groups"] = groups
    out["outliner"] = outliner
    tex = [dict(t) for t in template.get("textures", [{}])][:1] or [{}]
    tex[0].update({
        "name": TEX.name, "path": str(TEX.parent).replace("\\", "/"),
        "width": str(spec["texture_size"]), "height": str(spec["texture_size"]),
        "uv_width": str(spec["texture_size"]), "uv_height": str(spec["texture_size"]),
        "source": "data:image/png;base64," + base64.b64encode(TEX.read_bytes()).decode(),
        "uuid": uid("tex", TEX.name), "saved": "True", "internal": "True",
    })
    out["textures"] = tex
    return out


def validate(bb, spec):
    errs = []
    cube_uuids = {e["uuid"] for e in bb["elements"]}
    group_uuids = {g["uuid"] for g in bb["groups"]}
    seen = []

    def walk(nodes):
        for n in nodes:
            if isinstance(n, str):
                seen.append(n)
            else:
                if n["uuid"] not in group_uuids:
                    errs.append(f"outliner 引用了不存在的组 {n['uuid']}")
                walk(n.get("children") or [])

    walk(bb["outliner"])
    if len(seen) != len(cube_uuids):
        errs.append(f"outliner 里方块 {len(seen)} 个 != elements {len(cube_uuids)} 个")
    miss = cube_uuids - set(seen)
    if miss:
        errs.append(f"{len(miss)} 个方块没挂进 outliner")
    for e in bb["elements"]:
        if e["name"] is None or not e.get("faces"):
            errs.append(f"元素缺 faces: {e.get('name')}")
        if "rotation" in e and e["origin"] is None:
            errs.append(f"{e['name']} 有旋转但没 origin")
    if len(bb["elements"]) != len(spec["cubes"]):
        errs.append(f"元素数 {len(bb['elements'])} != spec 块数 {len(spec['cubes'])}")
    if len(bb["groups"]) != len(spec["bones"]):
        errs.append(f"组数 {len(bb['groups'])} != spec 骨骼数 {len(spec['bones'])}")
    tex = bb["textures"][0]
    if not str(tex.get("source", "")).startswith("data:image/png;base64,"):
        errs.append("贴图 source 不是内嵌 base64")
    if tex.get("uv_width") != str(spec["texture_size"]):
        errs.append(f"贴图 uv 尺寸 {tex.get('uv_width')} != {spec['texture_size']}")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", default=str(BB))
    a = ap.parse_args()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    template = json.loads(Path(a.out).read_text(encoding="utf-8")) if Path(a.out).exists() else {}
    bb = build(spec, template)
    errs = validate(bb, spec)
    print(f"spec: {len(spec['bones'])} 骨骼 / {len(spec['cubes'])} 块  →  bbmodel: "
          f"{len(bb['groups'])} 组 / {len(bb['elements'])} 元素 / 动画 {len(bb.get('animations') or [])} 条")
    if errs:
        print("校验失败:")
        for e in errs:
            print("  ✗", e)
        raise SystemExit(1)
    print("校验通过: outliner 全覆盖 / faces 齐 / 贴图内嵌 / 数量一致")
    if a.check:
        print("(--check 未写盘)")
        return
    Path(a.out).write_text(json.dumps(bb, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写入 {a.out} ({Path(a.out).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
