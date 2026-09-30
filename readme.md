# Apocalypse Zombies

Forge 1.20.1 的末日僵尸模组。僵尸按全局等级与尸潮波次逐阶进化；月相改写夜晚的规则；
尸潮分五波压境、由精英领队；四只特殊敌对生物各有一套独立技能与骨骼动画；另配套 GeckoLib 驱动的枪械。

| | |
|---|---|
| **当前版本** | `1.1.45` |
| **Minecraft** | 1.20.1 |
| **Forge** | 47.4.0+（开发机运行实例 47.4.23） |
| **GeckoLib** | 4.8.4 —— **硬依赖**（`mandatory=true`），由玩家自行安装，本模组不捆绑 |
| **JDK** | 17 |
| **许可** | 代码 GPL-3.0-or-later；含 TaCZ 借用内容的开发包另受 CC BY-NC-ND 4.0 约束 |

第三方署名与三条许可约束见 [`NOTICE.md`](NOTICE.md)；建模与贴图标准见 [`美术规范.md`](美术规范.md)。
**开发手册见 [`docs/wiki/`](docs/wiki/README.md)**（环境、代码地图、建模流程、工具脚本手册、出货与 CI）。

---

## 构建

```bash
./gradlew build                                  # 开发包（含借用的音效与转录动画）
./gradlew clean build cleanJar borrowedPack      # 三件产物一起出
```

产物都落在 `build/libs/`：

| 产物 | 含 TaCZ 借用内容 | 用途 |
|---|---|---|
| `apocalypse_zombies-<ver>.jar` | **有** | 开发 / 自用。**不得商用、不得公开分发** |
| `apocalypse_zombies-<ver>-clean.jar` | 无 | 分发用。动画为完全原创的手工版 |
| `apocalypse_zombies-borrowed-assets.zip` | 有 | 本地资源包，装进 `resourcepacks/` 把借来的音效与动画覆盖回去 |

### 部署到本地实例

```bash
cp build/libs/apocalypse_zombies-1.1.40.jar \
   "C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods/"
```

**Forge 没有热重载**：换包必须等客户端**完全退出**再重开才生效。游戏运行中替换 `mods/` 里的 jar，
进程持有的仍是旧包。出货一律走 `tools/_deploy_<ver>.py`（自升版号 → 构建 → mods.toml / 资产三向对账
→ 探锁部署 → 其余模组 md5 逐个断「原样在位」）。

> 换版本号后**必须删掉 mods 目录里的旧 jar**，同名模组存在两份会让游戏启动即崩。
> 备份一律改成非 `.jar` 后缀（如 `.jar.old.bak`），Forge 只扫 `.jar`，留着旧版本号的文件不会被加载。

> 若构建**卡在配置阶段**——日志停在 `The daemon has started executing the build.` 之后不再增长、
> `build/` 几分钟内没有新文件——那是 ForgeGradle 在插件 apply 阶段做联网探测时被 socket 阻塞，
> `--offline` / `--no-daemon` 都管不到它（它们只作用于 Gradle 自己的依赖解析层）。
> 用一个必定被拒的代理让该探测立刻失败即可（本机实测：挂 10 分钟零进展 → **25 秒 BUILD SUCCESSFUL**）：
>
> ```bash
> JAVA_TOOL_OPTIONS="-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=1 -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=1" \
>   ./gradlew build --offline --console=plain
> ```
>
> `JAVA_TOOL_OPTIONS` 会被所有 JVM（含 forked daemon）继承；命令行 `-Dorg.gradle.jvmargs="..."` 无效。

---

## 功能

### 僵尸进化（6 阶）

`COMMON` → `REINFORCED` → `ELITE` → `MUTANT` → `TYRANT` → `WARLORD`

- 阶数落在实体 NBT 的 `az_evolution_tier` 上，随世界存续，不因区块卸载丢失。
- 生成不是无条件拉满：波次给「保底阶」（`min(MAX_TIER, waveIndex - 1)`），全局等级给「天花板」
  （`min(MAX_TIER, globalLevel + 1)`），实际取值在两者之间随机 —— 所以早波次不会跳出暴君。
- 另有 `evolution.spawn_with_tier_chance` 决定普通刷怪是否直接带阶出现。
- 带阶僵尸头顶显示阶名与颜色（灰 / 黄 / 金 / 红 / 暗红 / 暗紫）；低阶不挂铭牌，
  是否显示由 `EvolutionTier.showsNamePlate()` 决定。
- 蓝月之夜，带阶僵尸死亡会额外掉落铁锭或金锭（阶越高概率越高）。

### 月相事件（7 种）

| 月相 | 视觉 | 玩法效果 |
|---|---|---|
| `none` | 原版 | — |
| `blood_moon` / `super_blood_moon` | 红月，超级月面更大 | **锁床**：整夜无法入睡（`lunar_events.blood_moon_blocks_sleep` 可关） |
| `yellow_moon` / `super_yellow_moon` | 黄月 | 作物整夜被强制催熟，超级更快 |
| `blue_moon` / `super_blue_moon` | 蓝月 | 全体玩家获得幸运（普通 I / 超级 II），且带阶僵尸死亡额外掉铁/金锭 |

月相由服务端判定并持久化在世界数据里（`ApocalypseData`），客户端通过 `ClientMoonState` 收到后
负责天空色、雾色与月面渲染（`textures/environment/moon_phases.png`）。

### 尸潮（5 波）

四波随机化尸潮依次压境，波次进度与剩余数量显示在 boss bar 上。波次越高，僵尸的起步阶越高。

### 特殊敌对生物（4 种）

**1.1.0 新增。** 全部基于原版敌对生物改造，各带一格技能槽；技能是「前摇 → 命中 → 收招」三段，
命中时刻由 `EliteAbility` 的 `(duration, impactTick)` 定义：

