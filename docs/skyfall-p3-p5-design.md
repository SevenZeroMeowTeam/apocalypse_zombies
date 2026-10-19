# 《天陨武库》P3–P5 设计

> 前置：`3.9.0` 已交付 P1+P2 最小闭环（终端方块 + 六协议核心 + 六边形面板 + 服务端授权/充能）。
> 本文件只设计 **P3 相位同步与多人演出 → P4 资产原创化 → P5 验收与发布**，不重复 P1/P2 内容。
> 约束沿用：Forge 1.20.1 / Java 17、GeckoLib 4.8.4、只用原版 `RenderType` + 事件相机，
> **不引入 shader / FBO / Mixin**；参考包与参考图只作结构参考，不进 jar。

---

## 0. 现状事实（设计要挂在这些点上）

| 事实 | 位置 | 对设计的影响 |
|---|---|---|
| 打击开始包 **只发给施放者本人** | `OrbitalStrikeManager.schedule()` 末尾 `PacketDistributor.PLAYER` | 广播需要新增收件人集合 |
| 客户端演出完全由**本地开始时间**推 | `OrbitalStrikeClientState.startGameTime` + `elapsed()` | 想要相位同步必须引入「时间偏移」校正 |
| 相位边界目前由客户端从 `lockTicks/fallTicks + 协议 XML` 推 | `OrbitalStrikeClientState`、`OrbitalCinematic`、`StrikeProtocol` | 服务端已经能算出同样的相位（`StrikeProtocol.phaseAt`），缺的是「告诉客户端」 |
| 跳过的键 `K` 已经通用 | `ClientEvents` 第 244–249 行 | 广播旁观者天然可跳过，不用新键 |
| 相机会在 `distanceToPlayer() > 160` 时自动退出 | `OrbitalCinematic` `MAX_DISTANCE = 160` | 广播半径上限就对 160 设计 |
| 打击与终端没有硬链接 | `SkyfallTerminalManager.authorize()` 只调用 `schedule` | 取消/退款需要把 `terminalPos` 传进 `ActiveStrike` |
| 资产 10 张图派生自用户参考图 | `textures/environment/carrier_*.png` 等 | P4 要按资产哈希做「出包」验收 |
| 出货是脚本制、一版一脚本 | `tools/_deploy_<ver>.py`、`docs/wiki/07` | P5 直接照 `_deploy_199.py` 的结构写 |

---

## 1. P3：相位同步 + 多人演出 + 取消路径

### 1.1 目标

1. **相位不再各算各的**：服务端每个相位切换发一次包，客户端用服务端 tick 校正时间轴；
   卡顿/掉帧后画面不会「提前落地」。
2. **过场广播**：施放者附近（默认 160 格）的玩家也能看到同一部电影 + HUD；
   每个客户端可以**自己关掉**别人的过场，只看世界效果。
3. **可取消**：拆终端、管理员命令、关服、维度卸载都能中止未结算的打击，
   且不会留下「半截任务 / 二次伤害 / 卡住的镜头」。
4. **性能上限**：同时存在的打击、每 tick 方块预算可配置，超出时排队而不是一起爆。

### 1.2 网络协议（新增 2 个、扩展 1 个）

```java
// 新增：S2C，相位切换（每个相位一次，整场约 6 个包）
public record StrikePhasePacket(UUID strikeId, byte phase, int serverTick) {}

// 新增：S2C，取消
public record StrikeCancelPacket(UUID strikeId, byte reason) {}
// reason: 0 TERMINAL_BROKEN / 1 ADMIN / 2 CONFIG_OFF / 3 WORLD_UNLOAD

// 扩展：OrbitalStrikePacket 增加三个字段
UUID strikeId;          // 同一次打击的唯一标识（所有后续包都带）
boolean spectator;      // true = 我不是施放者，只是被广播的旁观者
long serverGameTime;    // 服务端发包时的 gameTime（用于首次对齐）
```

- `NetworkHandler.PROTOCOL` 从 `"1"` 升到 `"2"`：新旧客户端不允许混连（宁可连不上，也不要半同步）。
- 所有新字段都只在 `OrbitalStrikePacket` 尾部追加；`TerminalSyncPacket` 不动。

### 1.3 服务端改动（`OrbitalStrikeManager`）

