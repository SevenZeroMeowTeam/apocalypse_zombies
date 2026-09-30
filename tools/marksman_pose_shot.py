#!/usr/bin/env python3
"""把导出动画里的关键帧值直接写进 Blockbench 骨骼再截图 —— 用来目检姿态与旋转方向。
（MCP 驱动不了 Blockbench 的动画播放循环，但把数值写进 Group.rotation 就能看到同一姿态。）"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bbmcp_call as bb  # noqa: E402
import bb_shot  # noqa: E402

ANIM = ROOT / "art/marksman/marksman_skeleton.animation.json"
BUILD = ROOT / "build"
sid = bb.handshake()
doc = json.loads(ANIM.read_text(encoding="utf-8"))


def ev(js):
    raw = bb.text_of(bb.call(sid, "risky_eval", {"code": js}))
    try:
        d = json.loads(raw)
        r = d.get("result", d)
        return json.loads(r) if isinstance(r, str) else r
    except Exception:
        return raw[:300]


def pose(clip: str, t: float, out: str, cam, target):
    a = doc["animations"][clip]
    vals = {}
    for bone, chans in a["bones"].items():
        rot = chans.get("rotation") or {}
        key = f"{t:.3f}".rstrip("0").rstrip(".")
        if key not in rot:
            continue
        v = rot[key]
        v = v["post"] if isinstance(v, dict) else v
        vals[bone] = v
    js = ("(function(){var D=%s;var n=0;Group.all.forEach(function(g){"
          "if(D[g.name]){g.rotation[0]=D[g.name][0];g.rotation[1]=D[g.name][1];g.rotation[2]=D[g.name][2];n++;}"
          "else{g.rotation[0]=0;g.rotation[1]=0;g.rotation[2]=0;}});"
          "if(typeof Canvas!=='undefined'&&Canvas.updateAllBones){Canvas.updateAllBones();}"
          "return {applied:n,names:Object.keys(D)};})()" % json.dumps(vals))
    r = ev(js)
    bb.call(sid, "set_camera_angle", {"view": "main", "projection": "perspective",
                                      "position": list(cam), "target": list(target)})
    p = bb_shot.shot(view="main", out=str(BUILD / out))
    print(f"{clip}@{t}s 应用 {r.get('applied') if isinstance(r, dict) else r} 根 -> {p}")
    return vals


v1 = pose("skill_bone_lock", 1.55, "marksman_pose_skill.png", (-44, 30, -48), (0, 15, 0))
print("  1.55s:", json.dumps(v1, ensure_ascii=False))
pose("skill_bone_lock", 1.70, "marksman_pose_impact.png", (-44, 30, -48), (0, 15, 0))
v3 = pose("walk", 0.25, "marksman_pose_walk.png", (-54, 22, -30), (0, 11, 0))
print("  walk .25s:", json.dumps({k: v3[k] for k in ("leg_r", "leg_l", "shin_r", "arm_r", "arm_l") if k in v3}, ensure_ascii=False))
