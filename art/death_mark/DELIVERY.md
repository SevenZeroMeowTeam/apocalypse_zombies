# 1.1.30 交付台账 —— 持枪怪近身切近战 / 走位射击 / 死亡标记 / 投掷怪免爆

出货日期：2026-09-26
产物：`apocalypse_zombies-1.1.30.jar`
大小：1,777,008 字节
md5 ：`0c3af3ee540664bf4880fb6d1c2962a4`
部署位置：`C:\Users\Administrator\Desktop\.minecraft\versions\1.20.1-Forge_47.4.23-2\mods\`
（旧包 `1.1.29` 已改名 `.old.bak`；同目录另外 20 个第三方模组 md5 未变）

## 用户原话

1. `持枪僵尸，敌人靠近时自动切近战攻击，可以移动不是原地不动，添加死亡标记技能`
2. `投掷僵尸免疫爆炸伤害`

## 五项改动

### ① 敌人靠近时自动切近战（`entity/GunAttackGoal.java`）

根因不是「没写近战」，是**近战被饿死**：原版 `MeleeAttackGoal` 与开火 Goal 抢同一个
`Flag.MOVE`，而 `GunAttackGoal.canUse()` 写的是「有目标 + 有枪就为真」⇒ 永久霸占通道，
同一只怪身上的近战 Goal 一次都跑不出来（编译过、日志干净、完全静默）。

改法：目标进入 `guns.melee_handoff_range`（默认 **3.0 格**）内时 `canUse()` 与
`canContinueToUse()` 都返回 false，把 MOVE 交还给近战 Goal；`canContinueToUse` 委托给
`canUse()`，所以「跑着跑着敌人贴上来」也会立刻放手，不只在接管那一刻判一次。

配套：`event/GunArmedMobs.ensureGunGoal` 现在同时保证「近战出口存在」—— 若这只怪身上没有
任何 `MeleeAttackGoal` 子类（`ZombieAttackGoal` 也是它的子类，已从 1.20.1 源码核实），
就补一个 `MeleeAttackGoal(1.0D, false)` 在 2 号位。判定按**类**而不是按优先级，所以
`SoldierZombie`（近战挂在 3 号位）不会被加出第二个近战 Goal。

### ② 可以移动，不是原地不动（同文件）

旧实现射程内直接 `getNavigation().stop()` ⇒ 站桩开枪。现改为**游走射击**：每
`guns.strafe_interval`（默认 30 tick）换一条腿，朝目标侧向偏移 `STRAFE_STEP = 3.0` 格落一步，
`strafeSign` 每次取反 ⇒ 左右交替而不是一直往同一边绕圈。太远仍旧靠近；走位排在开火之前，
**换弹期间照走**（旧代码换弹时会提前 return，又变成雕像）。

为什么不是每 tick 重发移动指令：寻路会反复作废，视觉上是原地抽搐。一条腿只下一次指令。

### ③ 死亡标记（`effect/` + `registry/ModEffects.java` + `event/DeathMarkHandler.java`）

用户的四项定案全部落地：

| 项 | 定案 | 落地 |
| --- | --- | --- |
| 触发 | 命中即标记 | `LivingHurtEvent` 里判 `getDirectEntity()` 是否为子弹 / 箭 / 酸弹，且 `getEntity()` 是 `Monster` |
| 强度 | +20% / 10s / 3 层 | `death_mark_damage_bonus = 0.20`、`death_mark_duration = 200`、`death_mark_max_stacks = 3` |
| 视觉 | 自定义 MobEffect + 18×18 图标 | `textures/mob_effect/death_mark.png`（144 行生成器 `tools/death_mark_icon.py`，纯标准库） |
| 范围 | 全部远程怪 | `BulletProjectile` / `AbstractArrow`（残兵弓、骸骨射手、超大跟踪箭）/ `AcidProjectile` |

关键顺序：**先按已有层数加伤，再加新的一层** —— 于是「第一枪只是标记、第二枪开始才痛」，
层数是打出来的。反过来写会让第一枪就带上它自己刚打出来的加成。
加伤只认 `Monster` 打出的伤害：玩家互殴、摔伤、岩浆不会因为被僵尸打过一次就统统变重。

### ④ 投掷怪免疫爆炸伤害（`entity/SoldierZombie.java`）

残兵按抛物线往目标脚下丢 TNT，自己的手雷就炸在脚边 —— 不做免伤它会被自己炸死，玩家只要站
旁边看戏。走 `isInvulnerableTo` 而不是覆写 `hurt`：这一层在伤害计算之前被
`LivingEntity#hurt` 查过，击退、着火、仇恨一起免掉，也不必判「是不是我丢的那颗」。
`super.isInvulnerableTo(...)` 必须保留（无敌帧、抗火都长在父类）。