**`ActiveStrike` 增加字段**

| 字段 | 用途 |
|---|---|
| `UUID strikeId` | 本次打击标识（`UUID.randomUUID()`） |
| `@Nullable BlockPos terminalPos` | 授权来源终端；自由开火为 null |
| `StrikePhase lastPhase` | 只在相位变化时发包 |
| `List<UUID> viewers` | 开场时确定的收件人（施放者 + 广播范围内的玩家） |
| `long chargeSeconds` | 取消退款用（记录这次扣了终端多少充能） |

**`schedule` 签名扩展**（旧签名保留，委托新签名）

```java
public static UUID schedule(ServerPlayer player, BlockPos target, OrbitalStrikeMode mode,
                            int radius, float damageMul, float fallMul,
                            @Nullable BlockPos terminalPos)
```

- 开场收件人：`player` + `level.players()` 中 `distanceToSqr(target) <= broadcastRadius²` 的玩家（去重）。
- 每个 tick：`phase = protocol.phaseAt(age, lockTicks, fallTicks)`；
  `phase != lastPhase` → 给 `viewers` 逐个发 `StrikePhasePacket`，`lastPhase = phase`。
- 收件人离线/换维度：发包前校验；不追发历史相位（客户端有本地推算兜底）。
- **取消 API**：`public static void cancel(UUID strikeId, CancelReason reason)`；
  从 `ACTIVE` 移除 → 发 `StrikeCancelPacket` → 若 `terminalPos != null` 且尚未进入 FIRE，调用
  `SkyfallTerminalBlockEntity.refundCharge()`（充能清零，可立刻再打）；已过 FIRE 的不退款。
- **取消触发点**：
  - `SkyfallTerminalBlock.playerWillDestroy()` → `cancelStrikesFrom(pos)`（配置 `cancel_on_break`，默认 true）；
  - `/apocalypse skyfall cancel [all|<id前缀>]`（权限 2）；
  - `ServerStoppingEvent`：清空前先给所有 active 发 `WORLD_UNLOAD`；
  - `resolveLevel(strike) == null`（维度被卸载）→ 取消；
  - `Config.ORBITAL_STRIKE_ENABLED == false` → 取消。
- **并发上限**：`max_concurrent_strikes`（默认 2）。超限时 `schedule` 拒绝并给玩家 actionbar 提示
  `skyfall.strike.busy`；`/apocalypse skyfall strikes` 可列出进行中的打击（调试用）。

### 1.4 客户端改动

**`OrbitalStrikeClientState` 新增**

| 字段/方法 | 说明 |
|---|---|
| `UUID strikeId` | 包对不上就忽略（防旧包乱入） |
| `boolean spectator` | 用于 HUD 与相机策略 |
| `float timeOffset` | 时间轴校正量（tick） |
| `int phaseOrdinal` | 服务端最后告知的相位；-1 = 无 |
| `onPhase(byte phase, int serverTick)` | 算出 `expectedElapsed = protocol.phaseStart(phase, lock, fall)`；`drift = expected - elapsed()`；`|drift| > 3` 时 `timeOffset = drift`，之后每 tick 乘 0.85 衰减（10 tick 内平滑归零） |
| `elapsed()` | 改为 `baseElapsed + Math.round(timeOffset)` |
| `cancel(reason)` | 清状态 + `OrbitalCinematic.disengage` + HUD 退出 |
| `phase()` | 有 `phaseOrdinal` 用服务端的，否则回落 `protocol.phaseAt(...)` |

> 为什么用平滑偏移而不是直接改 `startGameTime`：直接改会让相机在 1 tick 内跳位；
> 偏移量衰减相当于「悄悄追帧」，最多 3 tick 的可见误差，镜头不会闪。

**`OrbitalCinematic`**

- `apply()` 开头增加：`if (spectator && !ClientFilmSettings.broadcastFilms()) return;`
  （旁观者本地关掉后，镜头不被拉走；世界效果照常）。
- 旁观者不播放 `letterbox` 之外的玩家姿态/手持隐藏逻辑（只动相机与 FOV）。
- 取消包到达时 `disengage` + 权重归零，避免「镜头停在太空」。

**`OrbitalScreenFX`（HUD v2）**