| 实体 ID | 原型 | 技能 | 时长 / 命中 tick | 行为 |
|---|---|---|---|---|
| `screamer_zombie` | 僵尸 | `SCREAM` 尖啸 | 46 / 22 | 给周围尸群挂移动速度 II + 力量 I，并召唤援军 |
| `crusher_zombie` | 僵尸 | `SLAM` 下砸 | 32 / 18 | 范围内造成伤害 + 击退，并挂 60 tick 缓慢 |
| `corroder_zombie` | 僵尸 | `SPIT` 吐酸 | 28 / 15 | 后仰蓄酸 0.75 秒，命中瞬间射出 `acid_projectile` |
| `marksman_skeleton` | 骷髅 | `SNIPE` 蓄力狙击 | 42 / 34 | 蓄力后射出暴击箭 |

- **动画是 Java 侧程序化骨骼动画**，不是 GeckoLib 关键帧文件：`ElitePose` 提供
  `hold` / `strike` / `pulse` 三个姿态量，子类模型实现 `applyCastPose`，再由 `CastPoseBlender`
  插值 —— 所以收招会平滑融回原版姿态，不会硬切。
- 姿态状态走 `SynchedEntityData`（`DATA_ABILITY` / `DATA_ABILITY_TICK`）由服务端同步，
  客户端模型在 `setupAnim` 里读取。
- 四只都有刷怪蛋，创造模式可直接取用测试。

**生成与控制**（1.1.0 接入）：

- 自然生成走**自定义 biome modifier**（`apocalypse_zombies:elite_spawns`），作用于
  `#minecraft:is_overworld`，权重**实时读配置**（默认 3；对照原版四类僵尸各 100，约每 170 只出一只精英）。
- 配套 `SpawnPlacements` 登记 —— 两者缺一不可，只加 biome modifier 会被刷怪器静默跳过。
- **蘑菇岛被显式排除**：`#minecraft:is_overworld` 这个标签包含 `minecraft:mushroom_fields`，
  而它是原版唯一保证不刷怪的群系（玩家当安全屋），所以在生成判定里补了一道否决。
- 精英也随尸潮登场：默认第 3 波起、每两波 +1、封顶 3 只；它们计入 boss bar 总数，也必须清完才算这波结束。

### 美女僵尸 / 士兵僵尸

**1.1.6 起陆续追加**的两只独立精英实体。技能仍是「前摇 → 命中 → 收招」三段，但技能集、骨骼与贴图
各自成篇（面纱 / 长发 / 鬓发 / 拖尾 / 裙摆均为真骨骼）。逐版改动与验收口径见
`art/bride/DELIVERY.md`、`art/bride/PHASE2_DELIVERY.md`、`art/soldier/DELIVERY.md`。

### 枪械

| 物品 ID | 说明 |
|---|---|
| `awm` | 栓动狙击步枪，.338。**镜片即视场**：抬镜时整枪与双臂不再绘制 |
| `m1_garand` | 半自动步枪，.30-06，8 发漏夹。铁瞄 |
| `mosin_nagant` | 栓动步枪，7.62×54R，固定 5 发盒式弹仓。铁瞄 |
| `uzi` | 冲锋枪，9mm，**全自动**：按住左键连发、松手停火、弹匣打空自动停 |
| `crossbow` | 十字弩，现代复合结构；右键 = 透明十字瞄准镜 |

- **五把枪打完自动换弹**：弹匣打空立刻换；空匣状态下扣扳机也触发。
- **铁瞄还是镜，由枪自己回答**：`hasScopeOverlay()` / `hidesModelWhileAimed()` 走 `GunItem` 的实现，
  不写死在渲染层 —— 铁瞄枪（M1 / 莫辛 / Uzi）照门就是瞄准点，枪必须留在画面里。
- **跑步持枪姿态**（1.1.40）：跑动时枪从瞄准线上下到身侧，五把枪共用一套姿态，见更新日志。
- 持枪时**左键开火**（Uzi 按住连发）、**右键抬镜**、`R` 换弹（可在控制里改键，分类「Apocalypse Zombies」）。
- **服务端权威**：客户端只发请求（`FirePacket` / `ReloadPacket`），「有没有子弹、动作是否占用、
  子弹打中了什么」全部由服务端裁决。
- 弹量存在物品 NBT 的 `Ammo` 里；换弹分两路 —— 满弹匣走战术换弹（保留膛内那发），
  空仓走完整上膛流程，动画与音效也不同。
- 姿态走客户端 `GunAimState` + `GunPose`：站立腰射 / 跑步持枪 / 抬镜三态连续混合；`WeaponArms` 按
  玩家皮肤绘制手臂，跟随各枪 `*GeoModel` 给出手部目标。
- 副手 / 背包 / 开镜状态都有对应封包处理。

### 指令

```
/apocalypse status                     # 当前月相、全局等级、尸潮状态
/apocalypse moon <id>                  # 切换月相（none / blood_moon / super_blood_moon /
                                       #   yellow_moon / super_yellow_moon / blue_moon / super_blue_moon）
/apocalypse moon clear|reset           # 清除月相事件
/apocalypse horde start|stop           # 手动起 / 停尸潮
/apocalypse evolution get|set|upgrade  # 查看 / 设置 / 提升进化等级
/apocalypse tiers                      # 列出全部阶位
```

### 配置

`config/apocalypse_zombies-common.toml`，分四段，每项都带注释：

| 段 | 管什么 |
|---|---|
| `lunar_events` | 各月相开关与效果强度（如血月是否锁床） |
| `evolution` | 进化速度、生成带阶概率、各阶数值 |
| `hordes` | 尸潮波次规模、触发条件 |
| `specials` | 特殊敌对生物：`elite_natural_spawn` / `elite_spawn_weight` / `elite_horde_from_wave` / `elite_horde_max_per_wave` |

> `specials.elite_spawn_weight` 改完要**重进世界**才生效 —— biome modifier 在加载时烘焙。

---

## 更新日志

### 1.1.45 — 2026-09-30

**新增 · 远程怪可 opt-in「看得见就能打」——骸骨射手不再对柱顶/塔上的目标一箭不放**

- **症状**：目标只要比射手高一格以上（柱顶、塔上、城墙边），射手**45 秒一箭不放** —— 不举弓、不移动，
  看起来像 AI 卡死。
- **根因**：`MobAiEnhanced` 是全局事件钩子，给所有 `Monster` 挂了 `PreyTargetGoal`；它只在「走得到」时
  （`PreyJudge.canPathTo`，高度容差 1 格）才认这个猎物，够不着的猎物让它空转占住 TARGET 标志 ⇒
  排在后面的玩家/铁傀儡目标永远起不来，`getTarget()` 恒 null。远程怪本不需要走过去 —— 有视线就该开火。
