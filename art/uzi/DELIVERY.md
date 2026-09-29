# uzi 交付台账

## 建模 v2 + 全套动画（8 clip）—— 未绑定 jar 版本

| 项 | 值 |
|---|---|
| 资产 | `geo/uzi.geo.json`（`geometry.uzi`）、`textures/item/uzi.png`（512×512）、`animations/uzi.animation.json` |
| 几何 | 骨骼 **22** / 体块 **185** / 长 **15.77u = 0.986 格** / 枪管棱柱 66 块（18 个角度采样，轴心 y=1.60） |
| 贴图 | 逐面 UV **1110 面全通过**，密度 13 px/u，图集占用 271/512 |
| 动画 | **8 个 clip**，232 个关键帧条目，一律 `lerp_mode: catmullrom`（导出期设插值的通道关键帧 323 个），导出 **79,658 字节**，`format_version 1.8.0` |
| 真源 | `tools/uzi_bb_gen.js`（几何+贴图，已是 IIFE）；`tools/uzi_anim.py`（8 个 clip 的关键帧数据 + 写盘/导出） |
| 运行器 | `tools/uzi_bb_run.py`（剥注释后送 `risky_eval`，顺手落贴图 PNG 并导出 geo） |
| 视图工具 | `tools/bb_shot.py`（MCP 视图抓图）、`tools/uzi_anim_appshot.py`（整窗截图，**带实时骨骼变形**） |
| 门禁 | `tools/check_uzi_art.py` PASS、`tools/check_uzi_anim.py` PASS；全仓库 **13/13** 个 `check_*.py` 全部 exit 0 |
| Java 同步 | **未做** —— `UziItem` / `GeoModel` / `ANIM_*` 常量尚未落地，动画只是资源侧就位 |

### 动画清单

| clip | 长度 | loop | 骨骼 | 关键帧 | 内容 |
|---|---|---|---|---|---|
| `static_idle` | 2.0s | ✅ | 9 | 22 | 静止/复位基准：把 `move`/`bolt`/`magazine`/`casing`/弹带全部钉在静止位，供其它 clip 混合回位 |
| `draw` | 1.0s | — | 9 | 27 | 拔枪：枪从画面下方 2.2u 抬起带过冲回落；枪机起始挂在后方 0.55u → 0.575s 释放闭锁（上膛） |
| `shoot` | 0.6s | — | 9 | 37 | 开火：枪机 **83ms 到顶 / 208ms 复进**（比手动拉栓快一倍，自由枪机的味道）＋抛壳＋后座上跳指数衰减 |
| `bolt` | 1.2667s | — | 6 | 32 | 拉栓：枪机沿 +Z 后退 **1.05u（66mm）**，到位抛壳，复进带一次回弹 |
| `reload_tactical` | 2.6s | — | 9 | 37 | 战术换弹（膛内有弹）：弹匣下移 5.60u 脱出 → 新匣入位 → 拉栓上膛（不抛壳） |
| `reload_empty` | 3.3s | — | 9 | 43 | 空仓换弹：弹匣脱出 → 新匣入位 → **三层弹带 1.88/1.94/2.00s 逐层亮起** → 拉栓上膛 |
| `ADS_up` | 0.18s | — | 9 | 17 | 进入瞄准：`move` 上移 0.42u + 前推 0.26u，枪身俯仰 0→3.6°（1/24s 步长 5 键，照弩既有实现） |
| `ADS_down` | 0.18s | — | 9 | 17 | 退出瞄准：`ADS_up` 的严格倒放，收在静止位 |

### 关键不变量（`check_uzi_anim.py` 逐条硬断言）

- 结尾必须回到静止姿态 —— 否则切回 `static_idle` 会跳变。（`ADS_*` 例外：过渡 clip，`ADS_up` 收在瞄准姿态、`ADS_down` 收在静止位）
- 弹匣最低点必须让**匣顶降到握把底之下**（实测 −5.02 vs −2.00，脱出 3.02u）—— 否则换弹看起来只是弹匣原地抖动。
- 自由枪机只能沿 **+Z** 平移，不许有 x/y 分量。
- 空仓换弹的弹带在**弹匣完全入位之后**才允许出现。
- `casing` 在每个 clip 都显式 scale 0 藏起来，只在 `bolt`/`shoot` 里抛出。
- `shoot` 的枪机循环必须够快（≤0.12s 到顶、≤0.25s 复进），否则不像自由枪机。
- `ADS_up`/`ADS_down` 必须**互为倒放且接力衔接**（`ADS_down` 起始 == `ADS_up` 终态）；过渡 clip 里除 `move`/`body` 外所有骨骼只许一个常量帧。
- `draw` 起始 `move.position.y ≤ −1.0`（枪确实从下方入画）、枪机起始挂后方且结尾归零。
- **符号必须与参考枪一致** —— 逐通道和 `m1_garand` / `crossbow` 的文件空间数值比：后座俯仰、拉栓俯仰、拔枪俯仰、ADS 终态俯仰、抛壳横向、抛壳翻滚方向。
- `additional_magazine` 永不被 K 帧（TaCZ 崩溃红线）。