| 角色 | 显示 |
|---|---|
| 施放者 | 保留现有：代号/相位/倒计时/`[K] SKIP`；新增**协议色相位条**（MARK→AFTERMATH 六段，当前段高亮）与「终端充能中」提示 |
| 旁观者 | 顶部细横幅：`CINDER // 焚城 · 远程授权`，剩余秒数，`[K] 跳过`；不显示自己的坐标/范围框 |
| 区内玩家（含旁观者） | 现有红晕/警告保留；显示「距离打击中心 xx 格」 |

**客户端配置**（新增 `apocalypse_zombies-client.toml`，`ModConfig.Type.CLIENT`）

```toml
[films]
	broadcast_films = true   # 别人放的打击是否也拉我的镜头（关掉只看世界效果）
```

### 1.5 服务端配置新增

```toml
[orbital_strike]
	broadcast_films = true          # 是否给附近玩家广播过场（关 = 只施放者看）
	broadcast_radius = 160          # 广播半径（32~256）
	max_concurrent_strikes = 2      # 同时存在的打击上限（1~8）
	strike_block_budget = 4000      # 每 tick 全局方块预算（500~20000）
[skyfall_terminal]
	cancel_on_break = true          # 拆终端是否中止未结算打击（并退款）
```

### 1.6 验收用例（P3 必须逐条过）

| # | 场景 | 通过标准 |
|---|---|---|
| 1 | A 施放、B 在 100 格内 | B 看到同一部电影 + 旁观 HUD；B 的相位条与 A 同步（误差 ≤1 相位） |
| 2 | B 把 `broadcast_films=false` | B 镜头不被拉走，但地面标记/命中/余波可见 |
| 3 | `/tick freeze` 40 tick 后解冻（A/B 同时） | 客户端相位在 10 tick 内追上；相机不跳位；落点/挖地方块与服务端一致 |
| 4 | 在 DEVICE 相位拆掉终端 | 打击取消：无伤害、无地形改动、镜头归位、终端充能清零可再打 |
| 5 | `/apocalypse skyfall cancel` | 同上，且 HUD 显示「已中止」 |
| 6 | 3 人各点一次（上限 2） | 第 3 次被拒并提示；前两次正常错开 |
| 7 | 关服 / 退世界 | 所有挂起打击清空，客户端不残留镜头/HUD |
| 8 | 六协议默认尺寸 | 专服 TPS ≥ 18；单次打击方块任务不跨 tick 尖峰 |

### 1.7 文件与工作量

**新增**：`network/StrikePhasePacket.java`、`network/StrikeCancelPacket.java`、`client/ClientFilmSettings.java`、`client/ClientConfig.java`
**修改**：`OrbitalStrikeManager`、`OrbitalStrikePacket`、`NetworkHandler`（协议号）、`OrbitalStrikeClientState`、`OrbitalCinematic`、`OrbitalScreenFX`、`ClientEvents`、`Config`、`SkyfallTerminalBlock`、`SkyfallTerminalBlockEntity`、`SkyfallTerminalManager`、`ApocalypseCommand`、`lang/*`
**预算：约 2.5 个执行轮**（协议/服务端 1 轮，客户端 1 轮，联机验收 0.5 轮）

---

## 2. P4：资产原创化（参考图出包）

### 2.1 目标

把 **10 张派生自用户参考图**的贴图全部换成项目自绘/程序化资产，jar 里不再含参考图像素；
参考图移到 `art/reference/` 并标注「仅参考，不随包」。

### 2.2 替换清单

| 包内文件 | 尺寸 | 现状 | 替换方案 |
|---|---|---|---|
| `textures/environment/carrier_cannon.png` | 1408×768 | `天基炮.png` 派生 | 自绘分层板 |
| `carrier_lance.png` | 1408×768 | `天基矛发射器.png` 派生 | 自绘分层板 |
| `carrier_singularity.png` | 1408×768 | `引力奇点.png` 派生 | 自绘分层板 |
| `carrier_plasma.png` | 1408×768 | `等离子发射器.png` 派生 | 自绘分层板 |
| `carrier_asteroid.png` / `carrier_asteroid_cutout.png` | 1408×768 / 600² | `小行星.png` 派生 | 自绘分层板 + 抠图 |
| `earth.png` | 512×512 | `小地球.png` 派生 | 程序化生成（噪声大陆 + 云 + 大气边缘） |
| `nebula.png` | 1024×512 | `宇宙.png` 派生 | 程序化星云（fbm + 星点 + 色带） |
| `sat_body / sat_panel / sat_dish.png` | 256² ×3 | `卫星.png` 裁切 | 自绘（金箔、电池格、白碟） |