- **修法**：新增实体级 opt-in 接口 `SightFiring`（`double sightFiringRange()`，≤0 = 不启用）；
  `PreyJudge.usable` 判序改为 `inRange` → 贴脸(3 格) → **看得见就能打** → `reachable`。
  只有实现了该接口的怪才放宽，近战怪零影响（爆炸半径 = 「谁实现谁才算」）。
- **同源约束**：`MarksmanSkeleton.sightFiringRange()` 取三件武器射程的最大值
  （`GIANT_ARROW_MAX_RANGE=32` / `LOCK_MAX_RANGE=26` / `BOW_RANGE=24`），**必须与武器入参同一批常量** ——
  报小了退回死锁、报大了锁上打不到的目标。`check_marksman.py` 的 c6 钉住四条不变量
  （实现接口 / 接口存在 / 判序带 `instanceof` 守卫 / 射程同源），并做了负向双向验证（抠守卫、颠倒判序都必红）。
- **实测**（headless 专用服务端 + RCON，同一条判据**先红后绿**）：柱高 3 格、柱顶站无甲铁傀儡 ——
  修前 **45 秒一箭不放**，修后 **1.8 秒**射出骨矢；`tools/rcon_marksman_test.py` **5/5 PASS**（原 4 条 + 柱顶靶一条）。
- **工程**：`mod_version` `1.1.44` → `1.1.45`（`gradle.properties` 仍是唯一来源，`mod.toml` 与 README 跟着走）。

### 1.1.44 — 2026-09-30

**骸骨射手换 GeckoLib 真骨骼 + 新技能「骨矢锁定」**（本版更新日志当时漏记，在此补上）

- **模型**：`marksman_skeleton` 从原版 `SkeletonModel` 换成 GeckoLib 真骨骼 —— 27 骨 / 33 体块 / 198 面，
  贴图 128×128（斗篷 + 骨弓 + 箭袋），总高 32 u = **2.0 格**（与原版骷髅一致 ⇒ 命中箱不漂移）。
  渲染换成 `MarksmanGeoModel` / `MarksmanGeoRenderer`，原版那对已删。
- **技能「骨矢锁定」**：`EliteAbility` **末尾追加** `BONE_LOCK(42, 34)`（`byId` 走 ordinal，插中间会让所有
  精英的施法状态错位）；前摇 26 tick 站定 + 粒子，命中瞬发追踪骨矢，伤害 = **目标最大血量 × 25%**
  且无视护甲 / 附魔 / 抗性 / 盾牌。
- **无敌帧**：1.20.1 的 `LivingEntity.hurt()` 在 `invulnerableTime > 10` 时只结算「本次 − 上次」的差额，
  这个分支没有任何 `DamageTypeTags` 能跳过（`bypasses_invulnerability` 管的是实体标志，
  `bypasses_cooldown` 是 1.20.5+ 才有）。修法：`BoneLockArrow.onHitEntity` 先 `target.invulnerableTime = 0;`
  再结算，实测单发由 24.0 变成 **25.0**。
- **实测**（headless + RCON，**4/4 PASS**）：满防具 + 抗性 V 的铁傀儡打 25 点 `bone_lock` 掉 **25.0**；
  对照组同样 25 点 `minecraft:generic` 掉 **0.0**；目标 10 格外射手自行起手并射出骨矢。
- 发布件仍是 `-clean.jar`（动画为完全原创的手工版，不含借用资产）。

### 1.1.43 — 2026-09-30

**修复 · 刷怪蛋召出的尸潮领主「满血却是第 2 阶段」，并把血量/护甲抬上去**（同日 1.1.42 的方框修复一并记在此）

- **根因**：原版 `Attributes.MAX_HEALTH` 的上限硬编码 1024
  （`RangedAttribute("attribute.name.generic.max_health", 20.0d, 1.0d, 1024.0d)`），且
  `AttributeInstance.calculateValue()` 结尾是 `attribute.sanitizeValue(total)` ——
  **修饰符叠加完还要再夹一次上限**，所以 1.1.41 起写的 2500 一直是 1024；而当时的阶段阈值是绝对数，
  `phaseFor(1024)` → `1024 > 833` → **Phase 2**。「满血 + 第 2 阶段」就是这么来的。
- **修法**：`ModEntities.liftHealthCap()` 反射抬 `RangedAttribute.maxValue`（按**值** 1024.0 认字段 ——
  开发是 Mojang 名、出货包是 SRG 名，写死名字会在另一侧静默失效）；三个阈值改为由 `BOSS_MAX_HEALTH` 推导、
  `phaseFor()` 比**运行时上限的比例**；`finalizeSpawn()` 把出生状态钉死（满血 + 按满血重算阶段 + 计数清零），
  刷怪蛋 / `/summon` / 刷怪笼 / 尸潮第 5 波结构上同构；阶段推进逐级，一击跨两级不再吞掉中间段的入场技与标题。
- **数值**：血量 2500 → **4200**（阈值 2800 / 1400 / 亡语 630）；护甲 5 → **15**、韧性 8 → **12**。
  护甲 5 在 1.20.1 公式下对 15 点伤害只有 **5%** 减伤（等于没穿甲），15/12 是 **−48%**。
- **实测**（headless 专用服务端 + RCON）：`attribute … max_health get` = **4200.0**、`Health` = **4200.0f**、
  `armor` = **15.0**、`armor_toughness` = **12.0**（修前同样是这两个命令量出 1024.0，才定位到上限夹取）。
- 1.1.42（同日）：修掉 `horde_overlord.animation.json` 的 per-axis 关键帧形状 —— 它在 GeckoLib 资源重载里抛
  `JsonParseException`，让客户端清空 `resourcePacks` 并导致全屏文字变方框。

### 1.1.41 — 2026-09-28

**调整 · 手持姿态摆正 + 枪械往画面中间收（五把枪共用）**

