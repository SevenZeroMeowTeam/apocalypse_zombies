# 柯尔特 1878 教练枪（`colt_1878`）交付说明

**并排**双管、折开式（break-action）霰弹枪，12 号。真实原型是 **Colt Model 1878 双管霰弹枪的
20 英寸「教练枪」（coach gun）**构型 —— 西部时代的马路护卫 / 驿站车夫用枪：管短好带、
折开装两发。参考尺寸（Cimarron 复刻件）：全长 **940 mm**、枪管 **610 mm**、约 **3.4 kg**。

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
| 放 83 个方块（逐面 UV，8 路并发） | `place_cube` × 83 | 同上 |
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
* 贴图 **512×512 逐面 UV 图集**，83 个方块 = **498 个面**，全部落在涂绘区（`check_gun_resources.py` 报"空白 0 个"）。

## 3. 骨架层级与 pivot（12 根，rest 姿态旋转全零）

```
root        (0, −0.608,  5.296)   0 方块 —— 武器根
move        (0, −0.608,  5.296)   0 方块 —— 整枪位移（后坐 / 抬枪 / 跑步姿态）
└ body      (0, 0, 0)            38 方块  机匣 / 托颈 / 枪托 / 双扳机座
  ├ barrel  (0, −0.508, −1.156)  24 方块  管组（并排双管 + 肋条 + 前珠 + 管口黄铜圈）
  │ ├ forend(0,  0.092, −6.280)   9 方块  前托（纺锤形，随管一起折）
  │ └ shell_upper (0, 0.392, −0.916)  0 方块  ┐ 空骨：与 S686 的骨骼名对齐，
  ├ latch   (0,  0.708,  0.916)    1 方块  折开拨杆（沿 +Z 推 0.14 u）  │ 实际壳体走 bolt_loaded
  ├ hammer_l(0,  0.708,  0.886)    4 方块  **左右两个外露击锤**（一根骨带两个锤，绕中轴同步）
  ├ trigger_front (0, −0.608, −0.566)  1 方块 前扳机
  ├ trigger_rear  (0, −0.608, −0.466)  1 方块 后扳机
  ├ hand_l  (0, −0.068, −1.466)    1 方块  左手落点标记（换弹时手臂目标）
  └ bolt_loaded (0, 0.392, −0.996) 4 方块  两发新弹（左右各一，`scale` 0↔1 显隐）
```

## 4. 动画清单（8 条，`colt_1878.animation.json`）

| 片段 | 长度 | 驱动骨骼 | 说明 |
|---|---|---|---|
| `static_idle` | 2.0 s 循环 | move / body / barrel | 呼吸浮动 + 双管重量造成的枪口微垂 |
| `draw` | 0.8 s | move / body | 从下方向上抬起入位（比 S686 的 1.0 s 快） |
| `shoot` | 0.6 s | move / barrel / **hammer_l** | 后坐 + 击锤弹开再落回 |
| `bolt` | 1.4 s | latch / barrel / shell_upper / **hammer_l** | 折开检查：拨杆 → 管折下 52° → 退壳 → 合膛（带回弹） |
| `reload_tactical` | **3.0 s = 60 tick** | latch / barrel / shell_upper / hand_l / **hammer_l** / bolt_loaded | 有弹换弹 |
| `reload_empty` | **3.6 s = 72 tick** | 同上 | 空仓换弹（多退一遍壳、手在弹袋里多摸一下） |
| `ADS_up` / `ADS_down` | 0.22 / 0.18 s | move / body | 抬镜 / 落镜（铁瞄） |

换弹动作链（照真枪折开式顺序）：**拨开膛杆 → 管组折下 52° → 退壳 → 左手探腰间弹袋 →
夹回两发 → 推入弹膛 → 合膛（带回弹）**。

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
* `shell_upper` 是 0 方块的**空骨**（与 S686 骨骼名对齐留的），实际壳体走 `bolt_loaded`。
* 未做（本模组用 GeckoLib 自研渲染，TaCZ 那套 LOD / 32×32 背包贴图 / 枪包命名空间不适用）：
  LOD 低模、HUD 侧视图、LabPBR。