### 2.3 方案（推荐 A，B 作为兜底）

- **A. 分层 2.5D 自绘板**：每张 1408×768 分 4 层——
  背景星野/行星弧（程序化噪声）→ 载体结构（参考图只取**构图语言**：机位、轮廓方向、明暗分区、主色）
  → 发光件（炮口/反应堆/环流，独立贴图给 `entityTranslucentEmissive`）→ 前景遮挡（尘埃/光斑）。
- **B. 程序化 3D 舞台**：扩展现有 `OrbitalSpaceStage`，用方块/几何画五种载体。
  更原创、包体更小，但照片级质感下降；作为 A 被否决时的兜底，也作为低画质回落。

### 2.4 管线

`tools/orbital_art.py`（Pillow，确定性）：
- 子命令 `earth` / `nebula` / `sat` / `cannon` / `lance` / `singularity` / `plasma` / `asteroid`；
- 输出到 `assets/.../textures/environment/`，`--preview <外部目录>` 出 2× 预览；
- 每张板同时输出 `*_emissive.png`（可选，由 `OrbitalCarrierPlates` 读取；若引擎暂不支持就先用单图）。

### 2.5 验收（必须自动化）

新增 `tools/check_orbital_art.py`：

1. 包内 10 张图的尺寸/格式正确；
2. 与根目录参考图做 **dHash/pHash**：汉明距离 ≥ 阈值（建议 24/64），证明不是原图缩放/裁切/重编码；
3. jar 内不再有与参考图哈希相同或高度相似的条目；
4. `art/reference/` 存在且 `README.md` 写明来源与许可（仅参考）；
5. `NOTICE.md` / `readme.md` 许可段更新：明确「参考图未随包分发」；
6. 视觉抽查：5 张载体板缩略图 + 3 张太空小图，人工确认「还是同一台机器」但细节全换。

### 2.6 批次与工时

| 批次 | 内容 | 验收 | 预算 |
|---|---|---|---|
| A1 | `earth` / `nebula` / `sat_body|panel|dish` | 太空舞台整体换掉，`OrbitalSpaceStage` 截图对比 | 1 轮 |
| A2 | `carrier_cannon` / `carrier_lance` | 焚城/断层电影板替换 | 1 轮 |
| A3 | `carrier_singularity` / `carrier_plasma` / `carrier_asteroid(+cutout)` | 剩余三协议替换，参考图彻底出包 | 1.5 轮 |
| A4 | `check_orbital_art.py` + 文档/许可 + 根目录参考图迁移 | 门禁全绿 | 0.5 轮 |

**风险**：这是全项目工时最大、最容易被「看起来不如原图」卡住的一块。
建议 A1 先做，确认风格能被接受再继续；不通过就转方案 B。

---

## 3. P5：验收与发布（4.0.0）

### 3.1 版本节奏（建议）

| 阶段 | 版本 | 内容 |
|---|---|---|
| P3 完成 | `3.10.0` | 相位同步 / 广播 / 取消 / HUD v2 |
| P4 完成 | `3.11.0` | 资产原创化（参考图出包） |
| P5 | `4.0.0` | 只做验收、文档、发布元数据；不再引入新机制 |

> 也可以把 P3+P4 合成一次 `4.0.0`。建议分开：P3 出错时不必回滚资产，P4 也能独立验收。

### 3.2 自动门禁：`tools/check_skyfall.py`

一次跑完，任一条失败退出码非 0：