腰射时枪身原本是斜的：`GunPose` 的 4° 偏航加在物品模型自带的 4° `display` 偏航**外侧**，两者叠成真实的 8°（`tools/hip_square_probe.py` 量得枪管偏离视轴 4.31°，方向余弦 `(+0.0698, −0.0279, −0.9972)`），屏幕上表现为整把枪歪着摆、右手压在最右下角。

| 对象 | 内容 |
|---|---|
| `GunPose.HIP_YAW/HIP_PITCH/HIP_ROLL` | `4.0 / 1.6 / −3.0` → **`0 / 0 / 0`**。枪管轴线与视轴**严格平行**（`(0, 0, −1)`，0.00°），腰射态也横平竖直；跑步姿态不受影响，仍是刻意的斜持（`SPRINT_*` 未动） |
| `GunPose.HIP_DX/HIP_DY` | `−0.30 / +0.30` → **`−0.38 / +0.27`**。握把屏幕落点 NDC x 由 `+0.54`（Uzi `+0.69`）收到 `+0.30 ~ +0.40`，进入画面下方中段——「右手往中间靠」 |
| 不动的东西 | `ADS_X/ADS_Y`、`DISPLAY_PITCH/YAW`、`FIRST_PERSON_SCALE` 全部原样。抬镜的 `display` 共轭抵消本来就与 hip 角度无关，量算残差仍是 `+0.0004 / +0.0004` 格，**开镜瞄具线零回归** |
| 取值依据 | 新增 `tools/hip_square_probe.py`（复用 `pose_measure.py` 的同一变换链）：输出摆正前/后枪管方向余弦，以及 `HIP_DX/HIP_DY` 六档候选下的握把 / 枪口 / 后照门 NDC 落点 |
| 副作用核对 | 手到肩距离 0.983 → 1.048 格（`WeaponArms` 按此拉伸手臂骨，约 +6.6%），仍在 `美术规范.md` 认可范围内；右键举镜、跑步姿态、`SPRINT_BOB_*` 摇摆均不受影响 |
| 验收 | `gradlew compileJava` 通过；`tools/check_gun_resources.py` 全过（5 枪 + 6 刷怪蛋 + 23 音效）；`pose_measure.py` 对 M1/AWM/Uzi 三把枪开镜残差仍在 0.001 格容差内 |

**注**：`mod_version` 仍是 `1.1.40`（本次未改 `gradle.properties`）；要在游戏里看到效果需重新构建并替换 jar。

### 1.1.40 — 2026-09-28

**新增 · 跑步持枪姿态（五把枪共用）**

停下来是「端着」，跑起来是「拎着」。这一版把两者分开：跑动时枪从瞄准线上下到身侧（偏航 22°、
俯仰 −20°、翻滚 20°，`GunPose.SPRINT_*`），并叠一层随步频起伏的轻微摇摆。

| 对象 | 内容 |
|---|---|
| `GunPose` | 新增跑步混合：位移与旋转都在「站立腰射 ↔ 跑步持枪」之间按 sprint 权重插值，再整体由抬镜权重收回。抬镜满值时 `s = sprint·(1−aim) = 0`，**瞄准态结构上零回归** |
| `GunAimState` | 新增 `sprinting` / `sprintProgress`，0.18 秒渐变进出 —— 与抬镜共用同一套「tick 累加 + 渲染插值」机制 |
| `WeaponHandGrip` | 摇摆相位取自 `walkDistO → walkDist` 的插值（按走过的地面算，不按墙钟），停步即停摆 |
| 取值依据 | 用 `tools/pose_measure.py` 的同一变换链离线解算（FOV 70，即 `onRenderHand` 实际使用的投影）：相对站立腰射，五把枪**枪口一致下压 0.47~0.54 NDC**，双手全在画面内（右手 y −0.61~−0.89） |
| 验收 | `tools/_deploy_140.py`：相对 1.1.39 变化的字节**恰为** 4 个 class + 构建元数据，资产条目零变化；`GunPose.class` 内 8 个跑步常量在、6 个腰射常量原样；`UziItem.class` 逐字节未变（ADS 是残差 0 的已验证量） |

**清理**：`WeaponArms` 里的一次性诊断（每秒一行 `ARMSDBG`）总开关关闭，不再写日志；探针留在原地备用。

### 1.1.37 → 1.1.39 — 2026-09-28（Uzi 冲锋枪）

程序化建模 → Blockbench 精修 → Java 全量接线 → 编译替换测试，三轮收口，逐版取证见
`art/uzi/DELIVERY.md`。

| 版本 | 内容 |
|---|---|
| 1.1.37 | 立项到可玩：几何 / 贴图 / 动画三份产物与 Java 注册一次做完，编译替换测试通过 |
| 1.1.38 | 铁瞄归零：前柱穿出护环，**2.34° 的偏差由几何唯一确定**（不是审美调参），前柱收到 3.26u → 0.00°；`ADS_Y` 0.3118 → 0.3015 |
| 1.1.39 | 腰射基准位抬高 + 手臂入场改造（对标 TaCZ 的持枪位：抬高 `HIP_DX/DY`、肩点外移、`ADS_SHOULDER_PUSH` 1.55 → 1.15）；**五枪打完自动换弹**（打空即换 + 空匣扣扳机也触发） |

1.1.39 的量算口径：原先腰射时枪与双臂整体落在画面下缘以下 —— 抬位后腰射握把 NDC 从 −1.56 到
−0.593，五把枪右手 y 全部进画面（−0.39 ~ −0.75）；瞄准态 `ADS_X −0.4746` / `ADS_Y +0.3015` 残差 −0.0000。

### 1.1.6 → 1.1.36 — 2026-09-26 → 09-28

这一段跨了 31 个版本，逐版的取证、失败与验收留在各功能的交付台账里。下面按功能归并，只记
「改了什么、证据在哪」，细节以台账为准。

**十字弩（1.1.26 → 1.1.36，`art/crossbow/DELIVERY.md`）**

左右凸轮 / 弓臂精确镜像（修「模型不完整、错位」）→ 弓臂几何重定 + 解算器换成「双不变量」版 →
现代复合重构（牙总成搬到弦的落点，重做成「爪座 + 上下颚 + 轴销」的现代勾爪；`check_crossbow_anim.py`
新增长弦道走廊零越界、爪前脸 ↔ 弦后脸 ≤0.05u 两条硬断言）→ **1.1.36 右键 = 透明十字瞄准镜**
（方案 B，`GunItem.SightStyle` 契约，只动 Java）。

