# 柯尔特 1878 教练枪（`colt_1878`）交付说明

**并排**双管、折开式（break-action）霰弹枪，12 号。真实原型是 **Colt Model 1878 双管霰弹枪的
20 英寸「教练枪」（coach gun）**构型 —— 西部时代的马路护卫 / 驿站车夫用枪：管短好带、
折开装两发。参考尺寸（Cimarron 复刻件）：全长 **940 mm**、枪管 **508 mm（20″，占全长 54%）**、
机匣 **152 mm**、枪托 **280 mm**、约 **3.4 kg**。**是 extractor（抽壳器）而不是 ejector（抛壳器）**，
退壳动画照这个做 —— 见第 8 节。

本目录里：

| 文件 | 内容 |
|---|---|
| `colt_1878.geo.json` / `colt_1878.animation.json` / `colt_1878.png` | 交付件快照（与 `src/main/resources/assets/apocalypse_zombies/` 下同名文件一致，只读留档） |
| `anim/` | 动画相位验收图（`tools/colt_1878_anim_shots.js` 拍） |
| `shots/` | 几何多角度验收图（`tools/colt_1878_shots.js` 拍） |

## 1. 建模方式与工具链

**没有手搓方块、没有在 Blockbench 里手工摆放。** 与 S686 同一套流程：本地脚本经
**blockbench-mcp**（HTTP `127.0.0.1:3000/bb-mcp`，Blockbench 5.2.1 + 插件 1.8.1）驱动 Blockbench。

| 步骤 | 用到的 MCP 工具 | 脚本 |
|---|---|---|
| 新建 GeckoLib 项目、UV 基准对齐 512² | `create_project` / `risky_eval` | `tools/colt_1878_build.js` |
| 上传 512×512 逐面 UV 图集（本地生成 PNG） | `create_texture` | 同上 |
| 建 12 根骨骼 | `add_group` × 12 | 同上 |
| 放 87 个方块（逐面 UV，8 路并发） | `place_cube` × 87 | 同上 |
| 校验 + 导出 geo | `geckolib_validate_model` / `geckolib_export_model` | 同上 |
| 建 8 条动画 | `create_animation`（跑前先 `risky_eval` 清同名片段） | `tools/colt_1878_anim.js` |
| 校验 + 导出 anim | `geckolib_validate_model` / `geckolib_export_animations` | 同上 |
| 规范化落位（剥 `animation.` 前缀、校验通道形状） | — | `tools/colt_1878_install.js` |
| **人眼核验**：几何多角度 | `create_offscreen_view` + `set_camera_angle` + `capture_screenshot` | `tools/colt_1878_shots.js` |
| **人眼核验**：动画相位（把时间轴拨到指定秒数再拍） | 再加 `animation_timeline(set_time)` | `tools/colt_1878_anim_shots.js` |

重跑一次全链：`node tools/colt_1878_build.js && node tools/colt_1878_anim.js && node tools/colt_1878_install.js`

## 2. 尺寸与坐标

* 项目铁律：**16 u = 1 方块 = 1 m**，1 u = 62.5 mm；**枪口 = −Z、上 = +Y、+X = 射手右侧**。
* 实测包围盒：z −9.064 … +5.821 → 全长 **14.885 u = 930 mm = 0.93 格**（真枪 940 mm）；
  高 2.276 u = 142 mm（含托颈下垂）；宽 0.912 u = 57 mm。
* 并排双管中距 0.38 u ≈ 24 mm（真枪两管中心距约 24–26 mm），管外径 0.35 u ≈ 22 mm。
  两管之间是**焊接肋条**（0.11 u 宽）+ 前珠。
* 贴图 **512×512 逐面 UV 图集**，87 个方块 = **522 个面**，全部落在涂绘区（`check_gun_resources.py` 报"空白 0 个"）。
* **方块之间不留任何缝**（两条一起才够）：
  ① 贴图生成**不再给每个面的四边压暗**。原来那行 `edge ? 0.76 : 1` 让每块方块的边缘都带一条
  深色描边，两块一拼就是一道黑缝 —— 用户说的"间隙"就是它。
  ② 下发 `place_cube` 时每块往各方向外扩 `GAP_FIX = 0.003 u`（0.19 mm），让相邻块**轻微重叠**，
  兜住 `toFixed` 取整与浮点相加留下的亚像素缝。
  立体感交给 MC 自己的逐面光照（up 亮 / down 暗），贴图里不必再烘一遍明暗。

## 3. 骨架层级与 pivot（12 根，rest 姿态旋转全零）