| # | 判据 |
|---|---|
| 1 | jar 存在且 `mods.toml` 版本 == `gradle.properties` 的 `mod_version` |
| 2 | 终端方块 + 6 核心的物品/模型/贴图/lang 键全部在包内 |
| 3 | `blockstates/skyfall_terminal.json → models/block → textures/block` 引用链可解析 |
| 4 | 2 份配方 + 1 份掉落表引用的 id 都已注册（终端/核心里程碑） |
| 5 | `zh_cn.json` 与 `en_us.json` 键集合完全一致（含 `skyfall.*`） |
| 6 | 六份 `strike/*.xml` 可被 `StrikeProtocols` 解析（复用 Java 侧逻辑的离线校验或 JSON 镜像） |
| 7 | P4 的资产门禁（`check_orbital_art.py`）全绿、jar 无参考图 |
| 8 | 配置项数量与代码声明一致（从 `Config.java` 反射字段数 vs 运行日志 `Config registry: N entries`） |
| 9 | `readme.md` 头表版本、更新日志段、`gradle.properties`、根 `mod.toml` 四处一致 |

运行期门禁：`tools/skyfall_probe.py`（把 3.9.0 手写的 RCON 探针产品化）——
启动专服 → 等 `Done` → `setblock` 终端 → `data get block` 校验 NBT 字段 → `loot spawn ... mine` 校验掉落
→ `/apocalypse skyfall strikes` 校验命令注册 → 退出码汇总。

### 3.3 联机验收（人工，2 客户端）

1. 主机 + 副机各进同一位面；A 放终端、装核心、授权打击；
2. 检查 P3 §1.6 的 8 条用例；
3. 副机把 `broadcast_films` 关掉再验一次；
4. 中途拆终端 / 退出世界 / 重新进入，确认无残留；
5. 两台机器配置不同的 `broadcast_radius` 时，以服务端为准（客户端不自行决定收件人）。

### 3.4 出货：`tools/_deploy_400.py`

照 `_deploy_199.py` 的八条判据写，不手工拷 jar：

1. 自升版号（`gradle.properties`）；
2. 构建（`build` + `cleanJar`，纯净包仍需 `cleanJar` 剥 TaCZ 转录动画）；
3. 三向对账（jar `mods.toml` / 资产清单 / 源码）；
4. 探锁部署（游戏进程必须完全退出）；
5. 其余模组 md5 全等；
6. 旧包挪 `mods_backup/`（保留 3 份），`mods/` 只留一个本模组包、不许子目录；
7. 文档四处版本号（`gradle.properties`、根 `mod.toml`、`readme.md` 头表、更新日志）；
8. `docs/wiki/07` 台账 + `NOTICE.md` 许可 + `art/reference/README.md`。

发布：`py tools/github_push.py -m "4.0.0: 天陨武库 ..."` → CI 出 `preview` 与 `v4.0.0` Release。

### 3.5 回滚与兼容

- `mods_backup/` 保留最近 3 份 jar；换包前一键回退就是拷回旧 jar。
- 存档兼容：方块 id `apocalypse_zombies:skyfall_terminal` 与 BE 的 NBT 键在 P3/P4 不改；
  升级只新增字段（协议 id、充能记录），旧存档终端默认「未装核心、充能已满」。
- 网络协议号升级到 `"2"`：混版客户端直接连不上，避免半同步；在 readme 里写明「服务端与客户端需同版本」。

### 3.6 发布检查表

- [ ] P3 八条用例全过（单机 + 专服 + 双客户端）
- [ ] P4 资产门禁全绿，jar 内无参考图，NOTICE/readme 许可更新
- [ ] `check_skyfall.py` 九条全绿；`skyfall_probe.py` 专服探针全绿
- [ ] 构建产物：开发包 + clean 包各一份，版本号一致
- [ ] readme 头表 / 更新日志 / 根 mod.toml / wiki 07 四处版本一致
- [ ] 部署脚本跑通、旧包进 backup、其它模组 md5 未变
- [ ] 退回旧包的路径实测一次（拷回 backup jar 能进游戏）

---

## 4. 里程碑与分工

