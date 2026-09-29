# 参考物：TaCZ 精密国际 AWM (`ai_awp`)

AWM 动画不是凭空编的，是**逐帧对着 TaCZ 官方枪包抄下来的**。这份文档记录抄了什么、
怎么换算、哪里做了偏离，方便以后加枪时复用同一套流程。

## 数据来源

```
<游戏实例>/.minecraft/versions/<ver>/tacz/tacz_default_gun/assets/tacz/
  ├── geo_models/gun/ai_awp_geo.json
  ├── animations/ai_awp.animation.json     <- 动画真值
  └── textures/gun/ai_awp.png
```

注意：TaCZ 里这把枪叫 **精密国际AWM**，gun id 是 `ai_awp`。**没有叫 AWP 的枪**，
网上说的 "AWP" 指的是同一支枪的俗称，不要在 TaCZ 里搜 `awp`。

转录脚本：`tools/tacz_anim_transcribe.py`（读上面那份 JSON，按下面的换算规则写出
`art/awm/awm.animation.json`，再同步到 `src/main/resources/assets/apocalypse_zombies/animations/`）。
关键常量在脚本开头：`S_GUN = 57.07 / 23.97`。

TaCZ 的动画键（`ai_awp.animation.json` 的 `animations`）与我们现在的对应关系：

| TaCZ 键 | 长度 | 我们的对应 clip | 状态 |
|---|---|---|---|
| `static_idle` | 2.0 s（循环） | `static_idle` | 已抄、已接线 |
| `static_bolt_caught` | 2.0 s（循环） | `static_bolt_caught` | 已抄，未接线 |
| `shoot` | 0.85 s | `shoot` | 已抄、已接线 |
| `bolt` | 1.2667 s | `bolt` | 已抄、已接线 |
| `draw` | 1.0 s | `draw` | 已抄，未接线 |
| `put_away` | 0.75 s | `put_away` | 已抄，未接线 |
| `reload_tactical` | 3.0 s | `reload_tactical` | 已抄、已接线 |
| `reload_empty` | 3.7167 s | `reload_empty` | 已抄、已接线 |
| `inspect` | 12.7833 s | `inspect` | 已抄，未接线 |
| `inspect_empty` | 10.25 s | `inspect_empty` | 已抄，未接线 |

## 换算规则

| 量 | 换算 |
|---|---|
| 旋转角度 | **1:1 直抄**（角度与模型尺寸无关）。已核对：`shoot` 的 `move.rotation` 与 TaCZ `shoot.root.rotation` 逐键相同 |
| 位移长度 | **÷ S_GUN**。脚本用 `S_GUN = 57.07/23.97 = 2.381`（按两个模型 bbox 实测长度比） |
| 左右方向 | **不镜像**（见下） |
| 时间轴 | TaCZ 的 keyframe 时刻直接用作我们的时刻（1:1，单位秒） |
| 手臂骨 | TaCZ 的 `righthand` / `lefthand` / `constraint` / `camera` **全部丢弃**（手上无臂） |

### 关于左右镜像（2026-09 改定）

早先的方案是 `MIRROR_X = −1`（"TaCZ 射手右侧 = −X，与我们相反"），照那个规则弹壳应该往 **+X** 抛。
核对模型实际布局后**否掉了镜像**：

| 部位 | TaCZ 的 x | 我们的 x |
|---|---|---|
| 枪栓/拉柄 | `bolt_rotate` x∈[−2.39, −0.16] | `bolt` x∈[−1.50, −0.10] |
| 弹壳 | `bullet_shell` 起点 x≈−0.04，飞行方向 −X | `casing` x=−0.45，飞行方向 −X |
| 弹匣 | 中置 | 中置（对称） |

两边枪栓与抛壳窗**同在 −X 侧**，手性一致，所以位移直抄、不取反。
（TaCZ 的 `righthand_pos` 在 +X、`lefthand_pos` 在 −X，与我们的 `righthand`(x=−1.05) / `lefthand`(x=+1.5) 相反——
但手臂骨我们根本不用，不影响任何一帧画面。）

> `美术规范.md` 换算表里那行 `MIRROR_X = −1` 尚未同步，以本文件与发布的数据为准。

### 关于 S_GUN 的两个数

