# 骸骨射手（MarksmanSkeleton）· GeckoLib 骨骼化设计

> 目标：把现有精英骷髅 `MarksmanSkeleton` 从原版 `SkeletonModel` 换成 **GeckoLib 真骨骼模型**，
> 并挂上新技能「**骨矢锁定**」—— 100% 自瞄必中、**无视无敌帧**，伤害 = 目标最大血量 × 25%（Config 可调）。
>
> 本文件是**两条工作线的接口契约**：几何/动画（Blockbench 生成器）与 Java（实体/技能/渲染）。
> 任何一方的规格改动都必须同步这里，再由 `tools/check_marksman.py` 双向核对。
>
> **几何/动画的实际落地产物链**（武器线同款：JS 在 Blockbench 里跑，Python 负责组装与落盘）：
> | 脚本 | 作用 |
> |---|---|
> | `tools/marksman_bb_gen.js` + `tools/marksman_bb_gen.py` | 建 27 骨 / 33 体块、逐面 UV 货架打包（密度自适应）、画 128×128 贴图 → geo.json + png 落 art 与 src |
> | `tools/marksman_bb_anim.js` + `tools/marksman_anim.py` | 建 4 段 clip、dump 关键帧 → 转 bedrock 1.8.0 animation.json 落 art 与 src |
> | `tools/marksman_pose_shot.py` | 把某 clip 某时刻的关键帧直接写进骨骼再抓图，用来目检姿态与旋转方向 |
>
> 三个不能踩的坑（都实测踩过）：`new Cube()` 之后**必须**调 `c.init()`，否则体块不进
> `Project.elements`、视口不渲染（全白截图）；贴图**不能**用 `Texture.fromPath`（异步，画布会停在
> 16×16，整张图画在 16×16 上），要用 `new Texture({width, height, internal:true})` 再强制改
> `TEX.canvas.width/height`；Blockbench 只在 Animate 模式应用姿态，且后台窗口的播放循环不跑，
> 所以姿态目检靠"把关键帧值写进 `Group.rotation`"，别指望 `Timeline.setTime`。

## 〇、铁律（项目既有规范，逐条适用）

| 规则 | 值 |
|---|---|
| 单位 | `16u = 1 Block`，`1u = 1px` |
| 朝向 | 面朝 **-Z**；`+X` = 模型自身**右侧**；`+Y` = 上 |
| 原点 | 脚底 `Y = 0`（root pivot = 0,0,0） |
| rest 姿态 | 所有骨骼旋转 **全零**（动画之外不允许有静态旋转补正） |
| 动画 | **只允许 rotation / position 通道，禁止任何 scale 通道**（含 molang 缩放） |
| 贴图 | **128×128**，逐面 UV 图集（不允许重叠、不允许拉伸） |
| 命名 | 骨骼小写下划线；Java 里的 clip 名以 `ANIM_*` 常量与之双向同步 |

## 一、体型与碰撞箱（不变）

模型总高 **32u = 2.0 Block**（脚底 0 → 颅顶 32），与原版骷髅同级 ——
**因此 `ModEntities` 的 `sized()` 与属性一律不动**，不产生任何命中箱漂移。

| 部位 | Y 区间 (u) | 宽 × 深 (u) |
|---|---|---|
| 脚 | 0 → 1.5 | 2.6 × 4.2 |
| 小腿 | 1.5 → 7.5 | 2.6 × 2.4 |
| 大腿 | 7.5 → 13.5 | 3.0 × 3.0 |
| 骨盆 | 13.5 → 17.0 | 7.0 × 4.0 |
| 腰椎 | 17.0 → 20.0 | 7.0 × 3.6 |
| 胸腔 | 20.0 → 25.0 | 9.0 × 4.4 |
| 颈 | 24.5 → 26.5 | 2.0 × 2.0 |
| 头骨 | 24.0 → 32.0 | 8.0 × 8.0 |
| 上臂 / 前臂 / 手 | 手底 10.0 | 2.5 / 2.3 / 2.1 |

## 二、骨架树（27 骨，rest 全零旋转）

