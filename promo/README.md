# Apocalypse Zombies 宣传片（LibTV 生成）

画布：LibTV「Apocalypse Zombies 宣传片 v1」（uuid `a8af46603b2a4d4fb478a107e62db4df`，工作区「末日僵尸·宣传片」/ 12870622）
本目录 `.libtv/run/` 保存了全部节点操作日志与任务结果 JSON。

## 分镜脚本（8 镜，约 33 秒）

| # | 节点名 | 关键帧 | 动态内容 | 状态 |
|---|--------|--------|----------|------|
| 1 | 分镜01·血月之城 | ✅ | 推镜穿雾，血月脉动 | ✅ 成片 720P 5s 含声 |
| 2 | 分镜02·僵尸围城 | ✅ | 僵尸群向镜头逼近 | ⛔ 算力不足 |
| 3 | 分镜03·狙击时刻 | ✅ | 屋顶持枪瞄准、环绕 | ⛔ 算力不足 |
| 4 | 分镜04·致命一击 | ✅ | 开枪、弹壳、僵尸倒地 | ⛔ 算力不足 |
| 5 | 分镜05·天火陨落 | ✅（+参考·小行星） | 小行星坠落 | ⛔ 算力不足 |
| 6 | 分镜06·轨道天罚 | ✅（+参考·天基炮） | 光柱轰击、冲击波环 | ⛔ 算力不足 |
| 7 | 分镜07·焚城余烬 | ✅ | 火风暴、熔岩、剪影 | ⛔ 算力不足 |
| 8 | 分镜08·片尾字卡 | ✅ 中文标题渲染正确 | 缓慢推近字卡 | ✅ 成片 480P 3s 无声 |

## 充值后续跑（在仓库根目录执行）

```bash
LIBTV="C:\Users\Administrator\.libtv\libtv.exe"
# 1) 把 6 个待跑节点升回 720P / 5 秒 / 含声（成片08 可选升 3s/720P）
for n in "成片02·僵尸围城" "成片03·狙击时刻" "成片04·致命一击" "成片05·天火陨落" "成片06·轨道天罚" "成片07·焚城余烬"; do
  "$LIBTV" node "$n" -s duration=5 -s resolution=720P -s enableSound=on
done
# 2) 串行触发（服务端限制同时只能跑 1 个任务，别并行）
for n in "成片02·僵尸围城" "成片03·狙击时刻" "成片04·致命一击" "成片05·天火陨落" "成片06·轨道天罚" "成片07·焚城余烬"; do
  "$LIBTV" node "$n" --run
done
# 3) 可选：对每段做高清超分
"$LIBTV" video hd list && "$LIBTV" video hd -n "成片01·血月之城"
# 4) 下载（非会员必须 --watermark true，成片带社区水印；会员传 false 无水印）
"$LIBTV" download -n "成片02·僵尸围城" --watermark true -o promo/video
```

## 说明

- 模型：关键帧 Seedream 4.5（字卡 Seedream 4.0），视频 Wan 3.0 `mixed2video`（图生视频）。
- 帐号为非会员；并发任务数上限 1，所有生成必须串行。
- 成片片段需在剪辑软件中按 01→08 顺序拼接；字卡建议停留 2-3 秒。
- `../.libtv/project.json` 是画布目录绑定（含画布 uuid），勿删；`run/` 是任务日志。

## ComfyUI 本地生成管线（2026-10-25 新增）

模型：MiniMax H3（Comfy-Org/MiniMax-H3，hf-mirror 并发下载 56GB）+ 社区 Cobijada w4a8 混合量化 12.5GB，
已装入 `F:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\`，便携包经 extra_model_paths.yaml 共享。

工具链（本目录）：
- `download_models.py`：hf-mirror 分块并发下载器（64MB 块 + .state.json 断点续传）
- `gen_clip.py`：分镜批量图生视频（turbo 8 步 LoRA + VAEDecodeTiled 分块解码）
- `supervise_scene.py`：监督器（服务挂掉自动重启、容错轮询、自动重提）
- `stitch.py`：8 段成片统一 1280x720@30fps 拼接（字卡段补静音）

运行环境：便携包 + DirectML（`--directml --cpu-vae --fp32-vae --force-fp16 --lowvram
--disable-async-offload --cache-none --use-split-cross-attention`），已打 5 处补丁
（详见记忆 comfyui-amd-setup.md）。

**当前卡点**：服务进程在任务 ~28 分钟处被外部静默终止（无任何日志/事件痕迹，嫌疑 360/Process Lasso）。
把 `python.exe` 与 `F:\ComfyUI_windows_portable_amd` 加入防护白名单后执行：

```bash
python promo/supervise_scene.py --scene 02 --rounds 3   # 自愈续跑，成功后换 03..07
python promo/stitch.py                                   # 全部完成后拼接
```

备选：更新 AMD 显卡驱动后走 ROCm 路线；或回 LibTV 充值续跑 6 个分镜（命令见上节）。
