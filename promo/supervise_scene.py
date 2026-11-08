# -*- coding: utf-8 -*-
"""场景监督器：服务挂了自动重启，轮询容错，最多 N 轮。

用法: python supervise_scene.py --scene 02 --unet <file> --clip <file> --rounds 3
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, r"C:\Users\Administrator\.zcode\cli\plugins\cache\zcode-comfyui-bridge\comfyui-bridge\0.1.0\scripts")
import comfy_bridge as cb  # noqa: E402
import gen_clip as gc  # noqa: E402

URL = gc.URL
SERVER_DIR = Path(r"F:\ComfyUI_windows_portable_amd\ComfyUI_windows_portable")
SERVER_CMD = [str(SERVER_DIR / "python_embeded" / "python.exe"), "-s", "ComfyUI/main.py",
              "--directml", "--cpu-vae", "--fp32-vae", "--force-fp16", "--lowvram",
              "--disable-async-offload", "--cache-none", "--use-split-cross-attention",
              "--disable-mmap", "--port", "8188"]
LOG = SERVER_DIR / "comfy-dml.log"


def server_up(timeout=8):
    try:
        with urllib.request.urlopen(f"{URL}/system_stats", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def start_server(wait=240):
    if server_up():
        return True
    print(f"[{time.strftime('%H:%M:%S')}] 启动 ComfyUI 服务…", flush=True)
    subprocess.Popen(SERVER_CMD, cwd=str(SERVER_DIR),
                     stdout=open(LOG, "a"), stderr=subprocess.STDOUT,
                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(10)
        if server_up():
            print(f"[{time.strftime('%H:%M:%S')}] 服务在线", flush=True)
            return True
    return False


def robust_poll(pid, timeout_per_scene):
    """容错轮询：单次请求失败不退出，指数退避重试。"""
    deadline = time.time() + timeout_per_scene
    fails = 0
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/history/{pid}", timeout=60) as r:
                entry = json.load(r).get(pid)
            fails = 0
            if entry:
                st = entry.get("status") or {}
                if st.get("status_str") == "error":
                    for m in st.get("messages") or []:
                        if m[0] == "execution_error":
                            d = m[1]
                            print(f"  [error] 节点 {d.get('node_id')} ({d.get('node_type')}): "
                                  f"{str(d.get('exception_message'))[:160]}", flush=True)
                    return entry, "error"
                if st.get("completed") and st.get("status_str") == "success":
                    return entry, "success"
        except Exception as e:
            fails += 1
            if fails % 5 == 0:
                print(f"  [poll] 连续 {fails} 次请求失败: {type(e).__name__}", flush=True)
            if fails >= 40:  # ~7 分钟无响应视为服务死亡
                return None, "dead"
        time.sleep(10)
    return None, "timeout"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--clip", default="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors")
    ap.add_argument("--unet", default="Cobijada_H3_Hybrid_Uncensored_pruned_hybrid_w4a8_convrot_pruned.safetensors")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--width", type=int, default=864)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--duration", type=float, default=5)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--out", default="video")
    args = ap.parse_args()

    for attempt in range(1, args.rounds + 1):
        print(f"===== 第 {attempt}/{args.rounds} 轮 =====", flush=True)
        if not start_server():
            print("[fatal] 服务起不来", flush=True)
            sys.exit(2)
        try:
            wf = gc.build_graph(args.scene, args)
            pid = gc.submit(wf)
            print(f"[{time.strftime('%H:%M:%S')}] 已入队 {pid}", flush=True)
        except urllib.error.HTTPError as e:
            print("[fatal] 提交被拒:", e.read().decode("utf-8", "replace")[:600], flush=True)
            sys.exit(3)
        entry, status = robust_poll(pid, 90 * 60)
        if status == "success":
            files = cb.download_outputs(URL, entry, gc.ROOT / args.out)
            print(f"[{time.strftime('%H:%M:%S')}] 分镜{args.scene} 完成", flush=True)
            for f in files:
                print("  ->", f["path"], flush=True)
            sys.exit(0)
        if status == "error":
            print("[round] 执行错误，换参数前先停止", flush=True)
            sys.exit(4)
        print(f"[{time.strftime('%H:%M:%S')}] 本轮失败: {status}，30 秒后下一轮", flush=True)
        time.sleep(30)
    sys.exit(5)


if __name__ == "__main__":
    main()