```
root                                     pivot (0, 0, 0)      ← 脚底地面
└── move                                 pivot (0, 0, 0)      ← 整体位移/受击晃动专用
    ├── hip                              pivot (0, 13.5, 0)
    │   ├── leg_r                        pivot (2.1, 13.5, 0)
    │   │   └── shin_r                   pivot (2.1, 7.5, 0)
    │   │       └── foot_r               pivot (2.1, 1.5, 0)
    │   └── leg_l                        pivot (-2.1, 13.5, 0)
    │       └── shin_l                   pivot (-2.1, 7.5, 0)
    │           └── foot_l               pivot (-2.1, 1.5, 0)
    └── spine                            pivot (0, 17.0, 0)
        └── chest                        pivot (0, 20.0, 0)
            ├── neck                     pivot (0, 24.5, 0)
            │   └── head                 pivot (0, 24.0, 0)
            │       └── jaw              pivot (0, 27.0, -2.0)   ← 技能时张口
            ├── cape_a                   pivot (0, 23.0, 2.6)    ┐
            │   └── cape_b               pivot (0, 17.0, 3.2)    │ 三段斗篷链，
            │       └── cape_c           pivot (0, 11.0, 3.6)    ┘ 滞后摆动是骨骼驱动
            ├── quiver                   pivot (3.0, 23.0, 3.0)   ← 箭袋 + 3 支箭
            ├── shoulder_r               pivot (4.6, 23.5, 0)
            │   └── arm_r                pivot (4.6, 23.5, 0)
            │       └── forearm_r        pivot (4.6, 18.0, 0)
            │           └── hand_r       pivot (4.6, 12.5, 0)
            └── shoulder_l               pivot (-4.6, 23.5, 0)
                └── arm_l                pivot (-4.6, 23.5, 0)
                    └── forearm_l        pivot (-4.6, 18.0, 0)
                        └── hand_l       pivot (-4.6, 12.5, 0)
                            └── bow      pivot (-6.3, 11.0, -3.0)  ← 骨弓，握在左手
```

**为什么是这套**：四肢/躯干/披风全部两段以上成链 —— 摆姿是真骨骼变换，不是整体旋转；
`root → move` 保留一层，给受击/施法的整体位移留通道而不污染腿部动画。

## 三、体块表（31 块，单位 u；左手/左腿为 X 镜像）

| 骨骼 | 体块 | from (x,y,z) | to (x,y,z) | 备注 |
|---|---|---|---|---|
| leg_r | thigh_r | 0.6, 7.5, -1.5 | 3.6, 13.5, 1.5 | 大腿骨，中空感靠贴图 |
| shin_r | shin_r | 0.8, 1.5, -1.2 | 3.4, 7.5, 1.2 | |
| foot_r | foot_r | 0.8, 0.0, -3.0 | 3.4, 1.5, 1.2 | 前伸的骨足 |
| hip | pelvis | -3.5, 13.5, -2.0 | 3.5, 17.0, 2.0 | |
| spine | lumbar | -3.5, 17.0, -1.8 | 3.5, 20.0, 1.8 | |
| chest | ribcage | -4.5, 20.0, -2.2 | 4.5, 25.0, 2.2 | |
| chest | rib_l / rib_r | ∓4.7, 20.5, -2.0 | ∓4.2, 24.5, 2.0 | 两层肋骨薄板 |
| neck | neck | -1.0, 24.5, -1.0 | 1.0, 26.5, 1.0 | 被头颅下端遮住 |
| head | skull | -4.0, 24.0, -4.0 | 4.0, 32.0, 4.0 | 颅顶 32u = 模型最高点 |
| jaw | jaw | -3.2, 24.5, -4.6 | 3.2, 27.0, -2.0 | |
| cape_a | cape_a | -4.6, 17.5, 2.2 | 4.6, 23.5, 3.2 | 三段共 1u 厚（薄板，走 cutoutNoCull） |
| cape_b | cape_b | -4.0, 11.5, 2.8 | 4.0, 17.7, 3.8 | |
| cape_c | cape_c | -3.2, 5.5, 3.2 | 3.2, 11.7, 4.2 | 下摆最窄 |
| quiver | quiver_box | 1.4, 16.0, 3.0 | 4.6, 23.0, 6.0 | 斜挎背后 |
| quiver | arrow_1..3 | — | — | 3 支箭杆，露出袋口 4u |
| arm_r | upper_arm_r | 4.6, 18.0, -1.25 | 7.1, 23.5, 1.25 | |
| forearm_r | forearm_r | 4.7, 12.5, -1.1 | 7.0, 18.0, 1.1 | |
| hand_r | hand_r | 4.8, 10.0, -1.2 | 6.9, 12.5, 1.2 | |
| arm_l | upper_arm_l | -7.1, 18.0, -1.25 | -4.6, 23.5, 1.25 | 镜像 |
| forearm_l | forearm_l | -7.0, 12.5, -1.1 | -4.7, 18.0, 1.1 | |
| hand_l | hand_l | -6.9, 10.0, -1.2 | -4.8, 12.5, 1.2 | |
| bow | bow_grip | -6.9, 7.5, -3.9 | -5.7, 14.5, -2.7 | 握点，位于手前 -Z |
| bow | bow_limb_top | -6.7, 14.5, -4.4 | -5.9, 19.0, -2.2 | rx +22°，弓臂上弯 |
| bow | bow_limb_bot | -6.7, 3.0, -4.4 | -5.9, 7.5, -2.2 | rx -22°，弓臂下弯 |
| bow | bow_string | -6.5, 4.5, -2.4 | -6.1, 16.5, -2.0 | 弦，1u 内偏 |

