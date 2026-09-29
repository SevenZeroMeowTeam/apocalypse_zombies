# AI 增强 · 交付台账（1.1.29）

**日期**：2026-09-26　**版本**：`1.1.29`　**md5**：`b58ef46b52c94b34a234f9ddd036459e`　**尺寸**：1,770,091 字节

**用户逐字请求**：
> 添加敌对生物自动锁敌的，增强敌对生物ai，增强村民ai，增强骷髅ai，骷髅有概率，发射超大号箭矢，跟踪敌人，增强铁傀儡ai

**范围**：纯 AI 与一个新弹射物实体 —— **不动几何、贴图、动画**。

---

## 一、六个子项落在哪

| # | 子项 | 落地 |
|---|------|------|
| ① | 敌对生物**自动锁敌** | `entity/ai/SharedAggroGoal`（同类受击 → 半径 16 格内同伴一起锁敌，每 20 tick 抽样）+ `entity/ai/ScentTargetGoal`（`NearestAttackableTargetGoal` 子类，`mustSee=false` ⇒ 隔墙也锁） |
| ② | 增强**敌对生物 AI** | `FOLLOW_RANGE 35→48`；`SurroundGoal` 围猎包抄（8 方位、由实体 id 定方位 ⇒ 队伍自然散开、不抢位）；破门 2.5%→15%（血月 30%）；血月范围 ×1.25、移速 ×1.15（接 `MoonEventManager`） |
| ③ | 增强**村民 AI** | **村民走 Brain 不走 Goal**（1.20.1 实测）：`getBrain().setMemory(WALK_TARGET, ...)` 定向逃离（背向最近敌对生物）+ `setActiveActivityIfPossible(Activity.PANIC)`；同段逻辑把正在打它的怪 `setTarget` 给 16 格内最近铁傀儡 ⇒ **呼叫铁傀儡**（用户选择不做敲钟） |
| ④ | 增强**骷髅 AI** | 拉弓 20→14 tick、散布收窄；走位用现成 `KeepDistanceGoal`（8–16 环带）；**并修掉它一个致命预存缺陷**（见下） |
| ⑤ | 骷髅有概率**发射超大号箭矢 + 跟踪敌人** | 新实体 `entity/GiantArrow`（`extends Arrow`/`AbstractArrow`）+ `entity/ai/GiantArrowGoal`；概率 **8%**（血月 15%）、精英骸骨射手 **20%**；冷却 200 tick；大小 **×2.5**、伤害 **10**、击飞 **3**、限速转向 **≤6°/tick**（用户选的中等档，跑位风骚的玩家躲得掉） |
| ⑥ | 增强**铁傀儡 AI** | `entity/ai/GolemGuardGoal`（附近村民被打 → 立刻转向那只怪，不等慢锁定）+ `FOLLOW_RANGE 48` + `ATTACK_KNOCKBACK`↑ / 攻击冷却↓ / `MOVEMENT_SPEED`↑（加修饰符前 `getModifier(UUID)` 防重） |

新增/改动文件：`event/MobAiEnhanced`（新，事件收口）、`entity/GiantArrow`（新）、`entity/ai/{SharedAggroGoal,ScentTargetGoal,SurroundGoal,SkirmishGoal,GiantArrowGoal,GolemGuardGoal}`（新）、`client/renderer/GiantArrowRenderer`（新）、`registry/ModEntities`（+`GIANT_ARROW`）、`client/ClientModBusEvents`（+渲染器）、`Config`（+`ai_enhance` 分节 **28 开关**）、`entity/KeepDistanceGoal`（**修缺陷**）。

## 二、三个关键实现决定

1. **超大箭继承原版 `Arrow`，不新造弹射物基类** ⇒ 直接复用原版 `DamageSource.arrow`，**不需要注册 `damage_type`**；渲染复用原版箭贴图（`ArrowRenderer` 子类），**不新增美术资产**。
2. **放大渲染必须绕原点缩放后沿视线回退 `(scale−1)×0.675` 格** —— 原版 `ArrowRenderer` 的箭尖画在实体位置**前方 0.675 格**（`translate(-4,0,0)` 后局部 x=−12，×0.05625）。少了这一步，放大后的箭尖会越过命中点、看起来「箭穿过去了但没打中」。
3. **追踪只改速度矢量，绝不手写 rot** —— 原版 `AbstractArrow.tick`（129–130 行）由速度自动导出朝向。

## 三、顺带修掉的两个**预存**缺陷（都不是本轮引入的）

### 1. `KeepDistanceGoal` 永久霸占 MOVE ⇒ 精英骸骨射手的弓是死的

`canUse()` 原来只有 `target != null && target.isAlive()`。Goal 的 MOVE 通道按优先级独占：这条 Goal 挂在**优先级 2**，而 `RangedBowAttackGoal` 在**优先级 4** —— 只要附近有目标，前者就永久占住 MOVE，**弓箭 Goal 一次都拿不到通道，一箭都放不出来**。失效是静默的：编译过、日志干净、表现只是「怪不射箭」。

