#!/usr/bin/env python3
"""整窗截图：拿到带实时骨骼变形的 3D 视口。

MCP 的 capture_screenshot 渲染的是未变形的静态几何（8 个 clip 抓出来一模一样），
要看到动画姿态必须抓整个 Blockbench 窗口。
"""
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bb_shot  # noqa: E402


def app_shot(out):
    res = bb_shot.mcp("capture_app_screenshot", {})
    blocks = (res.get("result") or {}).get("content", []) or []
    raw = next((b["data"] for b in blocks if b.get("type") == "image" and b.get("data")), None)
    if raw is None:
        print("没拿到图像：", str(res)[:400])
        return None
    p = Path(out) if Path(out).is_absolute() else ROOT / out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode(raw))
    print("%s  (%d bytes)" % (p, p.stat().st_size))
    return p


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    clip, t, out = a[0], float(a[1]), a[2]
    bb_shot.mcp("animation_timeline", {"action": "set_time", "time": t, "animation_id": clip})
    app_shot(out)
    print("  已转到 %s @%.4fs" % (clip, t))


if __name__ == "__main__":
    main()