（`shoulder_l/r` 无体块，仅作旋转枢纽 —— 与原版 `PlayerModel` 的肩枢轴同思路。）

## 四、贴图（128×128，逐面 UV 图集）

- 货架式打包器自动排布，**密度自适应**：从 2.0 px/u 起逐档下探，取"放得下"的最高档，
  保证 128×128 内无重叠、无拉伸；每一档都写进台账。
- 面部（`skull` 的 north 面）单独提档到 3 px/u —— 眼窝/牙要认得出。
- 配色：骨 `#d8d2bd`/暗面 `#a89f86`；眼窝浊黄 `#d6c46a`；破布斗篷 `#4a4438`；
  箭袋皮革 `#5b4632`；弓骨 `#cfc7ae`，弓弦 `#8d8878`；肋骨内侧 `#6d6455`。

## 五、动画（4 段，全部 rotation/position；禁止 scale）

| clip | 时长 | 循环 | 用途 / 关键帧 |
|---|---|---|---|
| `idle` | 3.0s | ✓ | 呼吸：`chest` rx ±1.6°、`spine` ±0.6°、`head` ry ±4°、`cape_b/c` ±2°、`bow` rx ±2° |
| `walk` | 1.0s | ✓ | `leg_*` rx ±30° 交替、`shin_*` 反向屈、`arm_*` 反相 ±25°、`cape_*` 滞后、`chest` ry ±3° |
| `shoot` | 0.9s | ✗ | 普通弓射：0s 抬弓 → 0.25s 拉弦（`forearm_r` rx -35°）→ 0.6s 释放 → 0.9s 回位 |
| `skill_bone_lock` | 2.1s | ✗ | **技能「骨矢锁定」**：0→1.7s 前摇（弓举过头顶 `arm_l` rx -110°、`forearm_r` 满弦、`jaw` 张开、`head` 锁定目标）→ **1.7s 命中**（`EliteAbility.BONE_LOCK` 的 impactTick=34）→ 1.7→2.1s 收招 |

关键帧时间点一律落在 `EliteAbility` 的三段切分上（前摇 / 命中 / 收招），
Java 侧只按 `getAbilityTick()` 推进，不额外同步动画时间。

## 六、Java 侧接口（与上表双向同步）