**美女僵尸（1.1.6 → 1.1.34，`art/bride/`）**

128 重绘 → PHASE2（1.1.11–1.1.18：四条扩充技能 + 行走重做 + 面部 / 体表重画 + 面纱 / 长发 / 鬓发 /
拖尾 / 裙摆真骨骼）→ 头纱下摆波浪扇贝边（1.1.25）→ 全身位移复标定（1.1.30–1.1.32）→
手臂攻击变明显（1.1.33）→ **目标死锁修复**（1.1.34：`ScentTargetGoal` → `PreyTargetGoal` + `PreyJudge`，
此前她不会攻击村民 / 铁傀儡 / 玩家）。

**士兵僵尸与 AI 强化（1.1.21、1.1.24、1.1.29、1.1.33，`art/soldier/`、`art/ai_enhance/`）**

士兵僵尸交付（1.1.21，md5 `87d93825505d91cdd21a657f24b5edf1`）与四轮 AI 行为强化。

**工程**

- 1.1.7–1.1.8：`mods/` 里的 jar 被外部进程持久持有（禁删 / 改名，但允许写入）→ **升版号换文件名**
  绕过；此后所有出货脚本都按「先验 md5 身份，再当基线」来做。
- 没有 git 仓库：改代码没有回退网，出货一律走 `tools/_deploy_<ver>.py`，并把「量算锚点随几何更新」
  「几何重跑会重掷骨骼 UUID，动画必须跟着重建」写成硬约束。

### 1.1.5 — 2026-09-24

**新增 · 莫辛-纳甘 M91/30：第三把枪，全链路接入**

木/钢结构的栓动步枪，从 Blockbench 脚本到 Java 注册一次做完：22 骨骼 / 170 方块 / 1020 面，
成品 1.43 格（22.9u，真机 1232 mm 按本工程 53.8 mm per unit 折算），512² 逐面 UV 图集，
骨骼一根不带旋转（`美术规范.md` 铁律）。贴图、几何、动画三份产物与 `art/mosin_nagant/` 留档一份哈希一致。

| 对象 | 内容 |
|---|---|
| `MosinNagantItem` | 栓动机构：每次扣扳机只出一发，`shoot`（12t 后坐）之后隔 `SHOOT_TICKS` 再放 `bolt`（22t 拉栓抛壳），闭锁前扳机失效 —— 与 AWM 同构 |
| 弹仓 | **固定 5 发盒式弹仓**。`reload_empty`（88t）开栓 → 一发一发压入 5 发（关键帧 24.2/36.7/48.3/60.0/72.5t）→ 末发闭栓；`reload_tactical`（72t）半仓补 3 发 |
| 瞄具 | 铁瞄：柱式准星 + 切线表尺。`hasScopeOverlay()=false`、`hidesModelWhileAimed()=false` —— 照门就是瞄准点，枪必须留在画面里 |
| 双手 | `MosinNagantGeoModel` 给出手部目标：右手握把 / 直拉机柄 / 弹仓上方压弹，左手托护木；`WeaponArms.renderMosinNagant` 按动作与进度驱动 |
| 音效 | 借 `sounds/awm/` 一套（CC BY-NC-ND 4.0，见 `NOTICE.md`）。**不用弹匣装卸声**——这把枪没有可拆弹匣，用错的声音比没有声音更糟。时刻表按 `mosin_nagant.animation.json` 的关键帧定，不是估的 |
| 弹道 | 7.62×54R：17/14/10 伤害跨 50/140 格，穿 3 个目标，射程 200 —— 介于 M1 的 .30-06 与 AWM 的 .338 之间 |
| 验收 | `tools/check_gun_resources.py`（三把枪全过）+ `check_mosin_art.py` / `check_mosin_anim.py` 均 0 错误 |

**修复 · 按 `logs/` 里的实机报错收口**

| 报错（`logs/`） | 根因 | 处理 |
|---|---|---|
| `Unable to load model: apocalypse_zombies:{screamer_zombie,crusher_zombie,corroder_zombie,marksman_skeleton}_spawn_egg` | `ModItems` 的注释以为"Forge 按 `_spawn_egg` 后缀自动套模型"——查 `ForgeSpawnEggItem` 源码：Forge 只自动注册**染色**（`ItemColors`），模型从来不自动生成。四个刷怪蛋没有 `models/item/*.json`，物品栏里是紫黑 missing 方块 | 补 4 份 `models/item/<id>.json`（`parent: minecraft:item/template_spawn_egg`，与原版刷怪蛋同构），改掉那条误导性注释 |
| `Missing sound for event: apocalypse_zombies:ammo_clip_pop` | `AMMO_CLIP_POP` 在 `ModSounds` 注册了，`sounds.json` 里却没有同名键；旁边的 `src/main/resources/main/assets/.../sound/events/*.json`（1.19 时代的 `sound/events` 写法）路径不合法，是两片打不进命名空间的死文件 | `sounds.json` 补 `ammo_clip_pop` → `awm/awp_reload_empty_mag_drop`（弹夹脱出的金属碰撞，与事件意图一致），删掉 `resources/main/` 整棵死目录 |
| `游戏日志 - 1.20.1-Forge_47.4.23-2.log`（17:26 启动即崩）里的 `ZipException: invalid CEN header (bad signature)` | `mods/` 里有一个中央目录损坏的 jar；现存唯一损坏件是 `hexalunar_calamity-1.0.0-r109.jar.broken`（1,176,823 字节，最后字节停在 `.../mtx.obj` 半截条目，`zipfile` 直接拒绝打开），它当时还叫 `.jar` 所以被 Forge 扫到，事后已改名 | 逐个校验 `mods/*.jar` 的 EOCD 签名：21 个全带 `50 4b 05 06`，当前无损坏件、无需处理。**教训：jar 没下全就重启 = 启动即崩，且崩溃栈不含文件名** |

