# AWM（精密国际 · Precision International AWM）— 资产说明

生成链路：`tools/awm_bb_gen.js`（几何 + 512² 图集）→ `tools/awm_bb_anim.js`（动画）
→ Blockbench `bedrock` 编解码器导出 → `tools/awm_anim_export.py` 转 GeckoLib `animation.json`。

## 文件

| 文件 | 说明 |
|---|---|
| `art/awm/awm.bbmodel` | Blockbench 工程源文件（可继续在 Blockbench 里微调） |
| `art/awm/awm.geo.json` | 几何（bedrock 1.12.0，identifier `geometry.awm`） |
| `art/awm/awm.animation.json` | 动画（bedrock 1.8.0，GeckoLib 可直接读） |
| `art/awm/awm.png` | 512×512 逐面 UV 图集 |
| `art/awm/_anim_raw.json` | 关键帧中间产物（`awm_anim_export.py` 的输入） |
| `art/awm/awm_side.png` / `awm_three_quarter.png` | 预览渲染 |
| `tools/awm_bb_gen.js` | 几何 + 贴图生成器（在 Blockbench 内经 MCP `risky_eval` 执行） |
| `tools/awm_bb_anim.js` | 动画生成器（同上） |
| `tools/awm_anim_export.py` | 关键帧 dump → GeckoLib animation.json |
| `art/awm/sounds/*.ogg` | 音效归档（22 个，TaCZ 原文件逐字节副本，见「来源与许可」） |

## 规范对齐（`美术规范.md`）

- 16u = 1 block；枪口 = **-Z**，上 = **+Y**，右 = **+X**。
- 所有圆柱/环形件（枪管、消焰器、镜筒、镜环、弹匣圆角）由 `create_cylinder` / `ring()` 生成，无手工方块拼圆。
- 贴图 512×512（`Project.texture_width/height = 512`）。
- 动画仅用骨骼 **Translation / Rotation**，无整体缩放。
- 骨骼名对齐 TaCZ AWM 约定：`root / move / body / barrel / bolt / scope / magazine / additional_magazine / constraint / camera / stock / grip / bipod / trigger_group`。
  - 弹匣变体 `mag_standard / mag_extended_1..3` 几何全部挂在 `magazine` 下，运行时由 Java 控制可见性。
  - `additional_magazine / constraint / camera` 保持空组（挂载点用）。

## 贴图集回填（2026-09-23）

**问题**：`awm.png` 与 `awm.geo.json` **不是同一代产物** —— 图集只画到 V=388，而模型 UV 用到 V=453。
2610 个面里 1549 个整块落在空白区、1013 个被 V=388 切穿，游戏里表现为枪身/瞄具大片纯黑。
根因在生成链路末端：`tools/awm_bb_gen.js` 第 7 段只把图集画进 Blockbench 的**内部贴图**
（`TEX.internal`，L315-322），**不写文件**；PNG 靠手工导出 —— 漏导一次就与几何脱代。

**修法**（只碰贴图，几何/动画零改动）：`tools/awm_tex_fill.py`
- 公式照抄生成器 L296-314：`rgb = MAT[材质] × SHADE[面朝向] × grain(x,y) × (1px 边缘 ? 0.76 : 1)`
- 材质**逐方块**反查：用方块自己**已涂绘**的面去套 `MAT[m] × SHADE[面]`（实测中位误差 3.1、90 分位 5.5）；
  环形件等判不出的，依次用「同骨同尺寸兄弟 → 同骨多数材质 → 生成器部件尺寸表 → 兜底表」补齐
- **只写原本 alpha<8 的像素**，并断言所有已涂绘像素逐字节不变（`--dry-run` 可只看统计）

实测：回填 2562 面 / 50604 像素，已涂绘像素改动 **0**；材质来源没有一块落到"未知"。
`tools/check_gun_resources.py` 对 AWM 从 1549 个空白面 → **0**。

> 想彻底根治：把生成器第 7 段的产物落盘纳入流程，或在每次导出后跑一次
> `check_gun_resources.py` —— 现有的「贴图必须 512²」检查**拦不住**这个缺陷。

