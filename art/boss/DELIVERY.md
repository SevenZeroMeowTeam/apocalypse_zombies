# 尸潮之主（三阶段 Boss）· 交付台账

**日期**：2026-09-30　**版本**：`1.1.41`（**已部署** 08:20）　**md5**：`2ab31881da9ce8344262be00bba4dc21`（2,045,270 B）　**旧版**：`1.1.40`（md5 `6f03e60e…`）已备份出 mods/

**用户逐字请求**：
> 新增boss血量为2500点分3阶段，每阶段不同技能，使用blockbench-mcp连接blockbench新建boss模型，攻击动画（包括远程，近战，召唤等），技能动画，尸潮由原来的4波提升到5波，调用blockbench开头的所用技能

**范围**：新实体 + 新模型/贴图/动画 + 尸潮波数与领场逻辑。**不动**任何既有枪械/精英的几何、贴图与冻结数值。

---

## 一、需求落点

| # | 需求 | 落地 |
|---|------|------|
| ① | 血量 **2500** | `HordeOverlord.BOSS_MAX_HEALTH = 2500.0F`；`ModEntities` 属性表 `MAX_HEALTH 2500` + **`ARMOR 5`（防御 5）** / `ARMOR_TOUGHNESS 8` / `KNOCKBACK_RESISTANCE 0.8` / **`ATTACK_DAMAGE 15`（攻击 15）** / `MOVEMENT_SPEED 0.21`（比普通僵尸 0.23 慢 —— 2500 血的怪不能追着人跑，否则没有"拉开距离打工"这个解法） |
| ② | **分 3 阶段** | 阈值 `PHASE2_HP = 1666`（2/3）、`PHASE3_HP = 833`（1/3）；`PHASE_COUNT = 3`。每跨一段当场放一个**入场技**：Phase 2 入场 = 踏地冲击波，Phase 3 入场 = 血怒。另有一条亡语：Phase 3 里跌破 15%（375）触发「垂死崩解」 |
| ③ | **每阶段不同技能** | 轮转表按阶段换：Phase 1 = 巨斧横扫 + 骨刺齐射（2 招）；Phase 2 = +踏地冲击波 + 召唤尸群（4 招）；Phase 3 = 5 招 + 亡语（近战/远程/召唤/控场/变身全覆盖） |
| ④ | **远程 / 近战 / 召唤** 攻击动画 | 近战 = `attack_melee`（巨斧横扫，±60°/5 格扇面，伤害 15 与基础攻击同口径）；远程 = `attack_ranged`（骨刺齐射 5 根，复用 `GiantArrow`）；召唤 = `summon`（尸笼狂转 + 拍地召 **5 只**僵尸，场上上限 12） |
| ⑤ | **技能动画** | `skill_quake`（7 格冲击波 + 上抛 + 缓慢）、`skill_rage`（给自己力量/迅捷/抗性/抗火各 12000 tick）、`skill_death`（8 格重击 + 凋零 + 再召 5 只 + 清自身负面） |
| ⑥ | **blockbench-mcp 建模型** | Blockbench 5.2.1 + MCP 插件 1.8.1：`create_project(geckolib_model)` → `risky_eval` 灌入**已发布**的 geo/animation/贴图（`tools/boss_bb_load.js`）→ 复核（下节） |
| ⑦ | **尸潮 4 → 5 波** | `Config.horde_waves` 默认 `4 → 5`；`HordeManager.totalWaves` 默认值同步；注释 "Four-wave" → "Five-wave" |
| ⑧ | **只有第 5 波刷新** | 唯一自动来源 = `HordeManager.spawnOverlord`（最后一波领场，`horde_boss_on_final_wave` 可关）；**自然刷怪表（`EliteSpawnBiomeModifier` / `ModSpawns`）里没有它**、`data/` 下 0 处引用、无 `SpawnPlacements` / `addSpawn` 挂载。Boss **计入本波存活人数**（`LIVING.add`）—— 清不掉它这一波就不结算 |
| ⑨ | **设计数值三件套** | 常量集中在 `HordeOverlord`：`ARMOR_POINTS = 5.0D`（防御 5）、`ATTACK_POWER = 15.0F`（攻击 15，横扫 `SWEEP_DAMAGE` 也引它，避免两套"攻击力"打架）、`SUMMON_COUNT = 5`（一次召 5 只，召唤技与亡语共用）。属性表**直接引用常量**，不写字面量 |

---

## 二、美术规格（`tools/boss_v1.py` = 唯一真相源）

