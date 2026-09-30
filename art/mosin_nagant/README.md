# 莫辛-纳甘 M91/30（Mosin-Nagant，7.62×54R）— 资产说明

按《美术规范.md》逐面 UV 路线生成：**枪口 −Z / 上 +Y / 右 +X**，原点落在机匣后端（≈ 机匣中心一带，见下），
骨骼零旋转，几何全部由生成器产出（不含手工方块）。

生成链路：

```
tools/mosin_nagant_bb_gen.js    几何 + 512² 逐面 UV 图集（Blockbench 内经 MCP risky_eval 执行）
        ↓  geckolib_export_model
art/mosin_nagant/mosin_nagant.geo.json ────────────────► resources/assets/apocalypse_zombies/geo/
tools/mosin_nagant_bb_anim.js   7 段动画
        ↓  geckolib_export_animations
art/mosin_nagant/mosin_nagant.animation.json ─────────► resources/.../animations/
        ↓
tools/check_mosin_art.py        图集自检（逐面 UV 必须落在涂绘过的像素上 + 两份 PNG 字节一致）
tools/check_mosin_anim.py       动画自检（片段长度契约 / 骨名对齐 / 换弹时序 / 隐藏件钉位）
```

## 文件

| 文件 | 说明 |
|---|---|
| `art/mosin_nagant/mosin_nagant.bbmodel` | Blockbench 工程源文件（170 方块 / 21 骨，可继续微调） |
| `art/mosin_nagant/mosin_nagant.geo.json` | 几何（GeckoLib Animated Model，22 骨 / 170 方块 / 1020 面） |
| `art/mosin_nagant/mosin_nagant.animation.json` | 动画（7 段，`geckolib_format_version: 2`） |
| `art/mosin_nagant/mosin_nagant.png` | 512×512 逐面 UV 图集（与资源目录那份字节一致） |
| `art/mosin_nagant/_gen_report.json` | 生成器自检报告（锚点实测、pivot 邻近度、预算、图集用量） |
| `tools/mosin_nagant_bb_gen.js` | 几何 + 贴图生成器 |
| `tools/mosin_nagant_bb_anim.js` | 动画生成器 |
| `tools/check_mosin_art.py` | 图集自检（在仓库根跑） |
| `tools/check_mosin_anim.py` | 动画自检（在仓库根跑） |

音效**不在本目录**：Java 接入时暂用 AWM 那批录音（与 M1 同样处理）。

## 标定（文献尺寸 → 模型）

基准：**M91/30 全长 1232 mm**，比例尺 **53.8 mm/单位**（= 1232 ÷ 22.9u，落在规范"成品 1.0~1.5 格"内）。

| 真机 mm（自枪口量） | 模型 Z | 部件 |
|---|---|---|
| 0 | −17.35 | 枪口（**硬锚点**，Java 弹道/枪口焰用） |
| 665 | −4.99 | 机匣前环（枪管裸露段终点） |
| 930 | −0.06 | 机匣后端（≈ 模型原点） |
| 1232 | +5.55 | 托底板后端 |

| 项目 | 实测值 | 规范锚点 |
|---|---|---|
| 膛线轴 `BORE` | 1.75 | `{0, 1.75, −17.35}` 枪口 ✓ 一致 |
| 前准星刃顶 | **2.68**（= 膛线轴 +50 mm） | 与后照门互校 |
| 后照门战斗缺口底面 | **2.38**（= 膛线轴 +34 mm） | 瞄准线取此值 |
| 抛壳点（弹壳静止位） | **`{0.90, 2.10, −1.95}`** | ✓ 一致（弹壳几何中心实测 = 锚点） |
| 全长 / 高 / 宽 | 22.90u（1.43 格）/ 3.85u / 1.41u | ≤ 2.6 格 ✓ |
| 密度 `S` | **12.0** px/单位（1020 面，图集用到 V=224/512） | 规范值 11~13 ✓ |
| 方块 / 骨骼 | 170 / 22 | ≤600 / ≤40 ✓ |