**自检**：`tools/check_gun_resources.py` 加两段 —— 8. 音效接线（`ModSounds` 每个事件都要有 `sounds.json` 键、反向不许有死键、引用的 `.ogg` 必须真在磁盘）；9. 非枪物品（刷怪蛋）也要有 `models/item/<id>.json`（parent 必须是原版 `template_spawn_egg`）与两套 lang。三把枪 + 4 个刷怪蛋 + 23 个音效全过。

**工程**：`mod_version` `1.1.4` → `1.1.5`（`gradle.properties` 仍是唯一来源，`mod.toml` 与 README 跟着走）。

### 1.1.4 — 2026-09-23

**修复 · AWM 开镜时枪身与双臂挡住镜筒（右键只开镜）**

镜筒在屏幕上是一扇窗：摆在窗前的东西就是玩家"透过"它看到的东西。而抬镜到位时，整枪正好被
`ADS_X/ADS_Y` 拉到屏幕正中、对准目镜 —— 于是枪身和双臂全落在镜筒里。真实的狙击镜此时什么也看不见枪，
你看到的是目镜里的像。

| 对象 | 改动 |
|---|---|
| `GunItem` | 新增 `hidesModelWhileAimed()`：这条规则**问枪自己**，不写死在渲染层 |
| `AWMItem` | `true` —— 镜片即视场 |
| `M1GarandItem` | `false` —— 照门就是瞄准点，枪必须留在画面里 |
| `ClientEvents.sightOwnsFrame()` | 抬镜进度越过 `SCOPE_HIDE_MODEL_AT = 0.5` 后整枪与双臂不再绘制；同一帧一并取消副手（免得火把挂进镜筒） |

交接时机是量出来的、不是拍的：黑色遮罩的浓度是 `SCOPE_DARKNESS × progress`，过半时为 **0.47** ——
枪是在半黑画面下退场的，看不到凭空消失；`RenderHandEvent` 的取消照旧保留，否则原版那只单臂会顺着空档回来。
铁瞄的 M1 之所以不能一起隐藏，是因为它的瞄准点就是枪上的照门。

**修复 · M1 加兰德两段换弹与拉栓按真机机构重做**

旧版把枪机留在闭锁位、只让漏夹下压 —— 真机上此时井口被枪机挡死，漏夹物理上压不进去。动作顺序改为
野战手册的四步：**① 导气杆拉到底并挂住 → ② 漏夹垂直压入弹夹井 → ③ 松手，枪机被漏夹自动释放前冲 →
④ 掌根拍拉机柄后端闭锁**。`reload_empty`（3.0s）与 `reload_tactical`（2.6s）都走这套顺序，第 ④ 步做成
前冲末端的减速节拍（`0.88 → 0.5 → 0.2 → 0.06 → 0`）；`shoot` 的半自动枪机循环补到与 `bolt` 相同的
**1.10u** 全行程（原来只有一半，越不过漏夹末弹底缘）。枪机后退量沿用 `bolt` 段的既有值，真机行程
6.6 cm ≈ 1.06u，差异已记录在 `art/m1garand/README.md`。

**新增 · 确定性导出链（M1 动画）**

MCP 的 `geckolib_*` 导出工具在本机工程状态下被禁用，改为：
`tools/m1_garand_bb_anim.js`（生成器顺手把原始关键帧写成 `art/m1garand/_anim_raw.json`）→
`tools/m1_anim_export.py`（raw dump → GeckoLib JSON，复刻插件的导出规则：24 fps 半点进位吸附、
单键通道静态缩写、多键 `post` + `lerp_mode`、左右手系翻转 position `[−x,y,z]` / rotation `[−x,−y,z]`）。
**转换器的正确性用"未改动的动画必须逐字节重现出厂文件"验**：`static_idle` / `draw` / `bolt` 三段与改动前
逐字节一致，`shoot` 只差枪机通道，两段换弹是预期重写 —— 差异全部能解释才写盘。

**新增 · 机构自检**：`tools/check_m1_reload.py` —— 起手枪机在闭锁位、0.35s 内拉到底、漏夹出现与卡住时
枪机仍在后退位、之后才自动前冲、前冲末端有拍击分级、半自动走全行程、`scale` 只出现 0/1（禁止整体缩放）。
以后改动画破坏机构会立刻变红。

**修复 · 关键帧撞帧（漏夹"永不消失"）**

关键帧在**导出时**才按 24 fps 吸附，相隔 < 1/24 s 的两个键会并到同一帧而丢掉一个：旧漏夹"消失"与新漏夹
"出现"那对 `scale` 键（0.98 / 1.02）双双落到第 24 帧，表现为旧夹永不消失、位置从"飞走"插值回"压入"划弧。
现在生成器**写入时就吸附并检测撞帧**（撞帧打 `KEYFRAME COLLISION`），这对键直接写成帧对齐的 `1.0` / `25/24`。

**工程**：版本号 `1.1.3` → `1.1.4`（`gradle.properties` 的 `mod_version` 仍是唯一来源，`build.gradle` 与
`mods.toml` 由占位符展开；根 `mod.toml` 同步）。

### 1.1.3 — 2026-09-23

**修复 · M1 Garand 漏夹井整体偏前一个井长（82mm）**

井在模型里落在机匣前缘（旧值 519…618mm，枪口起算），而真机漏夹是压进**机匣上方紧挨闭锁面**的井：
枪管 24″ = 610mm ⇒ 闭锁面在枪口后 610mm ⇒ 井前壁就压在这个面上，井长取漏夹（85mm）加余量 ⇒ **601…700mm**。
后壁 700mm 恰好落在模型里已有的 `Z(700)`（拉机柄 / 后照门座前沿），两个独立来源互证。
旧值的成因是 v3 把参考图里“木护木 / 木托颈”的边界当成了机匣前缘 —— 真机机匣 221mm，模型 280mm，
这段偏差一直没动，于是井被钉在了错误的一端。

| 对象 | 改动 |
|---|---|
| 漏夹井（5 方块） | Δz **+1.312u（+82mm）** → z −3.984…−2.400 |
| 机匣桥面 `brg_top` | 起端 Z(652) → **Z(700)**（井口让开） |
| 漏夹盖 / 漏夹 | Δz +1.312u；盖 pivot 留在 Z(799)（纯平移，固定基准） |
| 弹壳 `casing` | Δz **−0.752u** → 静止位从抛壳窗外（795mm）移到窗内中心（748mm） |
| `clip_in` 动画两段 | 旋转全清零、位移 x 归零（装填 = 平移合上，不再翻转），垂直压入保留 |
| `M1GarandGeoModel.CLIP` | z −4.60 → **−3.29** |
| `bolt_chan` 枪机通道 | 不动（首版工具按 bbox 把井内腔与它一起搬走，已回填并加断言） |