## 配置开关（全部可一键关）

```
guns.melee_handoff_range    = 3.0    # 0 = 关掉让位（回到旧的永久占通道）
guns.strafe_enabled         = true
guns.strafe_interval        = 30
guns.blind_handoff_ticks    = 40     # 射程内连续看不到目标多少 tick 后交还通道
specials.death_mark_enabled = true
specials.death_mark_damage_bonus = 0.20
specials.death_mark_max_stacks   = 3
specials.death_mark_duration     = 200
```

## 校验

`tools/check_melee_and_mark.py`：8 组断言 + **15 条变异测试（15/15 全抓）**。
断言覆盖：让位判定真的把距离与配置值拿来比（不是「文件里出现过配置名」）、
`canContinueToUse` 委托、旧的 `KEEP_DISTANCE` 已删净、走位方法真的下移动指令且不自己 `stop()`、
走位排在开火之前、`blindTicks` 在 `stop()` 里清零、效果类/注册表/总线注解/图标尺寸/lang 键、
免爆常量声明与 `super` 保留。

回归：`check_gun_mobs.py`、`check_ai_enhancements.py`、`check_player_health.py` 全过。

## 出货门禁（`tools/_deploy_130.py`，脚本自己跑构建）

入口不变量（`gradle.properties` 必须还是 1.1.29）→ 5 个校验器 → 图标 18×18 →
抬版本号 → `gradlew.bat build` → jar 内部门禁（3 个新类 + 图标尺寸 + `mods.toml` 版本 +
6 条**本模组标识符**指纹）→ 部署（只动 `apocalypse_zombies-` 前缀）→ 部署后断言
（唯一样本 + 另外 20 个模组 md5 未变 + md5 与产物一致）。

### 本轮踩到的坑：指纹不许钉原版名

生产 jar 是 **SRG 重映射**过的：覆写的原版方法名变成 `m_XXXXX_`，原版字段名
（`IS_EXPLOSION`、`DAMAGE_INDICATOR`）在 jar 里根本搜不到。首轮门禁因此报了两条
「这个改动没进 jar」的**假失败**。`javap -p -classpath build/libs/....jar
com.apocalypse.zombies.entity.SoldierZombie` 一看便知：方法在，名字是 `m_6673_`。

对策：凡是要「证明改动进了包」的原版 API 调用，旁边放一个**本模组命名的常量**——
`EXPLOSION_IMMUNITY`（`TagKey<DamageType>`）、`MARK_PARTICLE`（`ParticleOptions`），
门禁钉这两个名字。顺带也是更好的代码：决定只出现在一处。

## 未做 / 未验证

- **未在真实客户端实测**：静态断言 + jar 内证齐全，但「贴脸真的抡爪子」「跑动射击手感」
  「HUD 上那个图标好不好认」「自己丢的 TNT 真的不疼」只能在游戏里看。
- 部署时游戏（javaw）正在运行，jar 未被锁所以覆盖成功，但**必须完全退出游戏再重开**才生效。
- 死亡标记的增伤对**所有怪**的伤害生效（不止标记来源那只），这是「被标上就吃更重的伤害」的
  自然读法；若用户想要「只有打标记那只怪加成」，改 `DeathMarkHandler` 里的一处判定即可。
