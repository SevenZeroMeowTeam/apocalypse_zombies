# v5.0 参考包移植设计（The Shooting Star → 天陨武库）

> 授权范围：用户明确「可以复制上方文件源码」。本文件规定**复制什么、改什么、跳过什么**，
> 以及每一项的风险与回滚路径。参考包已解包到 `F:\mcmod\ref-shooting-star\the-shooting-star-decompiled`
> （只读参考，不进 git）。

---

## 1. 参考包架构（读完 34 个 GLSL + 232 个 java 后的结论）

| 层 | 参考包做法 | 我们的现状 |
|---|---|---|
| 太空场景 | `star_space.fsh` 404 行：**四层嵌套参考系**（地球帧/太阳帧/银河帧/枪），激光贯穿全部 | `orbit_sky.fsh` 单层：星空+银河带+星云+地球 |
| 世界光柱 | `star_beam.fsh` 240 行：屏幕空间**深度重建**（scenePosAt/skyAt/rayCylinderY），锁定镜、雷达扫边、实体红柱、井壁冷却、塌缩深渊 | `OrbitalStrikeHighlighter` 世界空间 quad/line 拼 |
| 后期 | `composite.fsh` 322 行：bloom（soft screen）+ 色差（r²）+ 径向变焦模糊 + 自动曝光 + 去饱和/对比分级 + 暗角 + 烧屏残影 + 胶片颗粒 + **36 种冲击帧** | `orbital.fsh` 单 pass：8 抽样径向模糊 + 4 tap bloom + 色差 + 白闪 |
| bloom | `bloom_down`（13 tap Jimenez）+ `bloom_up`（9 tap tent）+ `depth_copy` 绕开深度格式不匹配 | 4 tap 廉价 bloom |
| HUD | `white_space`：一 quad 一形状，uv 编码尺寸、color 编码形状（plate/shadow/disc/arc/wipe/shard/reticle/rule） | 逐元素 fill |
| 相机 | `CameraMixin` + 12 个 cinematic 类 | 事件相机 + 反射 |
| 共享 | `star.glsl` 177 行：`starField`（三层闪烁星）、`blackbody`、`pointGlow`、`facing`、`toLinear`、`sphereUV` | 无共享 include |

**关键洞察**：参考包的“真实感”= **黑体色温** + **线性空间色调映射** + **实体光柱的体积渐变** + **冲击帧的双色调墨线**。这四样都不依赖 FBO 数量，可以逐个移植。

---

## 2. 移植优先级（本版 = 5.0.0）

### P0 — 天幕升级（零风险，默认开启）
- 目标：`shaders/core/orbit_sky.fsh` 从“贴图级”升到“参考包级”。
- 从 `star.glsl` 复制：`starField`（三层星点 + 闪烁 + 星等分布）、`blackbody`、`pointGlow`。
- 新增：**月球**（程序化环形山，同日照方向）、**银河尘带**（fbm 暗纹 + 亮核）、
  地球加**镜面高光**（海面）+ 冰盖 + 云层涡旋。
- 顺带修一个真 bug：`GameTime` 在 fsh 里声明但 json 没声明、Java 也没 set —— 星空/星云/云
  一直是**静止的**。补上 uniform + Java 赋值，整幅天幕动起来。
- 风险：0（不碰 FBO，只改一个已验证可用的 shader）。

### P1 — 合成器升级（opt-in，带自动回退）
- 目标：`shaders/program/orbital.fsh` 对齐 `composite.fsh`。
- 复制：色差按 r² 缩放、径向变焦模糊（10 tap）、soft-screen bloom、
  去饱和 + 对比分级、暗角、胶片颗粒、白闪。
- 移植 **6 种冲击帧**（从 36 种里挑最有辨识度的）：墨线 / 反相 / 绯红 / 墨线+青饰 /
  半调网点 / 余烬线稿。算法照抄：Sobel 边缘 + **局部自适应阈值**（与周围亮度比较，
  白闪时形状仍成立）+ 旋转网点。
- 自动曝光：参考包用独立的 ExposureSampler；我们直接在 DiffuseSampler 上做 4×4 抽样（等效）。
- 安全网（4.0.3~4.0.6 黑屏的教训）：
  1. 每次 process 后 `glGetError`，非 0 即永久关闭并 warn；
  2. 新增 `/orbitpost on|off` 运行时切换，改配置不用重启；
  3. **默认仍关闭**（`post_shader_experimental=false`），确认不黑再改默认。
- 跳过：烧屏残影（需要 HoldSampler 多一张 FBO，收益/风险不成比例）。

### P2 — 实体光柱（下一轮，最大视觉增益）
- `star_beam.fsh` 的数学（heart/hot/deep/skin 四段渐变、能量条纹 fbm、空气雾、落地冲击环、
  井壁黑体冷却、塌缩深渊）**不用屏幕空间深度重建**，改用世界空间圆柱 quad + 专用
  `ShaderInstance`（`orbit_beam`），径向坐标由 quad UV 给出。绕开 depth_copy 与 FBO 深度问题。
- 这条是我们与参考包差距最大的一处，也是“真实感”的核心。

### P3 — 其余（后续）
- `star_gun`（枪体特写）+ `star_rays`（光轴）→ 世界空间 quad 版。
- `white_space` 的 uv 编码形状 → 我们的 HUD 重写（收益低，最后做）。
- `CameraMixin` → 暂不移植（事件相机已够用，冲突风险高）。

---

## 3. 明确不做

| 项 | 原因 |
|---|---|
| 完整 FBO 链（bloom_down/up ×5 级 + depth_copy） | Embeddium 下黑屏风险；我们用 1 张 swap 的单 pass 近似 |
| `white_space` HUD 引擎 | 重写全部 HUD，收益/工作量不成比例 |
| Mixin 相机 | 与镜头/优化模组冲突，且事件相机已满足 |
| 参考包的贴图/音效/字体/文案 | 只取算法与结构，资产一律自绘 |

---

## 4. 验证

| 阶段 | 命令 / 检查 |
|---|---|
| 构建 | `gradlew build cleanJar --offline` |
| 门禁 | `tools/check_skyfall.py`（新增 orbit_sky 新 uniform、orbital 新 uniform 声明检查） |
| 天幕 | 进 `/apocalypse orbit laser` 抬头看：星星闪烁、银河尘带、月球、地球镜面高光 |
| 合成器 | 主世界打一发 → `/orbitpost on` → 看冲击帧/bloom/色差；若黑屏自动关闭并 warn |
| 回退 | `/orbitpost off` 或 `post_shader_experimental=false` |
| 专服 | `skyfall_probe.py`（世界侧不受影响） |