留档：`awm.pre-fill.bak.png`（修复前）、`tex_fill_compare.png`（前后对比）。

## 动画

十段，全部从 TaCZ 官方 `ai_awp` 直抄（真值来源、换算与偏离见 `tacz_ai_awp_reference.md`）。
**角度 1:1 直抄；位移按 S_GUN 缩放；不做左右镜像。**

| 名称 | 时长 | 循环 | 真正在动的骨 | 说明 |
|---|---|---|---|---|
| `static_idle` | 2.0 s | loop | 无 | 持枪待机。TaCZ 的 `static_idle.root` 本身就是 `[0,0,0]`——他们的呼吸/摆动在 Java 摆动系统里，不在 clip 里，所以这里照抄后是"枪稳如钉"（见待办 7） |
| `static_bolt_caught` | 2.0 s | loop | `bolt` | 空仓挂机：枪栓停在后方待换匣（尚未接线） |
| `draw` | 1.0 s | once | `move` | 掏枪（尚未接线） |
| `put_away` | 0.75 s | once | `move` | 收枪（尚未接线） |
| `shoot` | 0.85 s | once | `move` | 纯后坐：枪口上跳 7.95°、后退 1.33u，0.6 s 回位（与 TaCZ `shoot.root` 的 `rotation` 逐键相同） |
| `bolt` | 1.2667 s | once | `bolt`, `casing`, `move` | 每发拉栓：抬把 60° → 后退 1.93u → 抽壳 → 弹壳向 **−X** 翻飞出画 → 新弹上膛 → 闭锁 |
| `reload_tactical` | 3.0 s | once | `magazine`, `round_in`, `move` | 战术换弹：弹匣下坠出画 → 新匣上行入井；**不动枪栓、不抛壳**，膛内留一发 |
| `reload_empty` | 3.7167 s | once | `magazine`, `bolt`, `casing`, `round_in`, `move` | 空仓换弹：0–2.1 s 换匣 → 2.45–3.7 s 枪身倒向抛壳窗，拉栓、抛壳、上膛、闭锁 |
| `inspect` | 12.7833 s | once | `magazine`, `bolt`, `casing`, `round_in`, `move` | 检视枪械（尚未接线） |
| `inspect_empty` | 10.25 s | once | `magazine`, `bolt`, `casing`, `round_in`, `move` | 空仓检视（尚未接线） |

每段的 `sound_effects` 也是从 TaCZ 同源搬过来的（键为秒，值形如
`apocalypse_zombies:awm_rechamber_out`），只保留我们随包分发的 22 个音效；inspect 系列与
`draw`/`put_away` 用到的 `p23_sn_alpha50_*` 没有随包分发，转录时丢弃并记进 LEDGER。

数值单位：位移为 Blockbench 模型单位（16u = 1 block，GeckoLib 内部 /16），旋转为角度。
Java 侧只接了 5 段（`static_idle` / `shoot` / `bolt` / `reload_tactical` / `reload_empty`），
其余 5 段已在 JSON 里、随时可以接线（见待办 6）。

**手性与镜像（重要）**：我们模型的枪栓（`bolt`，x∈[−1.50,−0.10]）与弹壳（`casing`，x=−0.45，机匣**左**壁 x=−0.85）
和 TaCZ 的 `bolt_rotate`（x∈[−2.39,−0.16]）、`bullet_shell` 同在 **−X** 侧，手性一致，
所以位移**直抄、不取反**。`美术规范.md` 换算表里的 `MIRROR_X = −1`（"TaCZ 射手右侧 = −X，与我们相反"）
是更早的方案，与现在发布的数据不符——以数据为准，规范那行待修订。

**弹壳与子弹怎么"出现"**：`casing` / `round_in` 静止时几何就埋在机匣里（`casing` 中心 x=−0.45，
机匣侧壁 x=±0.85），所以不需要可见性开关；飞出画面后再把 `scale` 打到 0。
这两根骨的 `position` 在片段末尾停在画外，下一段 `static_idle` 会把它们按自己的关键帧拉回原位
（此时 `scale` 仍是 0，看不见），所以片段之间不会拖影。


## 资源路径（已就位）