```
root        (0, −0.608,  5.296)   0 方块 —— 武器根
move        (0, −0.608,  5.296)   0 方块 —— 整枪位移（后坐 / 甩腕 / 抬枪）
└ body      (0, −0.508, −1.156)  38 方块  机匣 / 托颈 / 枪托 / 双扳机座   ← pivot 放在**铰链**上
  ├ barrel  (0, −0.508, −1.156)  24 方块  管组（并排双管 + 肋条 + 前珠 + 管口黄铜圈）
  │ ├ forend(0,  0.092, −6.280)   9 方块  前托（纺锤形，随管一起折）
  │ ├ shell_upper  (0, 0.392, −0.916)  4 方块  两发**打完的空壳**（退壳动画驱动的就是它）
  │ ├ hand_l  (0, −0.068, −1.466)  1 方块  左手：握在前托上，所以必须挂 barrel
  │ └ bolt_loaded  (0, 0.392, −0.996)  4 方块  两发**待装弹**（左右各一，`scale` 0↔1 显隐）
  ├ latch   (0,  0.708,  0.916)    1 方块  顶杆（沿 **+X 横向拨** 0.13 u，不是沿枪轴前后推）
  ├ hammer_l(0,  0.708,  0.886)    4 方块  **左右两个外露击锤**（一根骨带两个锤，绕中轴同步）
  ├ trigger_front (0, −0.608, −0.566)  1 方块 前扳机
  └ trigger_rear  (0, −0.608, −0.466)  1 方块 后扳机
```

⚠️ **`hand_l` 与 `bolt_loaded` 必须在 `barrel` 下，不能挂 `body`**：左手握的是前托、
待装弹进的是枪管上的弹膛，两者都随管组一起折。挂错的话枪管一折开，手就留在原地脱离前托、
弹则停在机匣原来那格。`GunFrame.partChain` 是运行时沿 `getParent()` 走的，所以换父级**不用改 Java**。

## 4. 动画清单（8 条，`colt_1878.animation.json`）

| 片段 | 长度 | 驱动骨骼 | 说明 |
|---|---|---|---|
| `static_idle` | 2.0 s 循环 | move | 整枪在手里微微起伏（**不给 body/barrel 转角**，枪管一动不动） |
| `draw` | 0.8 s | move / body | 从下方向上抬起入位（比 S686 的 1.0 s 快） |
| `shoot` | 0.6 s | move / **hammer_l** | 后坐 = **整枪向上微抬 + 向后推**（不用 barrel 转角）+ 击锤弹开再落回 |
| `bolt` | 1.4 s | latch / **body / barrel** / **shell_upper** / move / **hammer_l** | 折开检查：拨顶杆 → 机匣+托上翻 62°（枪管不动）→ extractor 顶壳 + 甩腕退壳 → 合膛（带回弹） |
| `reload_tactical` | **3.0 s = 60 tick** | latch / **body / barrel** / **shell_upper** / move / hand_l / **hammer_l** / bolt_loaded | 有弹换弹 |
| `reload_empty` | **3.6 s = 72 tick** | 同上 | 空仓换弹（两发壳都得退、壳胀了要抠一下、手在弹带里多摸一趟） |
| `ADS_up` / `ADS_down` | 0.22 / 0.18 s | move | 抬镜 / 落镜（铁瞄）—— 同样只走位移，不给 body 转角 |

换弹动作链**照真枪**（原型是折开式 + **extractor 抽壳器**，不是 ejector 抛壳器）：
**拇指横向拨顶杆 → 折开 → extractor 顶起两发空壳 → 甩腕抖掉壳 →
右手取两发 → 两发同时塞进两弹膛 → 合膛、顶杆自动回中**。
依据与研究来源见本目录第 8 节。

### 折开的表现方式：机匣向上翻，枪管不动

⚠️ 两件事要连着看，改一个必须改另一个：

1. **轴**：折开绕的是 **X**（铰链那根横轴），不是 Z。Z 是枪管长轴，绕它转只是**枪身滚转** ——
   枪仍水平伸着、仅换了个面。轴与符号由 `node tools/colt_1878_hinge_probe.js` 量出来，不要靠推理。
2. **谁转**：现在**不是**"枪管向下折"，而是 **body 转 −62°、barrel 转 +62°**。
   两个骨的 pivot **都是铰链**（`(0, −0.508, −1.156)`），反向角正好抵消 ⇒
   **枪管链（barrel / forend / shell_upper / hand_l / bolt_loaded）在世界坐标里完全不动**，
   只有机匣与枪托绕铰链向上翻。相对角一样是 62°，弹膛照样露出来，
   但第一人称里枪管不会甩出画面中心 —— 这是用户点名要的观感。
   "枪管真的没动"由 `node tools/colt_1878_fold_probe.js` 量：`body −62 / barrel +62`
   那一行，枪管 cube 的世界坐标与 rest **逐位相同**（`[−0.306, 0.276, −9.044]`）。