修法：`canUse`/`canContinueToUse` 改为「**目标有效且自己不在环带里**」（新增 `outOfBand()`，1 格迟滞防边界抖动）⇒ 进环带即交还 MOVE 给攻击 Goal。这条修复正好落在「增强骷髅 AI」范围内。

### 2. `SurroundGoal` 两处写反 ⇒ 围猎等于死代码

- `canUse` 原写成 `distance < engage`（贴身时才跑），而意图是「**还没贴身**就散开包抄」⇒ 反了。
- 类文档把优先级写成「要放在近战之后（数字更大）」⇒ 同样反了：近战 Goal 只要有目标就占 MOVE，挂在其后的 Goal 永远拿不到通道。

修法：`canUse` 改为 `distance > engage && distance <= engage + CHASE_WINDOW`（新增 `CHASE_WINDOW = 12.0`），注册优先级改 **1**（高于僵尸 2 / 蜘蛛 3 的近战 Goal）。另加 `hasRangedIdentity()`：**已有远程攻击 Goal 的怪（弓/三叉戟/药水/持枪/`KeepDistanceGoal`）不挂包抄** —— 它们要拉距离，不是贴身。

## 四、门禁（`tools/_deploy_129.py`，12 道，全过）

1. 版本号先落 `gradle.properties`，脚本自己跑 `gradlew.bat build`（不沿用旧产物）
2. jar 内 `mods.toml == 1.1.29`
3. 新增 9 个 `.class` 全在包里（少一个 = 某子项静默没落地）
4. 新鲜度指纹：`MobAiEnhanced` 含 `apocalypse_ai_range`/`hasRangedIdentity`/`onLivingTick`；`KeepDistanceGoal` 含 `outOfBand`；`GiantArrow` 含 `GiantSeeker`；`GiantArrowRenderer` 含 `TIP_AHEAD`；`SurroundGoal` 含 `CHASE_WINDOW`
5. `tools/check_ai_enhancements.py --selftest` 全绿（8 条静态断言 + **9 条变异测试**）
6. `tools/check_gun_mobs.py` 回归（1.1.24 持枪身份未被本轮覆盖）
7. 部署前探 jar 锁：被占用就报错退出，绝不半路拷坏
8. 旧包改名 `.old.bak`（按 `apocalypse_zombies-` 前缀过滤，**只动自己的包**）
9. 其余 **20 个模组逐个 md5 断「原样在位」**
10. mods 内 `apocalypse_zombies-*` 唯一样本

## 五、**未做 / 风险**

- **未在真实客户端实测** —— 交付基于编译 + 静态校验 + 变异测试，游戏内行为（队列阵型观感、跟踪箭手感、村民逃逸路径）尚未肉眼验证。
- 变异测试本轮抓到校验器**自己两个洞**：① 「Goal 是否接线」最初只查「文件里出现过类名」，把挂载整段删掉也能过 ⇒ 改为必须出现在事件层的 `X.class`；② `@Mod.EventBusSubscriber` 最初是子串匹配，注释掉照样过 ⇒ 改为行首锚定。两条都补成永久断言。

---

# 修订 · 1.1.34 —— 目标死锁（她不会攻击村民 / 铁傀儡 / 玩家）

用户逐字请求：`修复美女僵尸不会攻击村民，铁傀儡，玩家的问题`

出货：`apocalypse_zombies-1.1.34.jar`，md5 `1d73b1764e61942df2f1aade06b737d6`，1,793,505 字节
（`tools/_deploy_134.py` 12 道门禁全过，已部署进实例 mods；1.1.33 改名为 `.old.bak`）

## 一、缺陷（运行时取证，不是读代码猜的）

判据 `tools/bride_aggro_probe.py --scenario perch`：她与铁傀儡同场，另把一只村民放到 5 格高的柱顶（看得见、走不到）。

| | 冻结期（她锁着柱顶村民的那几十秒）铁傀儡掉血 | 拆锁后 |
|---|---|---|
| 修前 | **0.0**（一下都不打） | 有 |
| 修后 | **69.0**，13 次命中 | 31.0（合计 100.0 打死） |

与「她站在村民/铁傀儡旁边一动不动」完全一致。三个回归场景（villager / golem / control）同时通过，对照场景 0.0。

## 二、根因（1.20.1 反编译源码层闭合）