| 项 | 值 |
|---|---|
| 坐标铁律 | 16u = 1 格；上 = +Y；正面 = −Z；+X = 模型自身右侧；原点 = 两脚间地面 |
| 体格 | **3.04 格**高（普通僵尸 1.95）／45 根骨骼／129 体块／774 个面 |
| 曲面 | 躯干/四肢/颅骨全部用**八角环**拼圆润柱体（`oct_ring`），不手工堆方块 |
| 贴图 | **512×512**，逐面 UV 图集；躯干 **2.00 px/u**（`DEFAULT_TPU=6` / `TPU_DIV=3`）、脸与前切角 **4 px/u**（`FACE_TPU=12`）；图集占用 8.52%（22323 texels） |
| 动画 | 8 段：`idle` 3.0s(loop) / `walk` 1.6s(loop) / `attack_melee` 1.1s / `attack_ranged` 1.3s / `summon` 1.8s / `skill_quake` 1.4s / `skill_rage` 2.0s / `skill_death` 1.6s；共 162 个关键帧，**rotation 151 / position 11 / scale 0** |
| 驱动骨骼 | 30 根（动画只用骨骼，**没有任何整体缩放通道**） |

**结构**：三段躯干环 → 脖颈/颅骨（含可开合下颚、骨冠、双角）→ 双肩肩甲 + 两段手臂链 + 三指爪 → 背后尸笼（两条转箍 + 魂火）→ 三段披风链 + 左右翼 → 双腿骨链 → 右手巨斧（挂在 `hand_r` 下，挥砍是真实骨骼变换）。

**贴图**（`tools/boss_v1_skin.py`，纯标准库手写 PNG，可重复）：33 个画家函数 —— 腐肉 6（front/back/side/hand/leg/muscle）、骨架 10（颅顶/颞/枕/颅脊/骨冠/角/爪/牙/颌/脸）、锈铁 13（胸甲/背甲/肩甲/腰甲/甲脊/甲刺/钩环/笼条/魂火/斧柄/斧头/斧刃/斧背刺）、布与靴 3（披风/披风下摆/战靴）+ 2 个共享图元（`@lining` / `@cloth_dark`）。

---

## 三、Blockbench 复核（MCP，同一份发布数据反向灌入）

`tools/boss_bb_load.js` 把 **src 里那两份 JSON**（不是在生成器内存里的中间态）灌进 Blockbench 再读回来：

| 断言 | 结果 |
|---|---|
| 骨骼数 / 体块数 | **45 / 129**（与生成器一致） |
| 骨骼树 | `root → move → hip → spine → chest → neck → head`；`head → jaw / crown / horn_l→horn_l2 / horn_r→horn_r2`；`chest → shoulder_* → pauldron_*/arm_* → forearm_* → hand_* → claw_*1..3 / axe`；`chest → back_cage → cage_band1/2 + cage_soul`；`chest → cape → cape2 → cape3 / cape_wl / cape_wr`；`hip → leg_* → shin_* → foot_*` |
| 动画 | 8 段全部挂上，名字/时长/循环标志与发布一致 |
| 关键帧 | 162 个；**scale 通道 0** |
| 动画目标骨骼是否存在 | `missingBones = []`（每段剪辑驱动的骨骼名都能在模型里找到 —— 这一条是"动画不动"这类静默故障的唯一拦网） |
| 贴图 | `horde_overlord.png` 512×512，`file:///F:/mcmod/src/main/resources/...` 加载成功（`img.naturalWidth = 512`，`tex.canvas` 512²） |
| UV 尺寸 / 视界 | `texture_width/height = 512`，`visible_bounds 3.0 × 4.5` |

---

## 四、门禁

1. `python tools/boss_v1.py` —— **自校验 374/374 全过**（几何包围盒/密度分档/UV 无越界无重叠/骨骼树/剪辑首尾归零/无 scale/Java 常量与剪辑名回读一致/`EliteAbility` 时长与命中点对齐）
2. `python tools/boss_v1_skin.py` —— 458 个作画矩形 + 316 个共享图元；**基础层兜底补 0 px**（有画家漏画会当场报数）；连跑三次 sha256 不变；`art == src`
3. `python tools/check_boss.py` —— 十三类接线断言（阶段阈值自洽 / **设计数值 防御 5·攻击 15·召唤 5 且属性表真的引用常量** / 枚举追加在末尾 / GeckoLib 控制器齐备 / 无 scale / geo UV 全名键 / 贴图尺寸与 geo 声明一致 / 三个资源路径真的存在 / 实体+属性+渲染器+刷怪蛋注册 / **五波**与最后一波领场 + 计入本波人数 + 只召一次 / **只从第 5 波来的负向断言**（自然刷怪表·`SpawnPlacements`·`addSpawn`·`data/` 全 0 处，且任何新文件误引 `OVERLORD` 会当场炸）/ 中英双语关键条目）
4. `gradlew build` —— **BUILD SUCCESSFUL**
5. `tools/model_preview.py`（项目自带软渲染）出三视图，确认贴图绑定与形体（骨白颅骨 + 魂火眼 + 铁肩甲 + 腐肉躯干 + 铁靴，无白块/无错位）