| 位置 | 内容 |
|---|---|
| `MarksmanSkeleton` | `implements EliteMob, GeoEntity`；`ANIM_IDLE/WALK/SHOOT/LOCK` 常量；`registerControllers` 挂 `movement` + `cast` 两条控制器 |
| `EliteAbility` | **末尾追加** `BONE_LOCK(42, 34)`（`byId` 走 ordinal，插中间会让所有精英施法状态错位）；`SNIPE` 保留但不再被引用 |
| 技能 | `MarksmanHooks.ability() → BONE_LOCK`；`onImpact() → fireBoneLock()` |
| 弹体 | `BoneLockArrow extends GiantArrow`：继承追踪物理（`turnDegrees` 每 tick 修向 + 目标速度前导），命中即 `apocalypse_zombies:bone_lock` 伤害 = `目标最大血量 × AI_MARKSMAN_LOCK_RATIO`，随后 `discard()`（不穿透） |
| 伤害标签 | `damage_type/bone_lock.json`；标签文件：`bypasses_armor` + `bypasses_resistance` + `bypasses_enchantments` + `bypasses_shield`（盾牌格挡也绕开）+ `bypasses_invulnerability`（**管的是实体 `Invulnerable` 标志**）；**不挂** `is_projectile`。注意 1.20.1 **没有** `bypasses_cooldown`（那是 1.20.5+），名字写错 = 整个标签被静默丢弃，`check_marksman.py` 的 c4 直接开原版数据包核对 |
| **无视无敌帧** | 标签做不到（实测）：1.20.1 `hurt()` 在 `invulnerableTime > 10` 时只结算「本次 − 上次」的差额，该分支无标签可跳过。`BoneLockArrow.onHitEntity` 命中时先 `target.invulnerableTime = 0;` 再 `hurt(...)`；`check_marksman.py` 的 c5 钉住这一行（判序，剥注释后比 `hurt(` 的先后） |
| 粒子 | 前摇每 4 tick：眼眶 + 弓身 `SOUL_FIRE_FLAME`；释放瞬间：`SOUL` + `DAMAGE_INDICATOR`；弹体每 tick `SOUL_FIRE_FLAME` 尾迹 |
| 渲染 | 新增 `MarksmanGeoModel` / `MarksmanGeoRenderer`（`GeoEntityRenderer`，shadow 0.5）；`ClientModBusEvents` 换绑，删除原版 `MarksmanModel` 的 layer 注册 |
| Config | `AI_MARKSMAN_LOCK_RATIO`(0.25)、`AI_MARKSMAN_LOCK_COOLDOWN`(160)、`AI_MARKSMAN_LOCK_TURN`(60°)、`AI_MARKSMAN_LOCK_SPEED`(1.6)、`AI_MARKSMAN_LOCK_LIFE`(100) |

**决策留档**：用户确认的口径是「目标最大血量的 **25%**，固定值且无视护甲」（20 血 → 5.0 伤害），
与最初口述的 5% 不同 —— 比例做成 Config，改回 0.05 只需改一行配置。

## 七、验收（缺一不可）

1. `tools/check_marksman.py`：骨骼名 ↔ Java `ANIM_*` 常量双向一致；无 scale 通道；
   UV 无重叠超界；脚底 0 / 颅顶 32；rest 旋转全零；弹体伤害公式 = `maxHealth × ratio`。
2. Blockbench 回灌：把**发布的** geo/anim JSON 读回 Blockbench，骨数/体块数/关键帧数与原工程一致。
3. headless 服务端 + RCON（`tools/rcon_marksman_test.py`，4/4 PASS 实测）：
   ① 标签级 —— 满防具（保护 IV 下界合金）+ 抗性 V 的铁傀儡（100 血）打 25 点 `bone_lock` 恰好掉 **25.0**；
   ② 对照组 —— 同样 25 点 `minecraft:generic` 只掉 **0.0**（证明防具真的在减伤，① 的满额不是巧合）；
   ③ 技能自放 —— 目标 10 格外起手并射出 `bone_lock_arrow`；
   ④ 命中 —— 全程用 `minecraft:generic` 每 0.1 秒压制无敌帧（该伤害在满防具下掉 0 血，零噪声），
      骨矢落点仍恰好掉 **25.0**（没做清零就是 24.0）。
4. `clean build --offline` BUILD SUCCESSFUL；`mods/` 部署 1.1.44 后客户端实测动画与粒子。

**验收环境的三个前提（都是实测踩出来的，不满足就会得到「技能放了但不掉血」的假故障）**：
- 斗场必须**围三格高 `barrier` 围墙**：射手带 `KeepDistanceGoal`（7~18 格），没墙会自己走下
  y=100 的悬空台子掉到地面，之后既没视线也没法寻路（早期 3 个 FAIL 全是这么来的）。
- 布置时必须**区域清场**（`kill @e[x=…,y=…,z=…,dx=…,dy=…,dz=…,type=!minecraft:player]`）：
  上一轮测试残留的实体会吃掉弹体 —— 实测被一个残留的 `horde_overlord`（碰撞箱极大且 `Invulnerable`）
  吞掉全部骨矢，日志里 `onHitEntity` 打中的是它而不是靶子。
- 读血量用 `/attribute <e> minecraft:generic.max_health get`：`/data get entity … Attributes`
  的响应会**截断**，正则失配后静默返回 `None`。