1. 原版 `TargetGoal` 锁定后每 tick 把目标钉回去，而她表里那几条的 `mustSee` / `mustReach` 参数都是 `false` —— **锁上就永不放手**（`mustSee=false` 只关掉「锁定后复检视线」，`mustReach=false` 连可达性都不查）。
2. 该目标占着 TARGET 标志位，把同表里优先级更低的条目全部饿死 ⇒ 技能起手（要视线）与近战（要距离）双双起不来，她就定在原地。
3. 上一版（1.1.29）的 `ScentTargetGoal` 挂在 p0、两个参数同样是 `false`，正是「锁着够不着的东西」的那个源。
4. **第一版修法漏了高度**：只做「走得到吗」的路径判据，而原版 `canReachTarget` 只比 x/z —— 柱顶村民的柱子底部与它 x/z 完全相同 ⇒ 仍判成走得到。埋点 `[AZDBG]` 显示她照旧锁着柱顶村民，这才补上垂直容差。

## 三、修法

- 删 `ScentTargetGoal`；新增 `entity/ai/PreyJudge.java`：「用得上」= 活着 + `canAttack` + 追随距离内 + （**贴脸 3 格** 或 **走得到**）；路径判定补 `Math.abs(dy) <= 1` 高度容差；路径查询 15 tick 节流（贴脸免问，防寻路抖动）。
- 新增 `entity/ai/PreyTargetGoal.java`，挂 **p1**（同伴传仇恨 0 之下、原版玩家 2 之上）：按原版偏好顺序（玩家 → 村民 → 铁傀儡）只在**可用**候选里选；没有可用猎物时**占着 TARGET 但把目标置空**（一放手，原版村民目标就会把够不着的再锁回去）。
- `SharedAggroGoal` 用**同一套**判据复核传给同伴的目标（两边不许各判各的）。
- **特性不许修坏**：原 `ScentTargetGoal` 的意图是「失去视线但走得到时继续追」，必须保住 ⇒ `--scenario hide`（第 8 秒砌墙断视线、两侧留绕行通道）：砌墙前 0.0 / 砌墙后 **20.0**（村民被打死）✓。

## 四、门禁（`tools/_deploy_134.py`，12 道，全过）

1. 版本号先落 `gradle.properties`，脚本自己跑 `gradlew.bat build --offline`（不沿用旧产物）
2. jar 内 `mods.toml == 1.1.34`
3. `PreyJudge` / `PreyTargetGoal` 在包内；**`ScentTargetGoal` 已从包内消失**（死锁源必须消失，不只是不用）
4. 新鲜度指纹：`MobAiEnhanced` 含 `PreyTargetGoal`；`PreyTargetGoal` 含 `anyPrey`/`PreyJudge`；`PreyJudge` 含 `canPathTo`/`usable`；`SharedAggroGoal` 含 `PreyJudge`/`usable` —— **只钉自己的标识符**：原版方法名会被 SRG 重映射掉（第一版钉了 `createPath`，误报）
5. `tools/check_ai_enhancements.py --selftest` 全绿（新增 7 条静态断言 + **5 条变异测试**专钉本轮：判据里出现视线 / 丢掉高度比较 / 调度器排到原版之后 / 去掉空转分支 / 同伴传仇恨不复核）
6. `tools/check_bride_combat.py` 回归（她的技能幅度不受目标层修复影响）
7. 部署前探 jar 锁：占用就报错退出，绝不半路拷坏
8. 旧包改名 `.old.bak`（按前缀过滤，只动自己的包）
9. 其余 **20 个模组逐个 md5 断「原样在位」**
10. mods 内 `apocalypse_zombies-*` 唯一样本

另：临时埋点 `[AZDBG]`（`AbstractEliteZombie.logAiState()`）已删，出货源码重跑验收时服务端日志里 `AZDBG` 计数 = **0**。

## 五、验证矩阵（在出货源码编译出的服务端上重跑，端口 25566）

| 场景 | 判据 | 结果 |
|---|---|---|
| `perch` | 锁着够不着的村民期间仍要打得到铁傀儡 | 冻结期 69.0 / 21 次命中 / 打死 ✓ |
| `hide` | 失去视线但走得到 ⇒ 继续追 | 砌墙后 20.0 / 打死 ✓ |
| `villager` | 会攻击村民 | 20.0 打死 ✓ |
| `golem` | 会攻击铁傀儡 | 96.0 打死 ✓ |
| `control` | 不召她时受害者不掉血 | 0.0 ✓ |

## 六、**未做 / 风险**

- **玩家那一支没跑真机**（无客户端可连）：判据 `perch`/`hide` 覆盖的是同一套机制（判据与目标类型无关，玩家在她候选表的第一位）。玩家相关的实际手感仍需你在游戏里确认。
- **创造 / 旁观模式的玩家她依旧不打** —— 判据里保留了原版 `canAttack` 语义（那只针对「打不动」的目标，不是本轮缺陷）。
- 路径判定是 15 tick 一次 + 贴脸免问：极端寻路抖动下仍可能选错目标，但最坏后果是「暂时换一个能打的目标」，不再是整张表死锁。
- 死锁取证依赖 dev 服务端（25566 / RCON 25575）。25565 是你客户端的局域网世界，全程未触碰。