**新增 · 标定工具**

- `tools/m1_well_shift.py`：几何 + 动画 + Java 常量同批改动，**幂等**（定位同时接受新旧两种外框，
  出现“半新半旧”直接拒绝写盘），`--check` 预演不落盘，末尾跑一遍不变量断言。
- `tools/m1_well_overlay.py`：把新旧井位叠加到真机侧视参考图上（`art/m1garand/well_fix_overlay.png`），
  逐幅标定 —— 参考图是上下两幅方向相反的照片合成图，取并集算剪影会把比例和方向都算错。

**文档**

- `art/m1garand/README.md`：补真机标定表、井位判据（画的是**闭锁面**，不是机匣前缘）与本次改动清单。

**工程**

- 版本号 `1.1.2` → `1.1.3`（`gradle.properties` 的 `mod_version` 是唯一来源，`build.gradle` 与 `mods.toml` 由占位符展开；根 `mod.toml` 同步）。

### 1.1.2 — 2026-09-23

**修复 · 右键开镜时照门与准星不共线（缺的是一项旋转，不是常量没调好）**

`models/item/*.json` 的 `display` 里除缩放外还有 **rotation**（两把枪同为俯仰 2° / 偏航 4°），
它绕在姿态链**内侧**。把 hip 姿态的偏航/俯仰归零只让枪“不再歪”，前后照门仍差 **4.47°** ——
这是**平行但偏轴**，`ADS_X / ADS_Y` 无论怎么调都消不掉（只会随距离放大）。
修法是在 `GunPose` 里再乘这个旋转的**精确共轭**：用与 vanilla `ItemTransform.apply` 同一个
`Quaternionf.rotationXYZ` 构造再取共轭 ⇒ 构造性精确，不依赖 JOML 内部的结合次序。
角度由 `GunItem#adsPitch() / adsYaw()` 逐枪下发，两把枪的瞄具线与视轴夹角 **4.47° → 0.00°**。

**修复 · 开镜抬枪位移改为量算值**（原先是从 hip 姿态的偏移反推的估值）

| | 改前 | 改后（量算） | 与量算残差 |
|---|---|---|---|
| M1 Garand `ADS_X / ADS_Y` | −0.06 / +0.28 | **−0.475 / +0.346** | 0.0004 格 |
| AWM `ADS_X / ADS_Y` | −0.12 / +0.25 | **−0.475 / +0.346** | 0.0004 格 |

**调整 · 手持位置更靠画面内侧**（`GunPose.HIP_DX / HIP_DY`：−0.06 / +0.04 → **−0.10 / +0.08**）

握把（也就是右手抓握处）的屏幕落点从 NDC `(+1.24, −1.14)`（在画面外 14%）移到 `(+1.12, −1.02)`，
刚好压在下缘上 —— 腰射时能隐约看见右手，换弹动作不再被裁掉大半。画面右缘为 `+1.78`、下缘为 `−1.00`。

**新增 · 姿态量算工具** `tools/pose_measure.py`

走完整条变换链（手基座 → 姿态 → `display` → 几何）量算“把瞄具线送到视轴上”所需的位移与旋转，
并**自校验** Java 常量（与量算不符直接报 ✗）；另打印若干档 `HIP_DX / HIP_DY` 的 NDC 落点供取舍。
`tools/check_gun_resources.py` 相应增加两条断言：`adsPitch() / adsYaw()` 必须与物品模型 JSON 的
`display` rotation 逐字一致（且 roll 必须为 0）、`ADS_*` 必须落在量算区间 —— 两项都先拿旧值跑出过失败。

**文档**

- 根 README 与两把枪的 `art/<武器>/README.md`：补上 `display` 旋转这一环，以及“位移消不掉旋转误差”的判据。
- README「构建」一节记录本机构建在配置阶段被 ForgeGradle 联网探测阻塞的现象与解法。

**工程**

- 版本号 `1.1.1` → `1.1.2`（`gradle.properties` 的 `mod_version` 是唯一来源，`build.gradle` 与 `mods.toml` 由占位符展开；根 `mod.toml` 同步）。

### 1.1.1 — 2026-09-23

**修复 · 两把枪的贴图集与几何“脱代”（游戏里表现为枪身大片发黑）**

两把枪的图集都有一块**没画到模型 UV 用到的范围**，采到全透明像素 → 渲染成纯黑。
几何 / 动画 / UV / 贴图尺寸检查全绿，只有**逐面覆盖率**能看出来。同一类缺陷的两种形态：

- **M1 Garand**：生成器产物只写进 `art/`，资源目录那份是**更早的截断导出**（图只画到 V=237，UV 用到 V=322）。
  已装回 `art/m1garand/m1_garand_geo.png` 权威产物，并让生成器同时写 `art/` 与资源目录两处。
- **AWM**：图集本身与几何**不同代** —— 生成器的贴图段只把图集画进 Blockbench 的**内部贴图**、**不写文件**，
  PNG 靠手工导出，漏导一次就停在 V=388（UV 用到 V=453）。已按生成器自己的色板与绘制公式**逐像素回填**
  （`tools/awm_tex_fill.py`）：2562 面 / 50604 像素，只写原本全透明的像素，**已涂绘像素零改动**（脚本内断言）。

**新增 · 资源接线自检** `tools/check_gun_resources.py`

从注册表读出枪的清单逐把校验：资源路径、驱动骨与 clip 名对齐、`ANIM_*` / `TRIGGER_*` 与动画文件逐条匹配、
动作时长常量（按向上取整比对）、贴图 512²，以及新增的**逐面 UV 覆盖率** ——
旧图对 M1 报 1514/2076 面空白、对 AWM 报 1549/2610，修好后两把枪均为 **0**。
检查器自身做过变异测试（故意改错值必须报错），避免“永远绿的检查器”。

