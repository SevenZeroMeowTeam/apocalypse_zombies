#!/usr/bin/env python3
"""把 Uzi 动画拨到指定 clip/时间点，再从固定侧机位抓图。

⚠️ 实测无效，保留仅作记录：MCP 的 `capture_screenshot` 渲染的是**未变形的静态几何** ——
   8 个不同 clip/时间点抓出来字节完全相同（md5 一致）。要看动画姿态请用
   `tools/uzi_anim_appshot.py`（`capture_app_screenshot` 抓整窗，带实时骨骼变形）。

用法：
    python tools/uzi_anim_shot.py <clip> <time> <out.png> [--cam=.. --target=.. --locked=..]

侧视图用正交投影 + locked="west"（相机在 -X 看向 +X），这样能看到枪管上下俯仰。
注意：Blockbench 视口是**作者空间**，导出器把模型沿 X 镜像过，所以画面左右与游戏相反；
但俯仰（上下）不受镜像影响，判断"枪口该上跳还是下压"依然有效。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bb_shot  # noqa: E402


def pose(clip, t):
    r = bb_shot.mcp("animation_timeline",
                    {"action": "set_time", "time": t, "animation_id": clip})
    print("  set_time %s @%.4fs -> %s" % (clip, t, str(r)[:120]))


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    clip, t, out = a[0], float(a[1]), a[2]
    cam, target, locked = None, None, "west"
    for x in sys.argv[1:]:
        if x.startswith("--cam="):
            cam = [float(v) for v in x.split("=", 1)[1].split(",")]
        if x.startswith("--target="):
            target = [float(v) for v in x.split("=", 1)[1].split(",")]
        if x.startswith("--locked="):
            locked = x.split("=", 1)[1]
    pose(clip, t)
    bb_shot.shot("active", out, cam=cam, target=target, ortho=True, locked=locked)


if __name__ == "__main__":
    main()