- 规范 `美术规范.md` 写的是 `S_GUN = 2.113`（由"官方枪长 54.4 / 我们 24"推来）。
- 脚本实测的是 `57.07 / 23.97 = 2.381`（直接量两个 geo 的 bbox 长度）。
- 差约 11% 的位移量（枪栓行程 1.93u vs 2.18u、弹匣下沉 −9.48u vs −10.4u）。
- **两个数要统一**，但视觉上差别极小（1u ≈ 1 像素），暂时按脚本实测值发布。

## 抄下来的关键数值（已核对进 awm.animation.json）

**后坐 `shoot`**（TaCZ `shoot.root`）：峰值 `-7.95°` 抬枪口、姿态 `[+0.56, +1.33]`（÷2.381），0.6–0.8 s 回位。

**拉栓 `bolt`**（TaCZ `bolt`）：

| 部件 | TaCZ | 我们 |
|---|---|---|
| `root` 峰值旋转 | `[4.09, -3.79, 10.17]` @0.40 s | 同值给 `move` |
| `bolt_rotate` | 0.25→0.35 s 抬到 60°，0.85 复位 | 同（`bolt.rotation.z` 峰值 60.0°） |
| `bolt_group` 后退 | `+4.60u` | `+1.93u` |
| `root` 回位 | 1.20 s | 同 |

**战术换弹 `reload_tactical`**：`move` 旋转峰值 `[-10.25, -2.88, -19.10]` → 保持 → `[-7.64, -4.58, -25.74]`，
2.5 s 回零。弹匣不动枪栓，膛内那发留着。

**空仓换弹 `reload_empty`**：枪身先左倾压低换匣（0–2.1 s，峰值 `-25.74°`），
**再反向倒向抛壳窗一侧**拉栓（2.5–3.7 s，峰值 `+12.14°`），弹壳 2.633–3.033 s 抛出。

**待机 `static_idle`**：TaCZ 的 `static_idle.root` 是**单值 `[0,0,0]`（不是时间曲线）**——
他们的持枪呼吸/惯性摆动在 Java 摆动系统里，clip 本身是静止的。我们照抄，所以进游戏是"枪稳如钉"（见 README 待办 7）。

## 我们做的三处偏离（都是有意的）

1. **抛壳不用可见性开关** —— TaCZ 靠给游戏实体 `bullet_shell` 打 scale 关键帧来藏壳；
   我们的模型自带 `casing` 骨，静止时它就埋在机匣里（`casing` 中心 x=−0.45，机匣侧壁 x=±0.85），
   飞出去之后再 `scale → 0`。规范 §5 禁止的是**整体缩放**，部件级隐藏沿用 TaCZ 的做法。
2. **弹匣用一根骨演两次** —— TaCZ 有 `magzine_and_bullet` / `mag_and_lefthand` 两根；
   我们只有 `magazine`，所以旧匣掉出画面（y≈−9.5）之后再让同一根骨从下方升回来当新匣。
   出画之后再回来，观感上就是"换了个匣"。
3. **没有臂骨** —— 手上无臂，第一人称持枪手臂由游戏玩家手臂渲染。
   TaCZ 的 `righthand`/`lefthand`/`constraint`/`camera` 的动作全部丢弃，
   改由弹匣/枪栓/弹壳/子弹承担全部表演。

## 复核方法

对导出的 JSON 按 1/20 s 采样，断言（数值单位：Blockbench u / 度）：

| 断言 | 期望 |
|---|---|
| `bolt`：弹壳 x 越过机匣侧壁（<−0.86）的首帧 | ≈0.65 s |
| `bolt`：弹壳最远 x | ≈−17.8（1.00 s），随后 `scale → 0` |
| `bolt`：枪栓最大 z（后退） | 1.93 |
| `bolt`：拉柄抬把最大 \|rot.z\| | 60.0° |
| `reload_empty`：弹匣最低 y | ≈−9.48（1.10 s 出画） |
| 所有 clip 引用的骨名 | 必须都在 `awm.geo.json` 的 `bones[].name` 里 |

`tools/check_awm_anim.py` 里就是这套断言；`tools/awm_anim_export.py` 负责
"Blockbench 关键帧 dump → GeckoLib animation.json" 的格式转换。