### 踩到的坑（务必记住）

1. **`create_animation` 会把 clip 名存成 `animation.<name>`**，导出即成为 JSON 键；而 Java 的
   `RawAnimation.begin().thenLoop("static_idle")` 按键名取 —— 键对不上就是**静默不播**，导出文件看起来完全正常。
   必须在导出前逐个改名去前缀。仓库里 Blockbench 导出的 clip 全是纯名，紧凑数组体（`{"rotation":{"0.0":[x,y,z]}}`）是手写的，两种形态并存。
2. **GeckoLib 插件只在插值非 linear 时才写 `lerp_mode`** —— 默认导出没有 `catmullrom`。
   而 `BoneAnimator` 的关键帧存在 **`rotation`/`position`/`scale` 普通数组**里（**没有 `.keyframes`**），
   探测 `.keyframes` 得 0，会误判成空动画。
3. **生成器文件本身已经是 IIFE**（末尾 `})()`）。再包一层 `(function(){…})()` 会丢掉内层返回值，
   报「executed successfully, but no result was returned」—— 这条曾让我以为生成器没跑。
4. **几何重跑会重掷骨骼 UUID**，动画必须跟着重建；且建之前要**先删同名 clip**，否则重复堆叠。
   安全顺序只有一条：几何生成 → geo 导出 → 动画生成（reset + create + 去前缀 + 设插值 + 导出）。
5. **观察窗只开单侧等于没开**：`mag_lx`/`grip_lx` 是整块实心时，黄铜弹只在射手看不见的那一侧透出。
   两侧都开窗后才两侧可见 —— 单视角预览发现不了，必须渲两个对侧视角。
6. `risky_eval` 的载荷连 `/* */` 也不接受（不只是 `//` 和 `console.`）。
7. **旋转也会被导出器镜像 —— 这是唯一让「照抄参考文件」翻车的地方。** 见下一节。
8. **MCP 的 `capture_screenshot` 渲的是未变形的静态几何**：8 个不同 clip/时间点抓出来字节完全相同（md5 一致）。
   要看动画姿态必须用 `capture_app_screenshot` 抓整窗（`tools/uzi_anim_appshot.py`）。

### 镜像（既定契约，非 bug）

导出时**所有带 pivot 的元素 x 取反**，全局一致：`eject_port` 源 +0.80 → 导出 −0.86，与 `casing`（源 +0.62 → 导出 −0.62）同侧。
枪口/握把/弹匣的左右关系全部保留，只有偏轴心零件能暴露它。

**镜像同样作用于动画通道，且 position 与 rotation 的规则不同：**

| 通道 | 作者空间 → 文件空间 |
|---|---|
| `position` | **x 取反**，y / z 不变 |
| `rotation` | **x 与 y 取反**，z 不变 |

参考枪的 `.animation.json` 是**文件空间**（游戏直接读），把它里面的数值原样抄进 Blockbench **作者空间**，
整段动作就会上下/左右翻过来 —— 枪口该上跳却下压、抛壳该往射手右侧却跑到左侧，
而文件本身、门禁、导出日志**全部正常**，只有对着参考枪逐通道比符号才看得见。
`tools/uzi_anim.py` 因此统一用 `pos()` / `rot()` 转换，**源码一律按文件空间书写**，可以直接和 `.animation.json` 对照。

判定符号的**物理判据**（不依赖信任任何单个文件）：
`draw` 起始枪在下方 2.2u 且 `move.rotation.x = +14` → **文件空间 +x = 枪口下压**；
于是 `shoot` 的 `move.rotation.x = −2.6` 就是枪口上跳，符合后坐。
同侧校验：`ADS_up` 终态 `body.rotation.x` 必须与弩同为 **+3.6**；`bolt` 合俯仰必须与 m1 同号。

