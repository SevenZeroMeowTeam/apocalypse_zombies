# -*- coding: utf-8 -*-
"""MiniMax H3 模型并发下载器：分块(64MB) + 线程池 + 断点续传(按块跳过) + 顺序拼接。

用法: python download_models.py [--workers 16] [--repo base_url] [--dest models_root]
"""
import argparse
import json
import os
import shutil
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

FILES = [
    # (repo 相对路径, 目标子目录)
    ("diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors", "diffusion_models"),
    ("text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors", "text_encoders"),
    ("vae/minimax_h3_video_vae_fp16.safetensors", "vae"),
    ("vae/minimax_h3_audio_vae_fp32.safetensors", "vae"),
    ("loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", "loras"),
]

CHUNK = 64 * 1024 * 1024
lock = threading.Lock()
done_bytes = 0
total_bytes = 0
t0 = time.time()


def fetch_chunk(url, start, end, path, tries=6):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if len(data) != end - start + 1:
                raise IOError(f"short read {len(data)} != {end-start+1}")
            with open(path, "r+b") as f:
                f.seek(start)
                f.write(data)
            return len(data)
        except Exception as e:
            wait = 2 * (attempt + 1)
            print(f"[retry {attempt+1}] {os.path.basename(path)} {start}-{end}: {e} ({wait}s)", flush=True)
            time.sleep(wait)
    raise IOError(f"chunk {start}-{end} failed after {tries} tries")


def download_file(repo, rel, dest_dir, workers=16):
    global done_bytes, total_bytes
    url = f"{repo}/resolve/main/{rel}"
    dest = os.path.join(dest_dir, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".downloading"

    # 已有成品则跳过
    if os.path.exists(dest):
        print(f"[skip] {rel} 已存在", flush=True)
        return
    # 探测大小
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as r:
        size = int(r.headers.get("Content-Length", 0))
    if size <= 0:
        raise IOError(f"HEAD failed for {url}")
    # 预分配
    if not os.path.exists(tmp) or os.path.getsize(tmp) != size:
        with open(tmp, "wb") as f:
            f.truncate(size)

    chunks = [(s, min(s + CHUNK, size) - 1) for s in range(0, size, CHUNK)]
    with lock:
        total_bytes += size

    # 断点续传：.state.json 记录已完成块索引
    state_path = tmp + ".state.json"
    state = {"chunks": []}
    if os.path.exists(state_path):
        try:
            state = json.load(open(state_path))
        except Exception:
            state = {"chunks": []}
    done_set = set(state.get("chunks", []))
    todo = [c for i, c in enumerate(chunks) if i not in done_set]
    print(f"[resume] {rel}: {len(done_set)}/{len(chunks)} 块已完成", flush=True)

    def work(item):
        global done_bytes
        i, c = item
        s, e = c
        try:
            got = fetch_chunk(url, s, e, tmp)
        except Exception as ex_:
            print(f"[fail] {rel} 块{i}: {ex_}", flush=True)
            return i
        with lock:
            done_set.add(i)
            json.dump({"chunks": sorted(done_set)}, open(state_path, "w"))
            done_bytes += got
            el = time.time() - t0
            print(f"[{el:6.0f}s] {done_bytes/1e9:6.2f}/{total_bytes/1e9:.2f}GB "
                  f"({done_bytes/el/1e6:.1f}MB/s) {rel} {len(done_set)}/{len(chunks)}", flush=True)
        return None

    pending = list(enumerate(todo))
    for round_ in range(5):
        if not pending:
            break
        print(f"[round {round_+1}] 待下载 {len(pending)} 块", flush=True)
        with ThreadPoolExecutor(workers) as ex:
            results = list(ex.map(work, pending))
        pending = [p for p, r in zip(pending, results) if r is not None]
        if pending:
            print(f"[warn] {len(pending)} 块失败，30s 后重试下一轮", flush=True)
            time.sleep(30)
    if pending:
        raise IOError(f"{rel}: {len(pending)} 块最终失败")

    os.remove(state_path)
    os.replace(tmp, dest)
    print(f"[done] {rel} -> {dest}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="https://hf-mirror.com/Comfy-Org/MiniMax-H3")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    for rel, sub in FILES:
        download_file(args.repo, rel, args.dest, args.workers)
    print("[ALL DONE]", flush=True)


if __name__ == "__main__":
    main()
