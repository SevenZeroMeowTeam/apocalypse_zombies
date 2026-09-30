# 骸骨射手（精英骷髅 GeckoLib 真骨骼 + 骨矢锁定）· 交付台账

**日期**：2026-09-30　**当前版本**：`1.1.44`（**已部署** 12:42:24，md5 `39b7db93d4d054bb5e2d06276634c165`，2,064,366 B）
**发布件**：GitHub Release [`v1.1.44`](https://github.com/SevenZeroMeowTeam/apocalypse_zombies/releases/tag/v1.1.44)
→ 资产 `apocalypse_zombies-1.1.44-clean.jar`（1,400,156 B；tag 指向 `e9089fc`，CI run 36670289371 绿）
**历史版本**：`1.1.43`（`80be27db080ffeff62cfe57a865200e2`）在 `mods_backup/`，同目录还有 `1.1.42` / `1.1.41`

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
| 出货脚本 | `tools/_deploy_144.py`（钉死 1.1.43 基线 md5 + 变更集合） |

* **Forge 无热重载**：换包后必须**完全退出**重开客户端（退到主菜单不算）。
* **发布件 `.jar` 是 clean 构建**（不含 TaCZ 借用资产），已核验其中 **0 处**网易字样。
* **未决（等用户拍板）**：射手沿用共享猎物调度器，判据是「**走得到**」——对**看得见但走不到**
  的目标（玩家站柱顶 / 塔上 / 飞行）**不会开火**。要不要给它放宽成「有视线即可开火」，
  尚未决定；本次按既有行为交付，未改。
* **待用户实测**：模型 / 动画 / 粒子在客户端的观感（本台账只覆盖到 headless 数值验收）。
