# 《天陨武库》v5 设计：高保真轨道舞台

> 触发背景：玩家在世界里“找不到卫星/天基炮等打击设施”——因为它们目前**不是世界结构**，
> 只是打击演出里的程序化 3D 舞台。玩家同时授权使用参考包的
> **自定义 GLSL / FBO 后期 / Mixin 相机 / 多线程世界编辑** 四类技术。
> 本文件定义 v5 的边界、分层与里程碑；不复制参考包的代码、类名、贴图、音效。

---

## 0. 先把“设施”说清楚

| 层 | 现在有什么 | 玩家能不能“找到” |
|---|---|---|
| 地面终端 | 方块 + GUI（六协议、充能、范围） | 能，合成/放置即可 |
| 太空载体 | `OrbitalSpaceStage` 的 3D 程序化舰体/卫星/陨石，只在打击镜头里出现 | **只能在打击/预览镜头里看到** |
| 世界结构 | 无 | 找不到 |
| 后处理 | 4.0.3 起的单 pass（径向模糊/色差/bloom/白闪/调色） | 只在演出期间出现，且 4.0.3 黑屏过 |

**因此本版做两件事**：
1. 给玩家一个**随时能看设施**的入口（`/orbitpreview`，4.0.5 先上）；
2. 用四类技术把“演出层”做到接近参考包，而不是把设施塞进世界当建筑。

如果最终要“能走进去的轨道设施”，那是 v5-P5 的独立维度/结构工程，见 §4。

---

## 1. 四根技术支柱（允许使用）

### 1.1 自定义 GLSL（目标 8~12 个程序，不是硬凑 34 个）

参考包的 34 个 GLSL 里，真正决定观感的是：星空/星云、地球与大气、太阳/镜头光晕、
泛光、色差、径向模糊、曝光、冲击帧。我们按“每个程序一个可验证职责”落地：

| 程序 | 职责 | 接入方式 |
|---|---|---|
| `orbit_sky` | 星空 + 银河带 + 星云 FBM（全屏/天空盒） | 自定义 `RenderType` + 相机朝向四边形 |
| `orbit_earth` | 球面地球：大陆/云/夜面灯光/晨昏线/大气 | 世界空间球体 quad 或 raymarch 全屏 |
| `orbit_atmo` | 大气散射边缘（叠加在球体外） | 叠加 quad |
| `orbit_beam` | 光柱/矛体的体积感（多层噪声） | 世界空间 billboard |
| `orbit_bloom` | 亮度提取 + 两级模糊 | FBO 多 pass |
| `orbit_composite` | bloom + 色差 + 曝光 + 暗角 + 调色 | FBO 最终 pass |
| `orbit_impact` | 冲击帧（反相/墨迹/扫描线，可配置样式） | GUI 或 FBO |
| `orbit_grade` | 电影 LUT 近似（曲线/分离调色） | 可并入 composite |

**约束**：每个程序必须有 `try/catch` 回退；资源包缺文件时退回现有贴图舞台；
不引入需要 OpenGL 4.x 的特性（保持 3.3/GLSL 150 可编译）。

### 1.2 FBO 后期管线（多 pass，而不是现在的单 pass）

```
main ──bright──> half ──blurH──> half2 ──blurV──> bloom
main + bloom ──composite(CA/exposure/vignette/grade)──> swap ──blit──> main
```

- 用 `PostChain` JSON 声明 targets（`half`, `half2`, `bloom`）+ `PostChain.addPass(...)`
  拿 `PostPass` 引用来每帧写自定义 uniform（`PostChain` 不暴露 pass 列表，但 `addPass` 返回它）。
- 低画质：`post_quality=0` 只跑 composite（无 bloom）；`post_shader=false` 全关。
- **黑屏防线**：pass 前后显式 `disableCull/disableDepthTest`、`bindWrite(main)`、
  首帧 `glReadPixels` 黑帧检测（连续 2 帧全黑即自动关闭并记日志）。
- 只在打击/预览期间运行；无演出时零开销。

### 1.3 Mixin 相机（替换反射/事件拼装）