---

## 五、改动的文件

**新增**
- `src/main/java/com/apocalypse/zombies/entity/HordeOverlord.java` —— 实体：三阶段状态机 + 6 套技能结算 + Boss 血条 + 阶段标题
- `src/main/java/com/apocalypse/zombies/client/model/OverlordGeoModel.java` / `client/renderer/OverlordGeoRenderer.java`
- `tools/boss_v1.py`（几何/骨骼/动画/图集清单 = 唯一真相源）、`tools/boss_v1_skin.py`（贴图）、`tools/check_boss.py`（接线校验）、`tools/boss_bb_load.js`（Blockbench 复灌）
- 资产：`assets/apocalypse_zombies/geo/horde_overlord.geo.json`、`animations/horde_overlord.animation.json`、`textures/entity/horde_overlord.png`
- 台账：`art/boss/{horde_overlord.geo.json,horde_overlord.animation.json,boss_atlas.json,horde_overlord.png}`

**改动**
- `entity/EliteAbility.java` —— **追加** 6 条枚举（Boss 技能组，严格在 `VEIL_CHOP` 之后：byId 用 ordinal 联网同步）
- `registry/ModEntities.java`（+`OVERLORD` 实体、+.sized(1.6,3.1)、+属性表）、`registry/ModItems.java`（+刷怪蛋 +创造标签）
- `client/ClientModBusEvents.java`（+渲染器注册）
- `horde/HordeManager.java`（+`spawnOverlord`、最后一波领场、`bossSpawned` 门、计入 `LIVING`）
- `Config.java`（`horde_waves` 4→5、+`horde_boss_on_final_wave`）
- `lang/zh_cn.json` / `lang/en_us.json`（实体名/刷怪蛋/Boss 血条/阶段标题/降临提示）

---

## 六、未做 / 风险

1. **未在游戏里实测**：本机只能到"编译 + 静态校验 + 软渲染"这三层。实机验证清单见下（下一步）。
2. **Boss 唯一的自动来源就是第 5 波**：`EliteSpawnBiomeModifier` / `ModSpawns` 的自然刷怪表里没有它，`data/` 0 处引用，没有 `SpawnPlacements` 挂载 —— 这条有负向断言兜着（`check_boss.py` 9b）。**刷怪蛋保留在创造标签里**：它是手动物品、不是「刷新」，留着是为了验收三阶段技能；要连它一起收掉就说一声，`ModItems` 里去掉注册 + 创造标签两行即可。
3. **`summon` 一次 5 只、场上留存上限 12 只**：5 是设计给定值（`SUMMON_COUNT`）；12 不是平衡数值，是防"召到自己卡帧 / 被自家小弟埋掉"的围栏（`SUMMON_CAP`）。要连上限一起压到 5 就说一声。
4. **姿态预览工具不通用**：`tools/model_preview.py` 的 `--pose` 模式吃的是 **Blockbench 导出格式**（`{"post": {"vector": [...]}}`），本项目的剪辑走 **GeckoLib 原生数组格式**（`"0.5": [x,y,z]`），所以软渲染只能看静置姿态。要看挥斧那一帧得用 Blockbench（本次已确认 Blockbench 里 8 段全部可播）或 `bride_pose_probe.py` 那类探针。
5. **血怒增益时长 12000 tick（10 分钟）**：按"这一场战斗内不退"取的，不是无穷 —— 玩家拖过 10 分钟增益会掉。

---

## 七、出货记录（1.1.41）

- **流程**：`python tools/_deploy_141.py` —— 版本钉死（OLD=1.1.40 / NEW=1.1.41，基线 md5 `6f03e60e…`），
  自升 `gradle.properties` 的 `mod_version` → 构建 → 七道门禁 → 备份旧版 → 部署。
- **相对 1.1.40 的逐条字节比对**：改 10 / 增 8 / 删 0，集合与脚本里写死的预期**完全相等**；
  老模型/贴图/动画零漂移（`ASSET_DIRS` 反向断言）。
- **资产三向对账**（art 台账 == src 发布件 == jar 内条目）：`geo ee328f54` / `anim dc901420` / `png 88727cf8`。
- **门禁**：`check_boss.py` PASS · `check_uzi_anim.py` PASS · `check_uzi_art.py` PASS · `check_gun_resources.py` PASS。
- **常量回读**（javap 打在编译产物上，不是看源码）：2500f / 0.21d / 攻击 15.0d / 防御 5.0d / 韧性 8.0d / 横扫 15.0f 在，
  旧值 16.0f **不在**；`castRaiseHorde` 两个调用点前置均为 `iconst_5`（召唤技 + 亡语），`iconst_4` 0 处。
