# -*- coding: utf-8 -*-
"""宣传片分镜批量图生视频驱动：复用 comfy_bridge 构图 → 串行提交 → 轮询 → 下载。

用法:
  python gen_clip.py --scene 02            # 单镜
  python gen_clip.py --scene all           # 全部待跑镜
可选: --width 864 --height 480 --steps 8 --duration 5 --out video
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, r"C:\Users\Administrator\.zcode\cli\plugins\cache\zcode-comfyui-bridge\comfyui-bridge\0.1.0\scripts")
import comfy_bridge as cb  # noqa: E402

BRIDGE = Path(r"C:\Users\Administrator\.zcode\cli\plugins\cache\zcode-comfyui-bridge\comfyui-bridge\0.1.0")
TEMPLATE = BRIDGE / "workflows" / "minimax_h3_i2v.json"
ROOT = Path(r"F:\mcmod\apocalypse_zombies-main\promo")
URL = "http://127.0.0.1:8188"

# 服务器上已上传的关键帧(load_image_value)与分镜运动提示词
SCENES = {
    "02": {
        "image": "107e8370f40b.png",
        "prompt": "末日城市废墟，成群僵尸拖着残躯缓缓向镜头逼近，脚步拖沓，肢体僵硬扭曲，"
                  "尘土在暗红色天光中飘动，压迫感十足，镜头缓慢推进。低沉紧张的配乐，丧尸低吼声与风声。",
    },
    "03": {
        "image": "348ad4d19d45.png",
        "prompt": "屋顶上全副武装的狙击手持枪警惕，镜头围绕他缓慢环绕移动，风吹动他的衣物与披风，"
                  "远处末日城市废墟在昏黄天光下延伸，气氛紧张肃杀。风声与低沉的氛围音乐。",
    },
    "04": {
        "image": "d89a23d328a2.png",
        "prompt": "狙击手扣动扳机，枪口火光一闪，弹壳弹出旋转坠落，枪身轻微后坐震动，"
                  "远处一只丧尸中弹倒地扬起尘土。清脆枪声与弹壳落地声，低频冲击音效。",
    },
    "05": {
        "image": "9a2be3f79b15.png",
        "prompt": "燃烧的小行星拖着炽热火尾划破夜空坠落城市上空，火光渐强映亮云层与废墟街道，"
                  "镜头缓缓上摇追随陨石轨迹，震撼末日氛围。轰鸣声由远及近渐强，配乐恢弘紧张。",
    },
    "06": {
        "image": "1c4b4d7a344c.png",
        "prompt": "天基武器光柱从高空垂直轰击城市，白色光柱刺穿云层，冲击波环向四周扩散掀飞尘土，"
                  "白光过曝后显露出焦土与火光。强烈低频轰鸣与能量嗡鸣声，末日审判般的恢弘配乐。",
    },
    "07": {
        "image": "a30ac2734d72.png",
        "prompt": "火风暴在末日城市废墟中翻卷升腾，熔岩沿街道流淌，一个人物剪影伫立高处望向火海，"
                  "火星与灰烬随热浪飘散，镜头缓慢拉远。火焰咆哮声、余烬噼啪声与悲怆的配乐。",
    },
}

TURBO_LORA = "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"


def build_graph(scene, args):
    s = SCENES[scene]
    wf, meta = cb.load_workflow(str(TEMPLATE))
    params = {
        "image": s["image"],
        "prompt": s["prompt"],
        "width": args.width,
        "height": args.height,
        "duration": args.duration,
        "filename_prefix": f"promo/fenjing{scene}",
    }
    wf = cb.apply_params(wf, meta, params)
    add = json.dumps({"803": {"class_type": "LoraLoader", "inputs": {
        "lora_name": TURBO_LORA, "strength_model": 1.0, "strength_clip": 1.0,
        "model": ["6", 0], "clip": ["13", 0]}}})
    wf = cb.mutate(wf, [f"9.inputs.steps={args.steps}"] + (
        [f"13.inputs.clip_name={args.clip}"] if args.clip else []),
                   ['9.inputs.model=["803",0]', '16.inputs.model=["803",0]'],
                   json.loads(add))
    wf.pop("_meta", None)
    return wf


def submit(wf):
    payload = {"prompt": wf, "client_id": "promo-batch"}
    req = urllib.request.Request(f"{URL}/prompt", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["prompt_id"]
    except urllib.error.HTTPError as e:
        print(e.read().decode("utf-8", "replace")[:2000], file=sys.stderr)
        raise


def wait_job(pid, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(10)
        with urllib.request.urlopen(f"{URL}/history/{pid}", timeout=30) as r:
            entry = json.load(r).get(pid)
        if not entry:
            continue
        st = entry.get("status") or {}
        if st.get("status_str") == "error":
            for m in st.get("messages") or []:
                if m[0] == "execution_error":
                    d = m[1]
                    print(f"  [error] 节点 {d.get('node_id')} ({d.get('node_type')}): "
                          f"{d.get('exception_message')}", file=sys.stderr)
            raise RuntimeError("执行失败")
        if st.get("completed") and st.get("status_str") == "success":
            return entry
    raise TimeoutError(f"等待超时 {timeout}s")


def run_scene(scene, args):
    t0 = time.time()
    wf = build_graph(scene, args)
    pid = submit(wf)
    print(f"[{time.strftime('%H:%M:%S')}] 分镜{scene} 已入队 prompt_id={pid}")
    entry = wait_job(pid, args.wait)
    files = cb.download_outputs(URL, entry, ROOT / args.out)
    print(f"[{time.strftime('%H:%M:%S')}] 分镜{scene} 完成，用时 {(time.time()-t0)/60:.1f} 分钟")
    for f in files:
        print("  ->", f["path"])
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, help="02/03/04/05/06/07 或 all")
    ap.add_argument("--width", type=int, default=864)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--clip", default=None, help="覆盖文本编码器文件名")
    ap.add_argument("--duration", type=float, default=5)
    ap.add_argument("--out", default="video")
    ap.add_argument("--wait", type=int, default=5400)
    args = ap.parse_args()

    scenes = list(SCENES) if args.scene == "all" else [args.scene]
    for s in scenes:
        out = run_scene(s, args)
        if not out:
            print(f"[warn] 分镜{s} 无输出文件", file=sys.stderr)
    print("[ALL DONE]")


if __name__ == "__main__":
    main()