⚠️ **规范里的旧值 `镜光轴 3.34` 已按新模型更新**：那是 v3 模型的目视高度；新模型是机械瞄准，
瞄准线 = 后照门战斗缺口底面 2.38（前准星刃顶 2.68 互校），与 M1 加兰德同口径记法（M1 记 2.80）。

## 骨树（22 根，pivot 全部在自身几何内，无旋转）

```
root（geo 自带）
└─ move              [0, 1.75, −2.527]   整枪位移/旋转（TaCZ 姿态层；Java 的 GunPose 作用在它上面）
   └─ body           [0, 1.75, −2.527]   枪身
      ├─ constraint / camera / additional_magazine   空控制器（TaCZ 枪包对位用）
      ├─ barrel      [0, 1.75, −4.989]   枪管/通条/前准星/枪箍
      ├─ receiver    [0, 1.75, −2.527]   机匣/装填桥/后照门座
      ├─ bolt        [0, 1.75, −2.108]   枪机（绕膛线轴旋转 + 沿 Z 滑动；pivot 在膛线轴上）
      ├─ rear_sight  [0, 2.27, −6.198]   表尺片（铰链在座前端，向后展开）
      ├─ magazine    [0, 1.081, −0.621]  弹仓（pivot 在弹匣井后缘）
      │  ├─ floorplate [0, 0.653, −2.480]   托底板（前铰链）
      │  ├─ follower   [0, 0.783, −1.551]   托弹板
      │  └─ mag_r1…r5  [±0.07, 1.45/1.19/0.93, −1.551]  仓内 5 发（交错双列）
      ├─ trigger     [0, 1.007, 0.159]   扳机（绕 X 扣压）
      ├─ stock       [0, 1.192, 0.122]   木托/护木/上护木/托底板
      ├─ casing      [0.90, 2.10, −1.95] 弹壳（**静止位 = 抛壳锚点**）
      └─ round_in    [0, 2.642, −4.525]  待压入的那一发（机匣装填桥上方）
```

## 动画（7 段）

| 片段 | 长度 | 循环 | Java `*_TICKS` | 内容 |
|---|---|---|---|---|
| `static_idle` | 2.00 s | loop | `40` | 持枪呼吸/微摆；同时把弹壳/待压弹钉成不可见 |
| `draw` | 0.90 s | once | `18` | 举枪到位（枪身从下方抬起 + 轻微过冲） |
| `shoot` | 0.60 s | once | `12` | 后坐上抬 + 扳机扣放（**不抛壳**：栓动枪的壳在 `bolt` 里抛） |
| `bolt` | 1.10 s | once | `22` | 提柄 80° → 后拉 1.55u → 抛壳 → 推回 → 压柄 |
| `reload_tactical` | 3.60 s | once | `72` | 仓里还有 2 发 → 补 3 发（快节奏） |
| `reload_empty` | 4.40 s | once | `88` | 空仓逐发压入 5 发（0.83 / 1.42 / 2.00 / 2.62 / 3.21 s） |
| `inspect` | 2.60 s | once | `52` | 翻枪查看 + 栓半开（看机匣内） |

**机制要点（真机对应）**

- **直拉机柄**：旋转轴就是膛线轴（pivot 在 `[0, 1.75, −2.108]`），所以旋转是"绕枪机转"而不是"绕手柄转"；
  提柄 80° → 后拉 1.55u（≈90 mm 行程，待击块退出机匣）→ 推回 → 压柄。
- **抛壳**：固定抛壳挺只在枪机**退到位**时把弹壳挑出去，所以 `casing` 的出现时刻（0.458 s）晚于后拉到位（0.417 s）。
  弹壳静止位就在抛壳锚点 `{0.90, 2.10, −1.95}`，出现即飞走（+X 侧翻出）。
- **5 发弹仓**：`reload_empty` 逐发压入，**第 1 发压到底层**（`mag_r5`），最后一发留在最上层（`mag_r1`）——
  与真机弹簧/托弹板行为一致；`follower` 随弹堆下降（0.82 → 0.50 → 0.24 → 0）。