⚠️ 由此推出一条硬约束：**`shoot` / `static_idle` / `ADS_*` 都不许再给 barrel 或 body 转角**。
给 body 转角，枪管会跟着父骨动；给 barrel 转角，枪管自己动。后坐与呼吸一律用 `move` 的位移表达。
（`draw` 是唯一的例外 —— 那是入位动作，整枪转动本来就是对的。）

**外露双锤是本枪与 S686 最显眼的分野**，所以 `hammer_l` 是真动的：折开时被机构顶回待击位
（`rotation.x = +26°`）、合膛后落回 0°、射击瞬间弹到 +30° 再落回 —— 与 S686 的 `hammer` 通道
**逐字一致**。⚠️ 注意 `tools/colt_1878_anim.js` 里写的是 **负值**（−26 / +4 / −30）：
那份文件用的是 Blockbench 编辑器坐标，导出插件会沿 X 取反，看着"反了"改成正的就是穿模。

## 5. Java 侧

* `item/Colt1878Item.java` —— **继承 `S686Item`**，只覆盖五项：动作时长（`actionLength`）、
  音效时刻表（`soundCuesFor`）、伤害类型（`colt_1878_bullet`）、准线（`adsX/adsY/adsPitch/adsYaw`）、
  手感（`aimTime` 0.13 s / `aimedFov` 60° / `firstPersonScale` 1.32）。开火、换弹、手臂姿态
  那一整套逻辑一行都不用抄。
* 为此把 `S686Item` 的 `actionLength` / `soundCuesFor` / `bulletSource` / `damageType()` 从
  `private static` 改成 **`protected` 实例方法**；`tryFire` / `beginReload` / `inventoryTick`
  里的动作锁定不再直接读常量，而是走 `actionLength(...)` —— 所以子类覆盖一处，全链路跟着变。
* `registry/ModItems.java` 注册 `COLT_1878` 并入创造物品栏；
  `event/ZombieLoot.java` 的 0.2% 枪械档从六把扩到七把；
  `client/weapon/WeaponArms.java` 加 `renderColt1878` 分支（必须排在 `instanceof S686Item` **之前**，
  它是子类）+ `forgetFrames` 清 `Colt1878GeoModel.frame`。
* 资源：`geo/` `animations/` `textures/item/` `models/item/colt_1878.json`（与 s686 同一套持枪角）
  `data/apocalypse_zombies/damage_type/colt_1878_bullet.json` + 两套 lang。

## 6. 门禁与实测

* `python3 tools/check_gun_resources.py` → **全部通过（7 把枪 + 7 个其他物品 + 24 个音效）**，
  其中 colt 一行：geo/贴图/动画齐、12 骨 8 片段驱动骨对齐、498 面 UV 无空白、
  **动作时长常量与片段长度一致**、display 旋转 [2,4] 与 DISPLAY_PITCH/YAW 一致、ADS 位移在量算区间内。
* `node tools/colt_1878_install.js` → 规范化自检全部通过。
* MCP `geckolib_validate_model` → **0 error / 1 warning**：`animation.bolt` 声明 1.4 s 但最后一个
  关键帧在 1.4167 s（GeckoLib 按 `animation_length` 截断，实际不影响；S686 同款）。
* `./gradlew compileJava` → 通过。

## 7. 导入注意 / 未决项

* 渲染走 `Colt1878GeoModel`（geo / 贴图 / 动画三个 `ResourceLocation`）+ `Colt1878ItemRenderer`，
  与其它六把枪同一条链；`renderType`、动画控制器名无需新注册。
* ⚠️ **`ADS_X` / `ADS_Y` 目前沿用 S686 的量算值**（−0.4749 / 0.3533）。本枪肋条顶面比 S686 略低，
  实测跑过 `tools/pose_measure.py` 那条链后应按本枪几何重算。
* `shell_upper` 原本是 0 方块的**空骨**（当初为了和 S686 的骨骼名对齐留的），
  退壳动画一直在驱动一个不存在的东西 —— 已补上两发空壳方块，见第 8 节。
* 未做（本模组用 GeckoLib 自研渲染，TaCZ 那套 LOD / 32×32 背包贴图 / 枪包命名空间不适用）：
  LOD 低模、HUD 侧视图、LabPBR。

## 8. 真枪依据：它是怎么换弹的（动画照这个做）

原型 **Colt Model 1878**，这里按 Cimarron 复刻的 20″ 教练枪建模：
<https://www.cimarron-firearms.com/1878-coach-gun-12-ga-20-barrel-standard-blue.html>