| 里程碑 | 交付 | 写作用域 | 依赖 | 预算 |
|---|---|---|---|---|
| **P3-a 协议层** | 两个新包 + 协议号升级 + 开局收件人集合 | `network/`、`OrbitalStrikeManager`（上半） | 无 | 0.5 轮 |
| **P3-b 服务端** | 相位发包、取消、并发上限、终端退款、命令 | `OrbitalStrikeManager`、`SkyfallTerminal*`、`ApocalypseCommand`、`Config` | P3-a | 0.75 轮 |
| **P3-c 客户端** | 时间偏移、旁观者相机、HUD v2、客户端配置 | `client/`（ClientState/Cinematic/ScreenFX/ClientConfig/ClientFilmSettings） | P3-a（可与 P3-b 并行） | 1 轮 |
| **P3-d 联机验收** | §1.6 八条用例报告 | 只写 `docs/` | P3-b + P3-c | 0.5 轮 |
| **P4-art** | 10 张贴图 + 生成脚本 + 资产门禁 | `textures/environment/`、`tools/orbital_art.py`、`tools/check_orbital_art.py`、`art/reference/` | 无（可全程并行） | 3~4 轮 |
| **P4-doc** | NOTICE/readme 许可、参考图迁移 | `NOTICE.md`、`readme.md`、`art/reference/README.md` | P4-art | 0.25 轮 |
| **P5-gate** | `check_skyfall.py` + `skyfall_probe.py` | `tools/`、`docs/` | P3/P4 | 0.75 轮 |
| **P5-release** | `_deploy_400.py`、四处版本、GitHub 推送 | `tools/_deploy_400.py`、`gradle.properties`、`mod.toml`、`readme.md`、`docs/wiki/07` | 全部 | 0.75 轮 |

**建议顺序**：P3-a →（P3-b ∥ P3-c）→ P3-d ∥ P4-art → P4-doc → P5-gate → P5-release。
关键路径 ≈ **4 轮**；P4 并行时总工期 ≈ **4~5 轮**。

团队分工沿用 P1/P2：Lead 负责协议/服务端/发布，`client-ui` 负责 P3-c，`art-original` 负责 P4，
`qa` 负责 P3-d + P5-gate；写作用域互不重叠（见上表）。

---

## 5. 风险

| 风险 | 影响 | 对策 |
|---|---|---|
| 协议号升级导致旧客户端连不上 | 低（同版本发布） | readme 写明；服务端启动日志打印协议版本 |
| 广播把别人镜头抢走，体感差 | 中 | 客户端默认开、可关；旁观镜头更短；`K` 可跳过；距离 >160 不广播 |
| 相位校正导致镜头抖动 | 中 | 偏移量平滑衰减（±3 tick 内不纠正） |
| 取消时终端充能退款被刷 | 低 | 仅 FIRE 前退款；同一 terminal 每 tick 最多一次 |
| P4 画得不如参考图 | 高（决定是否继续） | A1 小图先验收；不通过转方案 B |
| 并发打击造成 TPS 尖峰 | 中 | 并发上限 + 全局方块预算 + 队列 |
| 当前会话 shell 被 Windows 权限挡住（见交付说明） | 高（无法构建） | 实现前先修会话权限（切完全权限或重开会话） |

---

## 6. 需要你拍板的 5 件事

| # | 问题 | 可选 | 我的建议 |
|---|---|---|---|
| 1 | 版本节奏 | (a) P3=3.10.0 → P4=3.11.0 → P5=4.0.0（b）P3+P4 合并成 4.0.0 | **(a)** |
| 2 | 过场广播默认值 | (a) 服务端开 + 客户端开（b）服务端开、客户端默认关（c）默认全关 | **(a)**，客户端可一键关 |
| 3 | 拆终端中止打击 | (a) 中止并退充能（b）中止不退（c）不中止 | **(a)** |
| 4 | P4 方案 | (a) 分层 2.5D 自绘板（b）程序化 3D 舞台（c）先 A1 看效果再定 | **(c)** → 通过就 (a) |
| 5 | P3 与 P4 顺序 | (a) P3 先（玩法优先）（b）P4 先（版权/原创优先）（c）并行 | **(c)** 并行，P3 为主线 |

---

## 7. 实现进度（3.10.0 已构建，2026-10-19）

> 本轮按推荐默认值开工（3.10.0→3.11.0→4.0.0；广播默认开；拆终端中止并退充能；P4 先 A1）。

