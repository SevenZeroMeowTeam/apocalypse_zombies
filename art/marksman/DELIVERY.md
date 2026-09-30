# 骸骨射手（精英骷髅 GeckoLib 真骨骼 + 骨矢锁定）· 交付台账

**日期**：2026-09-30　**当前版本**：`1.1.45`（**已部署** 13:21:38，md5 `79b845e4bab9b29d53168cfd0e6c2512`，2,065,090 B）
**1.1.45 = 本线的收尾改动**：远程怪可 opt-in「看得见就能打」，射手不再对柱顶/塔上的目标一箭不放（见 §六）
**上一版**：`1.1.44`（`39b7db93d4d054bb5e2d06276634c165`）已随本次部署移入 `mods_backup/`
**发布件**：GitHub Release [`v1.1.45`](https://github.com/SevenZeroMeowTeam/apocalypse_zombies/releases/tag/v1.1.45)
→ 资产 `apocalypse_zombies-1.1.45-clean.jar`（**1,400,862 B**；tag 指向 `3457ae2`，CI run `36673197744` 绿；
  该次 sha256 `34e2a0ef…9b83`，与 GitHub API 声明的 `digest` 一致 —— 但后续任何提交都会 `--clobber`
  重刷该附件，**md5/sha256 只对当次查询有效**，认版本请认 tag）
**历史发布件**：`v1.1.44`（`apocalypse_zombies-1.1.44-clean.jar`，1,400,156 B；tag `e9089fc`，CI run `36670289371`）
**历史版本**：`1.1.43`（`80be27db080ffeff62cfe57a865200e2`）在 `mods_backup/`，同目录还有 `1.1.42`

**需求（转述自对话，非逐字引文）**：把既有精英怪「骸骨射手」`MarksmanSkeleton` 从原版
`SkeletonModel` 换成 **GeckoLib 真骨骼模型**，并挂新技能「骨矢锁定」——**100% 自瞄必中、
无视无敌帧、伤害 = 目标最大血量 × 25%**（Config 可调），含建模 / 动画 / 粒子。

**范围**：`MarksmanSkeleton` 一条线（模型 + 动画 + 贴图 + 技能 + 弹体 + 伤害类型）。
**不动**任何 Boss / 枪械的几何、贴图与冻结数值 —— 出货闸门逐条字节比对守住这一点。

---

## 一、需求落点

| # | 需求 | 落地 |
|---|------|------|
| ① | **换成真骨骼** | `MarksmanSkeleton implements EliteMob, GeoEntity`；`MarksmanGeoModel` + `MarksmanGeoRenderer` 取代原版 `MarksmanModel` / `MarksmanRenderer`（两个旧类已删）；`registerControllers` 挂 `movement` + `cast` 两条控制器 |
| ② | **100% 自瞄必中** | `BoneLockArrow extends GiantArrow`：继承追踪物理（每 tick 修向 + 目标速度前导），**0 散布**、命中即碎（不穿透） |
| ③ | **无视无敌帧** | `onHitEntity` 命中时先 `target.invulnerableTime = 0;` 再 `hurt(...)` —— **标签做不到**，见 §四.1；闸门 `check_marksman.py` 的 c5 钉住这一行 |
| ④ | **伤害 = 最大血量 × 25%** | `damage = target.getMaxHealth() * Config.AI_MARKSMAN_LOCK_RATIO`（默认 `0.25`，固定值、无视护甲）；20 血 → 5.0，100 血 → 25.0 |
| ⑤ | **Config 可调** | `AI_MARKSMAN_LOCK_RATIO`(0.25) / `_COOLDOWN`(160) / `_TURN`(60°) / `_SPEED`(1.6) / `_LIFE`(100) |
| ⑥ | **建模 / 动画 / 粒子** | Blockbench 5.2.1 + MCP 插件 1.8.1 生成（`tools/marksman_bb_gen.js` + `marksman_bb_anim.js` = 唯一真相源）；前摇眼眶与弓身 `SOUL_FIRE_FLAME`、释放 `SOUL` + `DAMAGE_INDICATOR`、弹体每 tick 尾迹 |

---

## 二、美术规格（生成器 = 唯一真相源）

| 项 | 值 |
|---|---|
| 坐标铁律 | 16u = 1 格；上 = +Y；正面 = −Z；+X = 模型自身右侧；原点 = 两脚间地面 |
| 体格 | **2.0 格**（脚底 0 → 颅顶 32u），与原版骷髅一致 ⇒ **命中箱不漂移**（`ModEntities` 的 `sized(0.6, 1.99)` 与属性表一律未动） |
| 规模 | **27 骨 / 33 体块 / 198 面**；密度 2.00 px/u |
| 贴图 | **128×128**（斗篷 + 骨弓 + 箭袋全装束），逐面 UV 图集 |
| 动画 | 4 段：`idle` 3.0s(loop) / `walk` 1.0s(loop) / `shoot` 0.9s / **`skill_bone_lock` 2.1s**（命中帧 **1.70s = impactTick 34**）；**无任何 scale 通道**，rest 姿态旋转全零 |
| 三向一致 | `art/marksman` == `src/main/resources` == jar：geo `ca0172691c87afecadb7a14af90e0170`、anim `f0a1b86056781da31070dae54c5b8444`、png `9388d2261b372bc51e3a93b64713e9ad` |

---

## 三、验收证据

| 判据 | 结果 |
|---|---|
| `tools/rcon_marksman_test.py`（headless 服务端 + RCON） | **4/4 PASS** —— ① 满防具（保护 IV 下界合金）+ 抗性 V 打 25 点 `bone_lock` → 掉 **25.0**；② 对照组同数值 `generic` → 掉 **0.0**；③ 目标 10 格外技能自放并射出骨矢；④ 无敌帧被每 0.1 秒压满（31 次）时单发仍恰好 **25.0** |
| 全部闸门 | **15 个 `tools/check_*.py` 全绿**（含新增 `check_marksman.py` 的 c1–c5） |
| 闸门能红 | c5 正反两遍：正常 13 PASS / 抠掉 `invulnerableTime = 0` 必红 / 还原必绿 |
| 构建 | `./gradlew clean build --offline` → BUILD SUCCESSFUL |
| 出货闸门 | `tools/_deploy_144.py`：基线 md5 认身份 + 变更集合 12 改 / 10 增 / 2 删逐条比对 + 三向对账 + 数据包契约 + 门禁 + 备份 3 份 |
| **1.1.45 复跑** | `tools/rcon_marksman_test.py` **5/5 PASS**（原 4 条 + ⑤ 柱顶靶）+ 4 门禁全绿 |
| **1.1.45 出货闸门** | `tools/_deploy_145.py`：基线 md5 认身份 + 变化集合 **5 改 / 1 增 / 0 删** + **「资产零漂移」断言** + 三向对账（geo/anim/png 与 1.1.44 逐字节同）+ 数据包契约 + 门禁 + 备份 3 份 |

---

## 四、三条实测踩出来的坑（都已修，别再踩）

1. **「无视无敌帧」标签做不到** —— 1.20.1 的 `LivingEntity.hurt()` 在 `invulnerableTime > 10` 时
   只结算「本次伤害 − 上次伤害」的**差额**，而这个分支**没有任何 `DamageTypeTags` 能跳过**：
   `bypasses_invulnerability` 管的是实体身上的 `Invulnerable` 标志，`bypasses_cooldown` 是
   1.20.5+ 才引入的（写在 1.20.1 里 = 整个标签文件被静默丢弃）。
   实测：目标先挨 1 点普通伤害，25 点的骨矢只掉 **24.0**。⇒ 只能代码清零计数器。
2. **射手「不索敌」是测量环境的锅，技能代码没错** —— `MobAiEnhanced` 是全局事件钩子，给所有
   `Monster` 挂了 `SharedAggroGoal(p0)` 与 `PreyTargetGoal(p1)`；后者在「猎物在追随范围内、
   但走不到」时空转**占住 TARGET 标志**，排在 p3 的玩家/铁傀儡目标永远起不来。
   验收斗场因此必须围三格高 `barrier` 围墙 —— 射手带 `KeepDistanceGoal`（7~18 格），
   没墙它会自己走下 y=100 的台子掉到地面，之后既没视线也没法寻路。
   ★ **后续（1.1.45）：这条判断只对了一半。**「走不到」在斗场是干扰项，但在**正常游戏里同样是真
   bug** —— 玩家只要站得比射手高一格以上（柱顶 / 塔上 / 城墙边），射手就一箭不放 45 秒。
   根因就是这里写的那条「空转占 TARGET 标志」，修法见 §六。
3. **验收必须区域清场** —— 斗场里残留的实体（尤其碰撞箱巨大的 Boss，常带 `Invulnerable`）
   会把每一发弹体都吃掉、`hurt()` 返回 false，表现成「技能放了却不掉血」。
   另外读属性别用 `/data get entity … Attributes`（响应会被截断，正则失配后静默返回 None），
   用 `/attribute <e> minecraft:generic.max_health get`。

---

## 五、交付物与注意事项

| 项 | 位置 |
|---|---|
| 契约与接口 | `art/marksman/DESIGN.md`（骨骼名 ↔ Java、clip 名 ↔ `ANIM_*`、伤害口径） |
| 生成器 | `tools/marksman_bb_gen.js` / `.py`（几何 + 贴图）、`tools/marksman_bb_anim.js` / `marksman_anim.py`（4 段 clip + bedrock 1.8.0 导出）、`marksman_pose_shot.py`（姿态抓图） |
| 闸门 | `tools/check_marksman.py`（c1–c5）、`tools/check_bride_combat.py`（`enum_append_only` 语义改为「冻结前缀之后」） |
| 验收 | `tools/rcon_marksman_test.py`（口径见 §三） |
| 出货脚本 | `tools/_deploy_144.py`（钉死 1.1.43 基线 md5 + 变更集合）、`tools/_deploy_145.py`（钉死 1.1.44 基线 md5 + 本线的收尾改动） |

* **Forge 无热重载**：换包后必须**完全退出**重开客户端（退到主菜单不算）。
* **发布件 `.jar` 是 clean 构建**（不含 TaCZ 借用资产），已核验其中 **0 处**网易字样。
* **已决（1.1.45 落地）**：原先的未决项「射手沿共享调度器、对**看得见但走不到**的目标不会开火」——
  用户拍板放宽，实现为实体级 opt-in 接口 `SightFiring`（近战怪零影响，见 §六）。
* **待用户实测**：模型 / 动画 / 粒子的客户端观感 + **柱顶目标能被点名**（本台账只覆盖 headless 数值验收）。

---

## 六、1.1.45 —— 索敌 opt-in「看得见就能打」

**症状**：目标只要比射手高一格以上（柱顶 / 塔上 / 城墙边），射手**45 秒一箭不放** —— 不举弓、不移动、
不索敌，看起来像 AI 卡死。
**根因**：`PreyTargetGoal`（`MobAiEnhanced` 给所有 `Monster` 的全局挂载）只在 `PreyJudge.canPathTo`
成立（高度容差 1 格）时认这个猎物；够不着的猎物让它空转**占住 TARGET 标志** ⇒ 排在 p3 的玩家 /
铁傀儡目标永远起不来。远程怪本来就不需要走过去 —— 有视线就该开火。

| 项 | 落地 |
|---|---|
| 接口 | 新增 `entity/ai/SightFiring`：`double sightFiringRange()`，**≤0 = 不启用**（实体自己 opt-in） |
| 判序 | `PreyJudge.usable` = `inRange` → 贴脸(3 格) → **`sightFiring`** → `reachable`；`sightFiring()` = `mob instanceof SightFiring` && range>0 && dist²≤range² && `hasLineOfSight` |
| 射手 | `MarksmanSkeleton implements EliteMob, GeoEntity, SightFiring`；`sightFiringRange()` 取三件武器射程的最大值 `GIANT_ARROW_MAX_RANGE=32`（另有 `LOCK_MAX_RANGE=26` / `BOW_RANGE=24`），三处武器入参**全部改用同一批常量** |
| 不动的 | `EliteMob.hasTargetInRange`（技能起手本来就要求视线）、所有近战怪、**所有资产**（geo / anim / png / 数据包 / 伤害类型**零改动**） |
| 闸门 | `check_marksman.py` c6 钉四条不变量：实现接口 / 接口存在 / 判序带 `instanceof` 守卫 / 射程同源。负向双向验证：抠守卫、颠倒 `reachable` 与 `sightFiring` 判序都必红 |
| 实测 | 柱高 3 格、柱顶无甲铁傀儡：修前 **45 秒一箭不放** → 修后 **1.8 秒**射出骨矢；`tools/rcon_marksman_test.py` **5/5 PASS** |
| 出货 | `tools/_deploy_145.py`：变化集合恰好 **5 改 / 1 增 / 0 删**，且**资产零漂移**是脚本里的硬断言（不是口头承诺） |

**为什么射程必须同源**：`sightFiringRange()` 报小了**退回死锁**、报大了会**锁上打不到的目标** ——
两种情况都是**静默**的（不报错、日志无痕），只能靠 c6 盯住这批常量与武器入参同源。