```
src/main/resources/assets/apocalypse_zombies/
├── geo/awm.geo.json                  →  assets/apocalypse_zombies/geo/awm.geo.json
├── animations/awm.animation.json      →  assets/apocalypse_zombies/animations/awm.animation.json
├── textures/item/awm.png              →  assets/apocalypse_zombies/textures/item/awm.png
└── sounds/awm/*.ogg (22)              →  assets/apocalypse_zombies/sounds/awm/
   sounds.json                         →  22 个音效事件（category: player）
```

## Java 侧（已接入）

| 文件 | 作用 |
|---|---|
| `build.gradle` + `gradle.properties` | `software.bernie.geckolib:geckolib-forge-1.20.1:${geckolib_version}`（`4.8.4`，与游戏实例内已装的 `geckolib-forge-1.20.1-4.8.4.jar` 同版本，避免开发/运行漂移） |
| `item/AWMItem.java` | `extends Item implements GeoItem, GunItem`（`GunItem` = 发包/HUD/开镜共用的枪械接口，M1 加兰德同样实现它）；两个控制器：`main`（循环 `static_idle`）、`action`（四段触发式）。同时是整把枪的**服务端权威状态机**：弹药、动作锁、命中判定都在这里，时长常量与 clip 长度同源（`SHOOT_TICKS`/`BOLT_TICKS`/`RELOAD_*_TICKS`） |
| `client/KeyBindings.java` + `client/ClientModBusEvents.java` | `R` = 换弹（`key.apocalypse_zombies.reload`），mod bus 上注册 |
| `network/ReloadPacket.java` / `network/FirePacket.java` | 客户端 → 服务端"我按了 R / 左键"。两者都只是**请求**：服务端复核手持物、余弹、动作锁之后才决定做什么，连点换不来更快的射速 |
| `client/ClientEvents.java` | 输入层：左键射击（按住连发，实际节奏由服务端锁决定）、右键开镜、R 换弹；并接管 FOV 缩放、取消准星、绘制镜筒与弹药 HUD。第一人称交接也在这一层：开镜过半后 `sightOwnsFrame()` 让整枪与双臂（含副手）退出绘制 |
| `client/GunAimState.java` | **纯客户端**的瞄准状态（右键按住 → 抬镜进度，时长取枪自己的 `aimTime()`）。缩放/姿态/镜片只有本人看得见，所以不进网络。它原先叫 `AWMClientState`，加 M1 时泛化成认 `GunItem` 接口 |
| `client/model/AWMGeoModel.java` | `GeoModel<AWMItem>`，三条路径显式指向 `geo/` `animations/` `textures/item/` |
| `client/renderer/AWMItemRenderer.java` | `GeoItemRenderer<AWMItem>`；手持/GUI 取景由 `models/item/awm.json` 的 `display` 控制（Forge 在调 `renderByItem` **之前**已经把 `display` 压进 pose，所以数值真的生效）。开镜时整枪再抬 0.346 格、内收 0.475 格（`AWMItem.ADS_X/ADS_Y`，量算值而非估值），并抵消 `display` 的旋转，用同一个抬镜进度缓动。第一人称另按 `AWMItem.FIRST_PERSON_SCALE` 整体放大 1.25×（加在姿态链上游，只作用于第一人称；放大与抬枪的耦合关系见待办 3） |
| `data/apocalypse_zombies/damage_type/awm_bullet.json` + `data/minecraft/tags/damage_type/bypasses_armor.json` | 专属伤害类型，并挂进原版 `bypasses_armor` 标签：338 拉普阿穿铁甲，顺带拿到自己的死亡讯息 |
| `registry/ModItems.java` | `DeferredRegister` 注册 `apocalypse_zombies:awm`，加入原版「战斗」创造栏 |
| `registry/ModSounds.java` + `sounds.json` | 22 个音效事件；事件 id 即 sounds.json 的键，资源包可以单独替换任意一个音 |
| `models/item/awm.json` | `parent: builtin/entity` + 各视角 `display` 变换（进游戏后按需微调） |
| `META-INF/mods.toml` | 声明 `geckolib` 强制依赖 `[4.8.4,)` |

游戏内自检：`/give @s apocalypse_zombies:awm`