> 早期交付的 `bolt` / `reload_tactical` / `reload_empty` / `static_idle` 曾整体镜像（当时以镜像后的画面为准，
> 未与参考枪文件对符号）。本轮以 `rot()` 统一纠正，旧值全部作废。

校验脚本一律以 `|x|` + 符号一致性判定，绝不「修正」单个模型。

## 参考图判读（`R-C-uzi.jpg`，剖面图）

画面**右侧 = 枪口端**（竖直准星柱 + 外露短枪管）；**最左端 = 枪尾**（带铆钉螺母后盖板 + 顶部方形翻转照门 + 锯齿状复进簧）；
**弹匣插在握把内**（黄铜弹竖直堆叠、弹头朝前）—— Uzi 立身之本；红色高亮是**枪机本体**；扳机/护圈在握把**前方**。
按图中实际结构建模，不套印象。

## 出货记录 · 1.1.37（编译 jar 替换测试）

| 项 | 值 |
| --- | --- |
| 产物 | `apocalypse_zombies-1.1.37.jar` |
| md5 | `e0d329810177c0fc0dd65560e4b9a978` |
| 尺寸 | 1,993,836 字节 |
| 部署 | `.../versions/1.20.1-Forge_47.4.23-2/mods/`（唯一样本；1.1.36 已改名 `.old.bak`） |
| 出货脚本 | `tools/_deploy_137.py`（自升版号 → 构建 → 17 项对账 → 探锁部署） |

**本轮相对 1.1.36 的增量为 9 个 jar 条目，其余资产/数据逐条字节全等**（仅两套语言文件有意增键）：

```
assets/apocalypse_zombies/animations/uzi.animation.json
assets/apocalypse_zombies/geo/uzi.geo.json
assets/apocalypse_zombies/models/item/uzi.json
assets/apocalypse_zombies/textures/item/uzi.png
data/apocalypse_zombies/damage_type/uzi_bullet.json
com/apocalypse/zombies/item/UziItem.class        (+ UziItem$1.class)
com/apocalypse/zombies/client/model/UziGeoModel.class
com/apocalypse/zombies/client/renderer/UziItemRenderer.class
```

资产三向对账（jar == `art/uzi/` == `src/main/resources/`）逐字节相同，geo md5 `7c977c401123cad4c9c0800511d74132`。

**ADS 常量由 `tools/pose_measure.py uzi` 量出，非估算**：`ADS_X = −0.4746`、`ADS_Y = +0.3118`。
（`pose_measure.py` 本轮补了 `uzi` 行；顺带修掉「手持落点表格硬编码 M1 握把/枪口点」的缺陷，改为按枪取 `grip`/`muzzle`。）

**第三人称四常量由 `tools/uzi_tp_solve.py` 闭式解独立复现**（`T = S⁻¹Rᵀ(−(A+t_d)) − nudge − grip/16`）：
先以 M1 已出货值标定，最大误差 **4.2e-4**；随后解出 Uzi 四值与仓库现值**逐个吻合**——

| 常量 | 闭式解 | 仓库现值 |
| --- | --- | --- |
| `TP_X_RIGHT` | −0.593284 | −0.593 |
| `TP_X_LEFT` | −0.406716 | −0.407 |
| `TP_Y` | 0.391586 | 0.392 |
| `TP_Z` | −0.438433 | −0.438 |

即：`UziItemRenderer` 的第三人称常量**无需改动**。
（脚本原先手抄了 `scale=0.68`、`grip=(0,0.80,1.85)`，与真值 `uzi.json` 的 0.67 / `UziGeoModel.GRIP` 的 `(0.00,0.50,2.00)` 不符，
解出 `TP_Y` 偏 0.0192；已改为从源码读并入断言，杜绝复发。）


### 已修：瞄具线 2.34° 上翘（1.1.38）

原状态：前准星柱顶 y = 3.45，后照门窥孔片 `sr_ap` 中心 y = 3.08（差 0.37u）→ 开镜时两条线不平行，实测 **2.34°**。

根因（**几何读出，不是审美判断**）：前准星自己有护环 `sf_hood_top`（下沿 **3.26**），而柱顶 **3.45 比护环顶盖高 0.13
—— 柱戳穿了自己的护环**，这是真缺陷；后照门那边 `sr_leaf` 上沿 3.38、护耳 ≤ 3.46。

修法（`tools/uzi_bb_gen.js:197,205`）：**两端都收到 3.26**，而**不是**把 `sr_ap` 抬到 3.45（本档早先写的那个修法是错的，
会把窥孔片顶出护耳）。
  · `sf_post` 柱顶 3.45 → 3.26（origin y=2.78 不变，高 0.67 → 0.48）
  · `sr_ap` 中心 3.08 → 3.26（片体 3.16–3.36，仍在 `sr_leaf` ≤3.38、护耳 ≤3.46 内）