- 目标：`GameRenderer`/`Camera` 的 `setup`/`turn`/`pick` 关键点，提供：
  - 精确的相机位置/朝向/滚转/FOV（含过场冻结、输入屏蔽、手部隐藏）；
  - 与 `OrbitalCinematic` 的时间轴统一，不再靠 `ComputeCameraAngles` 反射补丁；
  - 旁观者/施放者/预览三种模式共用同一套相机状态机。
- 兼容：Mixin 只 `@Inject` 必要方法，不覆盖 `@Overwrite`；Embeddium/Oculus 下做
  `@Pseudo`/`require=0` 的软兼容；失败时回退现有事件相机。
- 风险：相机 Mixin 与其它镜头模组冲突概率高，必须提供 `mixin_camera=false` 开关。

### 1.4 多线程世界编辑引擎

- 现有 `DestroyJob` 在主线程按 4000 格/tick 预算推进；v5 改成：
  - **准备线程**：按 chunk/section 快照方块状态、计算要挖/要换的坐标与掉落，产出不可变变更包；
  - **主线程应用**：每 tick 限量 `setBlock`/`setBlockEntity`，检查区块已加载/保护/世界边界；
  - **区块票据**：只为已加载/已申请 ticket 的区块排队，禁止无界加载；
  - **取消/关服**：队列可丢弃，已应用部分不回滚（记录日志），保证不重复掉落/伤害。
- 上限：`threads`（默认 2）、`apply_per_tick`、`max_pending_chunks`、`protect` 全部配置化。
- 验收：1000 格半径的压力测试不崩、不一次性卡死；取消后无残留任务。

---

## 2. 里程碑

| 阶段 | 内容 | 验收 |
|---|---|---|
| **P0（4.0.5，本版）** | `/orbitpreview <mode>`：本地预览六种载体，不发包/不伤方块；修复后处理黑屏回归 | 命令能看全六种载体的太空段；无服务端副作用 |
| P1 | `orbit_sky` + `orbit_earth` + `orbit_atmo`：shader 太空背景替换贴图舞台 | 地球/星云/晨昏线接近参考包；关 shader 回退旧舞台 |
| P2 | FBO 多 pass：bloom + composite + 冲击帧 + 黑帧自检 | 命中 bloom/色差/曝光明显；黑帧自动回退；低画质可关 |
| P3 | Mixin 相机 | 过场相机不再靠反射；预览/旁观/施放共用；冲突可关 |
| P4 | 多线程世界编辑 | 大范围挖掘不卡主线程；取消干净；保护/边界测试通过 |
| P5（可选） | 轨道设施维度/结构：六个平台可传送参观 | 终端可进入/退出；结构原创建造；无破坏性副作用 |

---

## 3. 与现有实现的关系

- 保留：`StrikeProtocol` 相位机、服务端权威、预算 Job、终端 GUI、六协议玩法。
- 替换：`OrbitalSpaceStage` 的贴图 backdrop → shader 背景（P1）；
  单 pass 后处理 → 多 pass FBO（P2）；事件相机 → Mixin（P3，可回退）。
- 新增：`/orbitpreview`（P0 已完成）；轨道设施维度（P5，需单独确认）。

---

## 4. 需要拍板

1. **设施形态**：(a) 只在演出/预览镜头里看（推荐，和参考包一致）；(b) 真的做一个可传送的轨道维度。
2. **Mixin**：接受与镜头/优化模组冲突的风险吗？（提供开关，默认开）
3. **FBO 黑屏**：如果多 pass 在 Embeddium 下仍不稳，是否接受默认关闭 bloom、只留 composite？

---

## 5. 验证清单（每阶段）

- 构建：`gradlew build cleanJar --offline`
- 门禁：`tools/check_skyfall.py`（新增 shader/FBO 资源清单）
- 单人：六个模式各打一发 + `/orbitpreview` 各看一遍
- 专服：`skyfall_probe.py` 四步；无客户端 shader 时服务端不受影响
- 回退：`post_shader=false`、`mixin_camera=false`、`post_quality=0` 三条路径