**文档**

- `美术规范.md` 增加“图集必须画满模型用到的 UV”硬要求与对应的检查手段（只看尺寸拦不住它）。
- 两把枪的 `art/<武器>/README.md` 记录故障现象、根因与修法；修复前的图集留档为 `*.pre-fill.bak.png` / `*.old-resource.bak.png`。

**工程**

- 版本号 `1.1.0` → `1.1.1`（`gradle.properties` 的 `mod_version` 是唯一来源，`build.gradle` 与 `mods.toml` 由占位符展开；根 `mod.toml` 同步）。

### 1.1.0 — 2026-09-23

**新增 · 特殊敌对生物**

- 四只特殊敌对生物：`screamer_zombie`、`crusher_zombie`、`corroder_zombie`、`marksman_skeleton`，
  及其投射物 `acid_projectile` 与四个刷怪蛋。
- 每只一格技能槽（`SCREAM` / `SLAM` / `SPIT` / `SNIPE`），前摇—命中—收招三段齐备。
- 姿态为 Java 侧程序化骨骼动画（`ElitePose` + `CastPoseBlender`），不依赖 GeckoLib 关键帧文件；
  收招插值回原版姿态，不硬切。
- 技能状态经 `SynchedEntityData` 同步，服务端权威。

**新增 · 生成与控制**

- 自定义 biome modifier（`apocalypse_zombies:elite_spawns`）+ `SpawnPlacements` 登记，两件套缺一不可。
- 权重实时读配置，默认 3（约每 170 只怪出一只精英）。
- 精英随尸潮登场（默认第 3 波起、每两波 +1、封顶 3），计入 boss bar 总数与波次完成判定。
- 新增 `[specials]` 配置段。

**修复**

- **蘑菇岛不再刷精英**：`#minecraft:is_overworld` 含 `minecraft:mushroom_fields`，
  会把原版唯一的安全屋破掉，已在生成判定里显式否决。
- 精英不再随机持铁剑出场：原版僵尸 1%~5% 会带武器生成，与精英模型自带的武器重复，已堵掉装备槽随机。

**调整 · 枪械第一人称尺寸**

- 两把枪在第一人称整体放大 25%（`AWMItem.FIRST_PERSON_SCALE` / `M1GarandItem.FIRST_PERSON_SCALE`，
  经 `GunItem#firstPersonScale()` 下发）；第三人称、GUI、掉落物与展示框的尺寸不变。
- 放大加在**姿态链上游**（`WeaponHandGrip` 里手基座与 `GunPose` 之间的 `pose.scale`），而不是改物品模型的
  `display`：`display` 位于姿态链下游，只放大枪体而不放大抬枪位移，开镜时镜轴会被顶偏；
  加在上游则 `ADS_X / ADS_Y` 随之等比放大，镜轴仍落在屏幕中心，**调放大系数不必重测**这两个常量。
  手的锚点取自 GeckoLib 渲染矩阵（`GunFrame`），自动跟随，无需另配。
- 物品模型的 `display` 里还有**旋转**（逐枪 2° 俯仰 / 4° 偏航），它同样绕在姿态链**内侧**：
  只把 hip 角度归零并不足以让瞄具线与视轴平行，会残留 4.47° 的"平行但偏轴"，而**位移消不掉旋转误差**。
  瞄准时 `GunPose` 额外乘上该旋转的**精确共轭**（用与 vanilla `ItemTransform` 同一个
  `Quaternionf.rotationXYZ` 构造再取共轭 ⇒ 构造性精确，与 JOML 内部次序无关），角度由
  `GunItem#adsPitch()/adsYaw()` 下发，接线检查器逐字核验两者一致。
- 放大系数是逐枪的常量，进游戏按观感微调（`1.0` = 关闭）。

**工程**

- 版本号 `1.0.0` → `1.1.0`（`gradle.properties` 的 `mod_version` 是唯一来源，
  `build.gradle` 与 `mods.toml` 都由占位符展开；根目录 `mod.toml` 同步）。
- 全量重编（`--no-build-cache --rerun-tasks`）通过：**0 错误 / 21 警告**，
  警告全部是 `new ResourceLocation(String, String)` 的 `[removal]` 弃用（Forge 为 1.21 提前标记，
  1.20.1 下无害），共 19 处调用点，待后续统一迁移到 `ResourceLocation.fromNamespaceAndPath` / `parse`。

**待验证**

- 特殊敌对生物**已通过编译与部署校验**，但技能与动画的游戏内观感（三段姿态是否连贯、
  收招是否平滑、特效与命中是否对齐）**尚待客户端实测**。
- 枪械第一人称放大 25% 是起始值，观感同样**尚待客户端实测**（`display` 的基础尺寸 0.78 / 0.82 未动）。
- 1.1.0 发布后发现的**两把枪贴图集缺陷**见上方 1.1.1（游戏内表现为枪身大片发黑）。

### 1.0.0 — 初始版本

- 僵尸六阶进化系统与全局等级。
- 七种月相事件及其世界效果（锁床 / 催熟 / 幸运与额外掉落）。
- 四波随机化尸潮与 boss bar 进度条。
- GeckoLib 枪械：`awm`、`m1_garand`，服务端权威判定、NBT 状态机、战术 / 空仓换弹分流。

---

## 许可与署名

- **本项目代码**：GPL-3.0-or-later，全文见 [`LICENSE`](LICENSE)。
- **借用的第三方内容**（22 个音效 + 转录动画，来源 Timeless & Classics Guns: Zero / Serene Wave Studio）
  **只存在于开发自用包**，受 CC BY-NC-ND 4.0 约束：不得商用、不得公开分发、不得发布改编版。
  分发请用 `-clean.jar`。详见 [`NOTICE.md`](NOTICE.md)。
- **GeckoLib**（MIT）为硬依赖，不随本模组分发。
- Not affiliated with Mojang or Microsoft. 本模组不含任何 Minecraft 官方资源，使用需正版游戏。

### 版权行

> Copyright (C) `<年份>` `<著作权人>` —— **待项目所有者填写**。
> `NOTICE.md` 已把它列为发布前待办项；模组元数据里 `mod_authors` 目前是 `Hermes`。