改后两条线同高、与枪膛平行；`tools/pose_measure.py uzi` 报 **0.00° 离轴**（方向 `(0,0,-1)`）。

牵连（三处都已同步，漏一处就白改）：
  · `pose_measure.py` 的 uzi 锚点是**硬编码**的（`rear` 3.08 / `front` 3.45 / `anchor_checks` 同值）。
    geo 改了它**不会报错**（断言没挡住），只会静默拿旧值算出「还是 2.34°」—— 已校正为两端 3.26。
  · `UziItem.ADS_Y` 0.3118 → **0.3015**（孔心抬高 0.18u 后重新量算，残差 0.0000）。
  · 几何重跑重掷骨骼 UUID → 动画按本档第 53 条随之重建（9 clip / 354 键）。

## 出货记录 · 1.1.38（瞄具线归零 + 五把枪打完自动换弹）

| 项 | 值 |
|---|---|
| jar | `apocalypse_zombies-1.1.38.jar`，**1,994,232 字节**，md5 **`a2690d555581ba6730b24619280a6b59`** |
| 部署 | mods 目录唯一样本；1.1.37 → `1.1.37.jar.old.bak`；其余 **20 个模组 md5 全等** |
| 脚本 | `tools/_deploy_138.py` —— 基线用 **md5 钉身份**取 1.1.37 出货件（`e0d32981…`），不认同名 jar |
| 相对 1.1.37 | **恰 14 个条目变化**：5 把枪的 class + 各自 `$1` 内部类 + uzi geo/png + `mods.toml`/`MANIFEST.MF`。（`uzi.animation.json` 逐字节未变；五把枪以外的条目零变化） |
| 数值指纹 | 包内 geo 前柱顶 **3.26**、孔心 **3.26**；`UziItem.class` 含 `0.3015f` 且**不含** `0.3118f` |
| 门禁 | `check_uzi_art` / `check_uzi_anim` / `check_gun_resources` + 其余 5 个枪械校验器全过 |
| 瞄准 | `pose_measure uzi` **0.00° 离轴**，ADS 残差 0.0000 / 0.0000 |

### 五把枪「打完自动换弹」（M1 / 莫辛纳甘 / AWM / 十字弩 / Uzi）

用户要的是**两种触发都要**：① 打空立刻换 ② 若因故仍是空匣，扣扳机也触发。

实现（一处逻辑、五处调用，形状五把完全一致）：
  · **①** 挂在各枪 `inventoryTick` 的「已排定动作处理完之后、动作空闲处」：
    `if (selected && getAmmo(stack) <= 0 && getAction(stack).isEmpty() && !isLocked(stack, now)
    && entity instanceof ServerPlayer serverPlayer) beginReload(...)`
    —— **放在动作之后是本设计的关键**：M1 照常**叮**（叮声本就在 `reload_empty` 片段 t=12，不在射击片段，
    所以立刻换弹不会吃掉它）、栓动枪照常循环枪机，才轮到换弹。
    反过来想「在 `beginReload` 里跟冷却锁搏斗」是错的：`isLocked` / `put` / `TAG_LOCKED_UNTIL` 都是**各枪私有**，
    且每个 `beginReload` 自身就以 `isLocked` 守卫开头 —— 射击那一发设的冷却锁会把它直接挡回去。
  · **②** 各枪 `tryFire` 空匣分支：干响一声照旧，`return` 前补 `beginReload(player, stack, level)`。
  · 只对**手持**生效（`selected`）—— 躺在背包里的枪不会自己上膛。
  · 未动：连发节奏、空匣停火、拉栓、两套换弹片段及其按键绑定。

### 本轮未完成（下一步）

- **手持只见一只手**：`WeaponArms.render` 代码层面**两只手都在画**（`drawArm` 数学左右对称、五把枪
  `GRIP`/`SUPPORT` 落点相距 2.5–8.4 单位、`dist` 均远小于 3.0 剔除线），静态读代码**无法定论**。
  待查疑点：`GunFrame.toCamera` 超 4 格返 `null` → 左臂整条不画；或左手被枪身遮挡。
  **需要一张游戏内第一人称腰射截图**才能定位。
- **跑步跟随 TaCZ 持枪模式**：全项目**零 sprint 姿态**，属从零新增（新 clip + Java 侧接线），未动。