- **左键** = 开火。播 `shoot`，0.85s（17 ticks）后自动接 `bolt`（拉栓 + 抛壳 + 上膛）——打一发拉一下栓。
  按住不放会按 43 ticks（17 + 26 ≈ 2.15 s/发，约 28 发/分）的节奏继续打——这个节奏由两段 clip 的
  长度决定，**不是**参考数据里的 `rpm 43`（43 是数据里的转速字段，43 ticks 与之无关，纯属数字巧合；
  详见待办 9）。
- **右键（按住）** = 开镜，而且**只开镜**：0.25s 抬镜（对齐参考数据 `aim_time`）→ 视场角收到 20°，屏幕上出现镜筒与分划，
  原版准星被取消；松手即回落。**抬镜过半（`SCOPE_HIDE_MODEL_AT = 0.5`）之后整枪与双臂不再参与第一人称渲染**
  （`GunItem.hidesModelWhileAimed()`：AWM `true`、M1 `false`）。理由是镜片就是一扇窗——摆在窗前的东西正是玩家"透过"
  看到的东西，而抬镜到位时枪恰好压在屏幕正中、挡住镜筒；此时黑色遮罩已铺到 `SCOPE_DARKNESS × progress ≈ 0.47`，
  交接落在半黑画面下，看不到枪凭空消失。副手物品（火把之类）同一帧一并取消，免得挂进镜筒里。
  铁瞄的 M1 必须留在画面里（照门就是瞄准点），所以这条规则问枪自己，而不是写死在渲染层。
- **R** = 换弹：膛内有弹走 `reload_tactical`（只换匣、留一发在膛），打空走 `reload_empty`（换匣 + 拉栓抛壳 + 上弹）。
- 静止时 `static_idle` 循环。

**声音全部是 TaCZ 的原始录音**，且与动作共用一条时间轴：枪声分近/远两版——射手听 `awm_shoot`，
周围 64 格内的其他玩家听 `awm_shoot_3p`（TaCZ 的做法，避免近听自己的枪像被人贴在耳边开火）；
拉栓的四个音（开栓 / 抽壳 / 推弹 / 闭锁）和换弹的八个/九个音按 `sound_effects` 的时刻逐 tick 播放，
所以"咔哒"永远落在动作上而不是动作旁边。时刻表写在 `AWMItem.java` 里，
`tools/check_awm_anim.py` 的第 5 项把它和动画 JSON 逐条比对，并检查每个音效都有定义、有登记、`.ogg` 真的在。

**弹道是真判定，不是特效**：从眼睛拉一条 256 格的射线，先撞方块（墙就停在墙上），沿途最多穿透 4 个生物。
伤害按参考枪数据分档——80 格内 24、160 格内 21、再远 15；爆头 ×2（命中点高于目标身高 82% 即算），
并走挂进 `bypasses_armor` 的专属伤害类型。曳光弹、枪口火光、击中粒子与枪声（服务端播放，附近玩家都能听见）同步出现。

`MAGAZINE_SIZE = 5` 等 NBT 字段与参考数据一致（`awp_data.json` 的 `ammo_amount`、`rpm`、`aim_time`），
并由 `tools/check_awm_anim.py` 的「Java 契约」一项守着：clip 名、触发名、时长常量（= clip 长度 × 20 向上取整）
任何一样对不上就非零退出。

## 待办

1. `WeaponMount` 常量类，与几何 pivot 一一对应（`美术规范.md` 要求同步）：

   | 常量 | 值（geo.json 中为 X 取反后的值） |
   |---|---|
   | `WeaponMount.ROOT` | `(0, -1.07, 1.30)` |
   | `WeaponMount.BOLT_PIVOT` | `(0.42, 1.85, 1.45)` |
   | `WeaponMount.MAG_PIVOT` | `(0, 1.00, -1.45)` |
   | `WeaponMount.MUZZLE` | `(0, 1.575, -18.02)` |
   | `WeaponMount.SCOPE_PIVOT` | `(0, 3.15, -1.20)` |
   | `WeaponMount.TRIGGER_PIVOT` | `(0, 0.85, -0.20)`（扳机铰点，扳机刃绕此点绕 X 转） |

