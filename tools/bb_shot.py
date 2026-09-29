#!/usr/bin/env python3
"""从 Blockbench 视图抓图并存成 PNG。

用法：python tools/bb_shot.py <view> <out.png> [--cam=x,y,z --target=x,y,z]
  view: active | main | side | ......（见 `bbmcp_call.py call list_views '{}'`）

MCP 的 capture_screenshot 返回 base64 图，这里解码落盘。
不用 JSON 解析：MCP 输出会把长 base64 折行，插进字符串里的换行会让 json.loads 失败，
直接按正则取 base64 再拼回去更稳。相机参数可选，改过就保留，方便固定机位对比改动前后。
"""
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bbmcp_call  # noqa: E402  复用它的 MCP 客户端

_SID = None


def mcp(tool, args=None):
    """直接走 MCP 拿完整结果。

    不能 shell 出 bbmcp_call.py —— 它把结果打到 stdout，图片 base64 会在那儿被截断，
    这里要的是原始 content 块。"""
    global _SID
    if _SID is None:
        _SID = bbmcp_call.handshake()
    return bbmcp_call.call(_SID, tool, args or {})


def shot(view="active", out="build/bb-shot.png", cam=None, target=None, ortho=False,
         locked=None, fov=None):
    if cam or target:
        # projection 必填。正交"侧视图"要靠 locked_angle 锁（只给 position 不动），
        # 所以要真正的侧/顶视就给 --locked；要自由机位就用透视 + 可选 --fov。
        args = {"view": view, "projection": "orthographic" if ortho else "perspective"}
        if locked:
            args["locked_angle"] = locked
        if cam:
            args["position"] = cam
        if target:
            args["target"] = target
        if fov:
            args["fov"] = fov
        mcp("set_camera_angle", args)
    res = mcp("capture_screenshot", {"view": view})
    blocks = (res.get("result") or {}).get("content", []) or []
    raw = next((b["data"] for b in blocks
                if b.get("type") == "image" and b.get("data")), None)
    if raw is None:
        print("没拿到图像：", str(res)[:400])
        return None
    p = Path(out) if Path(out).is_absolute() else ROOT / out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode(raw))
    print(f"{p}  ({p.stat().st_size} bytes)")
    return p


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    view = args[0] if args else "active"
    out = args[1] if len(args) > 1 else f"build/bb-{view}.png"
    cam = target = locked = fov = None
    ortho = "--ortho" in sys.argv
    for a in sys.argv[1:]:
        if a.startswith("--locked="):
            locked = a.split("=", 1)[1]
        if a.startswith("--fov="):
            fov = float(a.split("=", 1)[1])
        if a.startswith("--cam="):
            cam = [float(v) for v in a.split("=", 1)[1].split(",")]
        if a.startswith("--target="):
            target = [float(v) for v in a.split("=", 1)[1].split(",")]
    shot(view, out, cam, target, ortho, locked, fov)