- **部署**：`mods/` 现只有 `apocalypse_zombies-1.1.41.jar`（md5 `2ab31881…`，2,045,270 B，08-30 08:20）；
  旧 `1.1.40` 备份到 **`…/versions/1.20.1-Forge_47.4.23-2/mods_backup/`**（md5 `6f03e60e…`，与出货件逐个字节一致）
  并从 `mods/` 移除（09-30 08:20，不是 08-30）；备份保留最近 3 份、更早的自动删。其余 24 个模组 md5 全等（未被误动）。
- **门禁抓到的真缺陷**：`check_gun_resources.py` 挡下「刷怪蛋没有 `models/item/horde_overlord_spawn_egg.json`」——
  缺这个文件物品栏里就是个紫黑块。已按既有六个蛋的写法补上（`parent: minecraft:item/template_spawn_egg`），
  这才是 jar 从 7 个新增条目变成 8 个的原因。
- **备份放 `mods/` 同级、不放 `mods/xxx_backup/`**：Forge 扫 mods 会往下走子目录，
  旧 jar 留在 mods 的子目录里有被当成重复模组加载的风险。
- ⚠ **Forge 无热重载**：改完必须完全退出重开客户端，退回主菜单不算。
- **未做**：git 提交 / 推 GitHub（CI 会在 main 上发 `v1.1.41`）；`build/libs/` 里还躺着被本次构建覆盖过的
  同名 `1.1.40` 与更老的 `1.1.10` 包，容易再次踩「同名不同内容」的坑，要清就说一声。

---

## 八、事故与修复（1.1.42）：全屏文字变方框

**现象**：用户启动 1.1.41 后游戏里**所有文字变成方框**（missing glyph）。

**根因**：`horde_overlord.animation.json` 的 138 条通道全是 **per-axis 嵌套**写法 ——
生成器 `Clip.to_json()` 把内部按轴存的结构原样 dump 成
`"rotation": {"x": {"0.0": 0.0, "0.375": 1.6, ...}}`，而 GeckoLib 的
`BakedAnimationsAdapter.addBedrockKeyframes` 只认「时间 → 三元向量」。它把 `"x"` 当时间、
把 `{"0.0": ...}` 当值 → `JsonParseException`。而 GeckoLib 是在**资源重载**里解析动画文件的：

```
08:27:01 Caught error loading resourcepacks, removing all selected resourcepacks
  Caused by: GeckoLibException: apocalypse_zombies:animations/horde_overlord.animation.json
  Caused by: JsonParseException: Invalid keyframe data - expected array, found {"0.0":0.0,...}
08:27:47 同样的错误再来一次 → 客户端停在半初始化的资源状态 → 字体没重建 → 全屏方框
```

副作用：客户端把用户选中的资源包从 `options.txt` 里清空了（`resourcePacks:[]`），
连汉化包一起丢。同一次日志里 awm / uzi / crossbow / bride / m1 / 莫辛**全部正常加载**，
只有这一个文件抛异常 —— 缺陷是这个文件独有的，与字体、资源包本身无关（`assets/indexes/5.json`
3598 个对象一个不缺，`unifont.zip` 在位）。

**修法**：`boss_v1.py` 的 `to_json()` 在出口处把 x/y/z 合并成 `{"t": [x,y,z]}`
（各轴按自身键线性取样，线性插值对段中插点不变 → 动作逐帧等价）；裸数组＝ GeckoLib 默认
`EasingType.LINEAR`，正对应本生成器「密集采样正弦」的写法。新增两道闸门：
`check_boss.py` 与 `check_gun_resources.py`（后者罩**所有**动画文件，CI 也跑）。

**验证**：门禁 RED（打在旧文件上：`idle/chest/rotation 时间键非数字 'x'`）→ GREEN（修复后）；
生成器自校验 375/375；**geo 逐字节未变**（`ee328f54`）—— 只动了动画形状；
全家 8 个动画文件 / 1387 条通道形状合规；1.1.42 与 1.1.41 的逐条字节比对 = 改 3（动画 json +
mods.toml + MANIFEST）/ 增 0 / 删 0。

**状态**：1.1.42 构建完成（md5 `6191b89f48f291e65af2b3247798a106`），验证全绿；
部署最后一步被 Windows 文件锁挡住（客户端进程占着 1.1.41 的 jar）—— 完全退出游戏后
重跑 `python tools/_deploy_142.py` 即完成换包 + 把被清空的资源包写回 `options.txt`。