2. ~~射击系统~~ —— **已完成**：左键射击 + 弹道命中 + 分档伤害 + 爆头 + 穿透 + 开镜姿态，见上文「操作」。
   状态仍存在 NBT（`TAG_AMMO / TAG_PENDING / TAG_PENDING_AT / TAG_ACTION / TAG_ACTION_AT /
   TAG_LOCKED_UNTIL`），服务端权威、够用；
   将来要加连发/多武器时再抽成独立的状态机类。
3. 第一人称尺寸由三个数共同决定，都是**按几何算出来的起始值**，进游戏按手感微调：
   `models/item/awm.json` 的 `display.firstperson_*`（基础 `scale 0.78`，逐枪的固有尺寸）、
   `AWMItem.FIRST_PERSON_SCALE`（在第一人称整体再放大 1.25×）、
   `AWMItem.ADS_X / ADS_Y`（开镜抬升：内收 0.475 格、上抬 0.346 格，把镜光轴送到眼前）——
   这两个数是**量出来的**不是估的：`tools/pose_measure.py` 走完整条变换链（手基座 → 姿态 →
   display → 几何）算出"把镜轴送到视轴上"所需的偏移，再与 Java 常量比对（残差 ≤0.001 格）。
   注意后两者是**耦合**的：放大系数作用在姿态链**上游**，`ADS_*` 位于其下游，会跟着一起放大 ——
   所以调放大系数**不必重测** `ADS_*`；反过来，若直接去改 `display` 的 scale，枪体变而姿态不变，
   镜轴会被顶偏（放大倍数越大越明显）。见 `GunItem#firstPersonScale()` 的说明。
   **但 `display` 里不只有缩放**：它的 `rotation`（2° 俯仰 / 4° 偏航）绕在姿态链**内侧**，
   只把 hip 角度归零，瞄具线会是"平行但偏轴"（4.47° —— 任何位移都消不掉，只会随距离放大）。
   所以瞄准时 `GunPose` 还乘上这个旋转的**精确共轭**，角度由 `GunItem#adsPitch()/adsYaw()` 下发，
   由接线检查器逐字核验 —— 详见 `art/m1garand/README.md` 的同一节。
   别处不要再加缩放（`美术规范.md` §5：动骨骼，不动整模）。
4. ~~`mag_standard / mag_extended_1..3` 变体的运行时可见性开关~~ —— 已在数据里解决：
   每段 clip 都给 `mag_extended_1..3` / `mag_spare` 打 `scale = 0`、给 `mag_standard` 打 `scale = 1`，
   换匣时再反过来。不需要 Java 参与。
5. 可选：打光最后一发后的**开栓挂机**状态 —— `static_bolt_caught` 循环已经在 `awm.animation.json` 里，
   缺的是 Java 侧的状态机：最后一发射出后不播 `bolt`（闭锁）而播 `static_bolt_caught`，按 R 换弹后再闭合。
6. 可选：接线 `draw`（掏枪 1.0s）/ `put_away`（收枪 0.75s）/ `inspect`（12.78s）/ `inspect_empty`（10.25s）。
   四段都已在 JSON 里，Java 里只要补 `triggerableAnim` 与触发时机（换手/检视键）。
7. **持枪摆动**：TaCZ 的 `static_idle` 本体是静止的（`root` 恒为 `[0,0,0]`），他们的呼吸/惯性摆动是 Java 摆动系统做的。
   我们照抄后第一人称是"枪稳如钉"。要手感，要么补一套程序化摆动，要么在 `static_idle` 里加一点微动（这是有意的偏离，需要记在这里）。
8. **`美术规范.md` 换算表待修订**：规范里写 `S_GUN = 2.113`、`MIRROR_X = −1`；
   实际发布的数据是 `tools/tacz_anim_transcribe.py` 用的 `S_GUN = 57.07/23.97 = 2.381`（按两个模型的实际 bbox 长度实测），
   且**不镜像**（我们的枪栓/抛壳窗与 TaCZ 同在 −X 侧）。二者差约 11% 位移，需要规范与脚本对齐一个值。