- **半满显示**：`reload_tactical` 假设仓里已有 2 发（`mag_r1/r2` 全程可见）；实际弹数由 Java 状态驱动
  （同 TaCZ 的 `bullet_in_mag` 逻辑），静止态按满 5 发。

参考 `tacz_default_gun/assets/tacz/animations/kar98.animation.json`（kar98k）：换弹分 intro/loop/end、
`reload_loop` 0.6833 s/轮、`bolt` 1.2667 s、`draw` 0.7833 s——本片集的节奏（压弹 0.60 s/轮、`bolt` 1.10 s、
`draw` 0.90 s）按莫辛的直拉机柄手感略作调整。

### 修正（2026-09-30）：压弹件只走竖直

**症状**：用户截图指出 —— 换弹时压在装填桥上的那一发（`round_in`）**一边下沉、一边沿枪身朝射手方向横滑**
（原话「是绿色箭头向上不是蓝色箭头平移」）。

**成因**：`insertRound()` 的位移带了前后分量 —— `z` 由 −0.30 走到 **+2.45**（横滑 2.75u），而竖直只走 1.9u。

**修法**：把该骨 `position` 通道**每一帧的 z 分量归零**（y 曲线与关键帧时刻原样保留）；
`art/` 与 `src/main/resources/` 两份一起改（各 24 帧），生成器 `tools/mosin_nagant_bb_anim.js` 的
`insertRound()` 同步改成 z 恒 0。可复跑补丁：`python tools/reload_press_vertical.py`（`--check` 只校验、不写盘）。

**验收**：`git diff` 每份恰好 24 行、只差 z 一个数；`tools/check_mosin_anim.py` 全过；
**从产物核验**（不看源码）：装入客户端那份 jar 内 `round_in` 的 (x, z) 取值集合 = `{(0, 0.0)}`，
且新旧包逐条目比对**只有** `mosin_nagant.animation.json`（46,106 → 46,082 B）与 manifest 时间戳不同。

## 自检

```bash
python tools/check_mosin_art.py mosin_nagant     # 图集：逐面 UV 落在涂绘区、两份 PNG 字节一致、无重叠
python tools/check_mosin_anim.py mosin_nagant    # 动画：长度契约、骨名对齐、换弹时序、隐藏件钉位
```

两者都必须 0 错误。图集检查是有来历的：M1/AWM 都出现过"贴图只画到 V=237 而模型用到 V=322"，
导致上千个面在游戏里渲染成纯黑——尺寸对、文件在，都不代表内容完整。

## Java 接入（已完成 · 2026-09-24 运行时实测）

资源、Java、注册一次做完，并在专用服务端（`./gradlew runServer`，Forge 47.4.23 + GeckoLib 4.8.4）
上做了运行时验证，不只停在"能编译"：

1. `registry/ModItems.java`：`MOSIN_NAGANT`（`ITEMS.register("mosin_nagant", ...)` + 创造模式页 `event.accept`）
2. `item/MosinNagantItem.java`：弹药 5 发、`SHOOT_TICKS=12 / BOLT_TICKS=22 / RELOAD_TACTICAL_TICKS=72 / RELOAD_EMPTY_TICKS=88`
3. `client/model/MosinNagantGeoModel.java`：三个 `ResourceLocation`
   （`geo/mosin_nagant.geo.json` / `textures/item/mosin_nagant.png` / `animations/mosin_nagant.animation.json`）
4. `client/renderer/MosinNagantItemRenderer.java` + `models/item/mosin_nagant.json`（firstperson 旋转要和 `DISPLAY_PITCH/YAW` 一致）
5. `client/weapon/WeaponArms.java`：**手上靶点是 per-gun 硬编码**，莫辛必须自己加分支，别指望通用解算
6. `data/apocalypse_zombies/damage_type/mosin_nagant_bullet.json`（`message_id: mosin_nagant_bullet`）
   + 两份 lang 的 `item.apocalypse_zombies.mosin_nagant` 与 `death.attack.mosin_nagant_bullet[.player]`