**extractor ≠ ejector** —— 这一点决定了"退壳"该长什么样：

- **extractor（本枪）**：开膛时只把弹壳**顶起几毫米**，壳还得用手指抠、或把枪口朝下**甩**出来。
- **ejector**：开膛时自动把壳**弹飞**。

参考：[Ejectors vs Extractors](https://forum.nosler.com/threads/ejectors-vs-extractors.45729/)、
[Remington Premier OU 手册](https://www.remarms.com/sites/default/files/PremierOU.pdf)（那句
"the ejectors automatically eject any fired rounds … when the action is opened" 说的是 ejector 枪）、
[侧并排使用手册](http://www.mackspw.com/PDF/Side%20By%20Side%20User%20Manual.pdf)、
[Stoeger CoachGun Drills](https://www.shotgunworld.com/threads/stoeger-coachgun-drills.335727/)、
[Speed reload Coach Gun](https://www.glocktalk.com/threads/speed-reload-coach-gun.1353308/)、
[SASS Cowboy Chronicle 2018-04](https://sassnet.com/uploads/downloads/cowboychronicle/2018/18aprchron.pdf)。

七步：① 拇指把顶杆**横向拨**到射手右侧解锁 ② 左手压前托、右手抬托颈，管组绕铰链**向下**折开，
枪口朝下、弹膛口朝上后方 ③ extractor 顶起两发空壳 ④ **甩腕**把壳抖出去 ⑤ 右手取两发
⑥ **两发同时**塞进两个弹膛 ⑦ 管组上抬合膛、顶杆自动回中（"咔"）。

### 修掉过的硬伤（都是"一眼就不像"级别）

1. **折开写成了绕 Z**（`[0,0,-52]`）。Z 是枪管长轴，绕它转是**枪身滚转** ——
   枪仍水平伸着、只是换了个面。改成绕 **X**、折 62°。
2. **`shell_upper` 是空骨** → 退壳在游戏里根本不可见。已补两发空壳方块
   （黄铜底缘朝 +Z，也就是弹膛口那一侧）。
3. **`hand_l` / `bolt_loaded` 挂在 `body` 下** → 枪管一折开，左手就脱离前托飘着、
   待装弹停在一个不存在的膛位上。改挂 `barrel`（Java 侧不用动，见第 3 节）。
4. **`colt_1878_build.js` 没下发 cube 级 rotation**（`place_cube` 的 `rotation` 写死成
   `[0,0,0]`）→ geo 里给枪托算好的下垂角从没生效；且下垂角**符号反了**
   （每段相对整体下降上翘 13.3°，8 段互相错开）→ 枪托是一串台阶。
   改对之后 `sin(13.3°) × 0.5075 = 0.1167 ≈ DROP/SEGS = 0.12`，相邻段端点正好对接。

### 1.1.63：方块无缝 + 折开改成"枪管不动"

5. **方块之间有一道黑缝**：贴图给每个面的四边都压暗了 24%（`edge ? 0.76 : 1`），
   一块块的边缘拼起来就是一串缝。去掉描边，并让每块往各方向外扩 `0.003 u` 与邻居轻微重叠。
6. **折开的"谁在动"**：原来是 barrel 绕铰链转 —— 枪管垂下去，第一人称里直接甩出画面中心。
   改成 `body −62° / barrel +62°`（两者同 pivot 反向）= **枪管世界不动、机匣与托向上翻**。
   连带把 `shoot` / `static_idle` / `ADS_*` 里 barrel 与 body 的转角全部撤掉，改用 `move` 位移表达。

### 复跑与验收

```
node tools/colt_1878_fold_probe.js       # 折开：机匣上翻、枪管世界不动（改动画前先跑）
node tools/colt_1878_hinge_probe.js      # 折开轴的几何量测（第一版定轴时用的，留着备查）
node tools/colt_1878_build.js --reset    # 重建 geo + 贴图（87 方块）
node tools/colt_1878_anim.js             # 重建 8 条动画
node tools/colt_1878_install.js          # 规范化落位 + 门禁
node tools/colt_1878_anim_shots.js       # 动画相位验收图
node tools/colt_1878_dump_clip.js reload_tactical   # 看关键帧，核对 body/barrel 是否严格反向
```

`anim/` 里就是这轮拍的验收图；其中 `reload_tactical_t0p67.png`（折开到底）和
`reload_tactical_t1p04.png`（甩腕退壳、两发空壳已飞出）最能说明问题。
改了 `tools/colt_1878_anim.js` 的时间表，记得同步改 `tools/colt_1878_anim_shots.js` 的 `PHASES`。