9. **射速与伤害与 TaCZ 官方数据不一致（记一笔，需要时再定）**：
   - 射速：我们 43 ticks/发（17 + 26 ≈ 2.15 s，约 28 发/分）由两段 clip 长度决定；
     TaCZ 官方 `ai_awp_data.json` 是 `rpm 171` + `bolt_action_time 0.9`（实战约 0.9 s 一发）。
     要贴近他们得把 `shoot` 与 `bolt` 叠着播，这是手感决定，不是 bug。
   - 伤害：我们用的是 `hexalunar_gun_pack` 的 24/21/15（分档 80/160）；TaCZ 官方是 `damage 42`
     加 `damage_adjust` 42/36/26。分档距离一致、数值差一倍 —— 要么明确以哪一份为准，要么按原版血量重配。


## 来源与许可

**分三类，许可不一样，别混着说。** 之前的版本写"整包按 GPL-3.0"，那是错的：
TaCZ 的**代码**是 GPL-3.0，**资产**另有声明 —— 依据是其 mod jar 里 `META-INF/mods.toml` 的原文
`license = "GPL3 / CC BY-NC-ND 4.0"`（作者 **Serene Wave Studio | Timeless Squad**，
版本 `tacz-1.20.1-1.1.8-hotfix`）。枪包目录里**没有**许可文件（`gunpack.meta.json` 只有 namespace，
`README.txt` 只讲配置），别去那儿找。

**TaCZ 不是本模组的依赖，也不随本模组分发。** 它只是开发期的参照：持枪 / 换弹 / 拉栓的姿态参考
其 `ai_awp`，音效是临时借用的原样副本。本项目自身代码是 **GPL-3.0-or-later**（仓库根 `LICENSE`），
借用内容只在**开发自用包**里，分发用的 `-clean.jar` 一点没有 —— 完整说明见仓库根 **`NOTICE.md`**。

三个产物（`./gradlew clean build cleanJar borrowedPack`）：

| 产物 | 含借用内容 | 许可 | 用途 |
|---|---|---|---|
| `apocalypse_zombies-<ver>.jar` | 有 | `GPL-3.0-or-later / CC BY-NC-ND 4.0` | 开发 / 自用，不得商业使用、不得公开分发 |
| `apocalypse_zombies-<ver>-clean.jar` | 无 | `GPL-3.0-or-later` | 分发用；动画换成完全原创的手工版 |
| `apocalypse_zombies-borrowed-assets.zip` | 有 | 同上 | 本地资源包，启用后把音效与动画覆盖回来 |

| 内容 | 来源 | 许可 | 我们的处置 |
|---|---|---|---|
| 动画数据（角度、位移、时间轴、`sound_effects`） | TaCZ `assets/tacz/animations/ai_awp.animation.json` 逐键转录 | CC BY-NC-ND 4.0 | **派生作品** —— 只留在自用包里，不进分发产物 |
| 22 个 `.ogg` 音效 | 同枪包 `tacz_sounds/ai_awp/` | CC BY-NC-ND 4.0 | **未修改副本**（md5 与原件逐一相同），同样只留在自用包 |
| 几何、贴图、UV 图集、蒙皮划分 | 本项目自己生成 | 本项目自己的许可 | — |
| 手感数值（`ammo_amount 5`、`aim_time 0.25`、`zoom_model_fov 35`、`head_shot_multiplier 2`、`pierce 4`、分档距离 80/160） | 枪包数据 + 作者自己的 `hexalunar_gun_pack` 的 `awp_data.json` | 数值本身不受版权保护 | — |

- **自用 / 局域网自己玩**：直接用开发包，没有任何实际顾虑，随便改。
- **公开分发**：用 `-clean.jar`。借用内容不进分发产物，所以 ND 与 NC 都不再是问题；
  想在自己机器上找回原样，启用 `borrowed-assets.zip` 那个资源包即可（客户端侧覆盖）。
- **要连借用关系也了断**：音效换 CC0 枪声只需替换 `sounds/awm/*.ogg` 并改 `sounds.json` 里的
  `name`，Java 一行都不用动；动画以 `awm.animation.handmade.bak.json`（五段手工版）为起点重做曲线。