验收：`python tools/check_gun_resources.py`（锚点、时长契约、lang、资源路径、音效一起验，会把三把枪都过一遍，
所以**加新枪后必须跑一遍变异测试**确认新枪真在检查范围内——见仓库 skill）。

### 运行时证据（专用服务端 + RCON，无玩家也能证到注册层）

| 断言 | 证据 |
|---|---|
| mod 以 1.1.5 加载 | `Found valid mod file main with {apocalypse_zombies} mods - versions {1.1.5}` |
| 物品进运行时注册表 | `REGISTRYDUMP` 物品表第 **1276** 号 = `apocalypse_zombies:mosin_nagant`（AWM 1274 / M1 1275 连号） |
| GeckoLib 认了它 | `Registered SyncedAnimatable for class com.apocalypse.zombies.item.MosinNagantItem` |
| lang 运行时解析 | RCON `summon item {Item:{id:"apocalypse_zombies:mosin_nagant"}}` → 回显 **Summoned new Mosin-Nagant M91/30** |
| damage_type 是活条目 | RCON `damage @e[tag=…] 100 apocalypse_zombies:mosin_nagant_bullet` → **Applied 100.0 damage to Zombie**（未注册的类型会在解析期被拒） |
| 服务端干净收尾 | RCON `stop` → `SERVER_EXIT=0`，`BUILD SUCCESSFUL`，无孤立 JVM |

`REGISTRYDUMP` 只覆盖 Forge 静态注册表，`damage_type` 是 datapack 注册表**不在转储里**——别把"转储里没有"
误读成缺陷；要证它只能靠 RCON 命令或 gametest（本版本 Forge 无 `net.minecraftforge.gametest.EmptyTemplate`，
gametest 得自备结构 NBT）。无玩家的服务端**不会把死讯写进日志**（死讯只广播给玩家），
所以击杀消息文案仍需客户端实测。视觉/听觉/动画表现同理，只能在客户端看。

锚点常量按上表同步：枪口 `{0, 1.75, −17.35}`、抛壳 `{0.90, 2.10, −1.95}`、瞄准线 `2.38`。

## 环境坑（Blockbench 5.2.1 + MCP 插件 1.8.1，实测）

- `risky_eval` 在**没有打开工程**时，`Undo` 是 undefined、`Project` 是数字 0 —— 先 `create_project`（格式 `geckolib_model`）再跑脚本。
- `Project.elements` / `Cube.all` 在这个版本**恒为空**：方块只能从骨骼树（`Group.all` → `children`）收集；
  而 `new Cube(...)`/`new Group(...)` 必须再 `init()` 才会登记进 `Project.elements`，否则 `Codecs.project.compile()`
  编出的 `.bbmodel` 是 `elements: 0` 的空壳。
- 项目自带的 `root` 组**不在** `Group.all` 里：不要自己 `new Group({name:'root'})`（每跑一次就多一根空 `root` 骨，
  导出后 geo 里出现重复骨骼）；挂载用 `addTo('root')`，清理用 `Outliner.root`（是数组）。
  生成器现在按这条改过：`Outliner.root` 里筛 `root` 组，**保留第一根、删掉其余**，一根都没有时才新建
  （改之前连跑几轮，导出的 geo 里攒到了 **6 根同名 `root`**——GeckoLib 会认错骨，务必别再用 `Group.all.find` 找 root）。
- 间接 `(0,eval)(src)` 的作用域里**没有 `require`**：生成器把 PNG 的 dataURL / 报告挂到 `globalThis`，
  由外层包装器（有 `require`）写盘。
- `Animation.select()` 在这个版本对脚本建的骨会抛 `Cannot read properties of undefined (reading 'fix_rotation')`，
  时间轴预览因此不生效；**动画数据本身没问题**（导出文件已逐帧核对），要看效果请手动在 Blockbench 里点开片段。
- 逐面 UV 必须在 `Project.box_uv = false` 之后再建方块；`face.texture` 要写贴图 **UUID**（写 0 会退回彩虹占位图）。