| 项 | 状态 | 位置 |
|---|---|---|
| `StrikePhasePacket` / `StrikeCancelPacket` | ✅ 代码已落地（**未编译**） | `network/StrikePhasePacket.java`、`network/StrikeCancelPacket.java` |
| `OrbitalStrikePacket` 扩展（strikeId / spectator / serverGameTime，兼容旧构造器） | ✅ | `network/OrbitalStrikePacket.java` |
| 协议号 `1 → 2`、两个新包注册 | ✅ | `network/NetworkHandler.java` |
| 服务端相位发包（相位变化才发，命中后补发 AFTERMATH） | ✅ | `OrbitalStrikeManager.onServerTick` |
| 过场广播收件人（施放者 + `broadcast_radius` 内玩家，逐个带 spectator 标记） | ✅ | `OrbitalStrikeManager.collectViewers` |
| 取消 API（按 id / 全部 / 按终端）+ 关服/关配置/维度卸载路径 | ✅ | `OrbitalStrikeManager.cancel*` |
| 拆终端中止 + 充能退款（FIRE 前才退） | ✅ | `SkyfallTerminalBlock.playerWillDestroy`、`SkyfallTerminalBlockEntity.refundCharge` |
| 并发上限 + 全局方块预算可配置 | ✅ | `Config.ORBITAL_STRIKE_MAX_CONCURRENT` / `ORBITAL_STRIKE_BLOCK_BUDGET` |
| 配置 5 项（broadcast_films/radius、max_concurrent、block_budget、cancel_on_break） | ✅（配置总数 211 → 216） | `Config.java` |
| **快速充能**：手持红石块右键终端 → 冷却缩短 `quick_charge_seconds`（默认 15s/个，可配物品） | ✅ 服务端已落地，GUI 提示由 task-4 补 | `SkyfallTerminalBlock`、`SkyfallTerminalBlockEntity.quickCharge`、3 个配置（总数 216 → 219） |
| `/apocalypse skyfall cancel | strikes` 运维命令 | ✅ 已落地（编译通过） | `ApocalypseCommand`、`OrbitalStrikeManager.activeCount/cancelAll` |
| 客户端时间偏移校正、旁观者相机开关、HUD v2 | ✅（`BUILD SUCCESSFUL`） | `client/OrbitalStrikeClientState`（phaseTarget/×0.85 回追）、`ClientConfig`/`ClientFilmSettings`、`OrbitalCinematic`、`OrbitalScreenFX`、`SkyfallTerminalScreen`（快速充能提示） |
| 编译 / 专服 / RCON 冒烟 | ✅ | `compileJava` 与 `build` 全绿；`runServer` 启动 `Done (3.6s)` + RCON；`tools/skyfall_probe.py` 四条判据 PASS（放终端/NBT/掉落/命令） |
| 客户端实机目检、双人验收 | ⬜ 待做 | 本机无图形客户端自动化，留 P3-d 人工验收 |
| P4-A1 太空舞台五件套原创化 | ✅（dHash min=23，门禁 PASS） | `textures/environment/{earth,nebula,sat_body,sat_panel,sat_dish}.png`、`tools/orbital_art.py`、`tools/check_orbital_art.py` |
| P4-A2/A3 载体板（5 张 1408×768 + 小行星抠图） | ✅（3.11.0，dHash 对本参考图最小 23） | `textures/environment/carrier_{cannon,lance,singularity,plasma,asteroid,asteroid_cutout}.png`、`tools/carrier_art.py`、`tools/check_carrier_art.py` |
| P5 门禁与出货 | ✅（4.0.0） | `tools/check_skyfall.py`（九组判据）、`tools/_deploy_400.py`（构建→门禁→探锁部署→备份→事后校验）、`tools/skyfall_probe.py`（专服 RCON 探针） |

### 环境与验证（2026-10-19）

- 会话切到「完全权限」后 shell 恢复；本轮的编译/构建/专服/RCON 都由 Lead 的 shell 执行。
- 两个 teammate 会话（client-ui / art-original）仍受 `Workspace is not owned by the current user`
  预检限制，无法自行跑命令：客户端代码由 Lead 编译并修了 1 处 `drawCenteredString` 重载，
  两轮贴图生成/门禁由 Lead 代为执行。
- 构建产物：`build/libs/apocalypse_zombies-3.10.0.jar`（mods.toml `version="3.10.0"`，运行日志
  `Config registry: 219 entries`）。
- 本次**未做**：图形客户端实机目检、双客户端联机验收（P3 §1.6 的 1/2/3/4/5 条依赖玩家输入）。
