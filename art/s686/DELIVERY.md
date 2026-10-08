# Gold Plate - S686 交付说明

上下双管、折开式（break-action）霰弹枪。参考图见本目录 `R-C-s686-gold-plate.webp`。

## 1. 建模方式与工具链

**没有手搓方块，也没有在 Blockbench 里手动摆放。** 全流程由本地脚本经
**blockbench-mcp**（HTTP `127.0.0.1:3000/bb-mcp`，Blockbench 5.2.1 + 插件 1.8.1）驱动
Blockbench 完成：

| 步骤 | 用到的 MCP 工具 |
|---|---|
| 新建 GeckoLib 项目 | `create_project(format=geckolib_model)` |
| 对齐 UV 基准到 512×512 | `risky_eval`（GeckoLib 项目默认按 16×16 解释 UV，会让 512 图集在游戏里错位） |
| 上传 512×512 逐面 UV 图集 | `create_texture(data=<本地生成的 PNG>)` |
| 建 25 根骨骼 | `add_group` × 25 |
| 放 281 个方块（含逐面 UV） | `place_cube` × 281（每块一次调用，8 路并发） |
| 建 8 条动画 | `create_animation` |
| 校验 | `geckolib_validate_model` → **0 error / 0 warning** |
| 导出 | `geckolib_export_model` / `geckolib_export_animations` |
| 视觉核验 | `create_offscreen_view` + `set_camera_angle` + `capture_screenshot` / `animation_timeline` |

脚本（可重跑、可 diff）：

- `tools/s686_geo.js` —— 几何定义（骨骼树 + 全部方块 + 调色板 + 明暗表）
- `tools/s686_build.js` —— UV 打包 / 贴图绘制 / MCP 下发 / 导出
- `tools/s686_anim.js` —— 8 条动画的下发与导出
- `tools/s686_install.js` —— 规范化并落位到资源目录（含逐面 UV 涂绘自检）
- 支撑库：`tools/bbmcp_lib.js`、`tools/png_write.js`、`tools/png_read.js`
- 核验用：`tools/bb_shots.js`（多视角截图）、`tools/bb_animshot.js`（动画指定时刻截图）

## 2. 尺寸与坐标

铁律：**16 u = 1 方块 = 1 m，枪口 = −Z，上 = +Y，+X = 射手右侧**，原点在机匣中心，握把在下方；
**所有骨骼初始旋转为 0**（可动位移全部靠动画关键帧）。

| 项 | 值 |
|---|---|
| 全长（Z） | 19.50 u = **1.22 格** |
| 高度（Y） | 3.14 u（含握把底面与开膛杆顶） |
| 宽度（X） | 1.36 u |
| 骨骼 / 方块 / 面 | 25 骨 / 281 块 / 1686 个四边形面（≈3372 三角面，落在美术规范 3k–15k 区间） |
| 贴图 | 512×512 RGBA，逐面 UV 图集，密度 **13 px/u**，占用 258/512 行 |

结构与真实 Citori / S686 类猎枪一致：

| 区段 | Z 范围 | 内容 |
|---|---|---|
| 枪管段 | −10.00 … +1.30 | 上下双管（8 边形棱柱）、中间瞄准肋条、前准星柱+珠、两道管箍 |
| 弹膛段 | −2.20 … +1.30 | 管径加粗；内藏两发 12 号霰弹（`shell_upper` / `shell_lower` 驱动） |
| 护木 | −3.64 … +1.05 | 木质前托包住下管，前端金属帽 + 卡笋 + 两侧防滑纹 |
| 铰链 | Z=+1.30, Y=−0.58 | **折开旋转轴**，`barrel` 骨骼的 pivot |
| 机匣 | +1.30 … +4.44 | 立式后膛面、泄气槽、铰链耳与铰链销、侧壁刻线 |
| 操作件 | — | 开膛杆（顶部）、外露击锤、保险钮（左侧） |
| 扳机组 | Z≈+2.55 | 护圈 + 扳机片 |
| 枪托 | +4.44 … +9.44 | 胡桃木：握把（底端下垂+底盖）→ 6 段折线托身 → 黑色托底板 |

圆形件全部由 `ring()`（等价 boxlib 的 `ring`）生成：8 边形法向量沿 X/Y/Z 轴旋转的薄板拼成棱柱，
相邻板交叠 1.12 系数消缝；**没有手堆方块拼圆**。

## 3. 骨架层级与 pivot

```
root                        [0, -0.90,  5.50]   后握把（规范指定）
└─ move                     [0, -0.90,  5.50]   整体位移通道
   └─ body                  [0,  0.00,  1.30]   机匣参考系
      ├─ receiver           [0,  0.10,  2.80]
      ├─ barrel             [0, -0.58,  1.30]   ★ 折开轴
      │  ├─ forend          [0, -0.60, -1.60]
      │  ├─ barrel_upper    [0,  0.36, -4.30]
      │  ├─ barrel_lower    [0, -0.36, -4.30]
      │  ├─ rib             [0,  0.00, -5.60]
      │  ├─ extractor       [0, -0.36,  1.10]   抽壳钩
      │  ├─ shell_upper     [0,  0.36,  0.40]   上膛弹壳
      │  └─ shell_lower     [0, -0.36,  0.40]   下膛弹壳
      ├─ stock              [0, -0.80,  6.60]
      ├─ trigger_group      [0, -0.62,  2.55]   绕扳机转轴
      ├─ hammer             [0,  0.58,  4.05]   绕击锤轴
      ├─ top_lever          [0,  0.88,  2.30]   开膛杆（沿 X 平移）
      └─ safety             [0.62, 0.30, 3.55]
   ├─ magazine              （空占位组）
   │  ├─ mag_standard / mag_extended_1..3
   ├─ additional_magazine   （必须为空，且不嵌套在 magazine 下）
   ├─ constraint
   └─ camera
```

折开式霰弹枪没有弹匣，`magazine` 一组按 TaCZ 规范保留为空占位，以保证与本仓库其它枪械的骨骼清单一致。

## 4. 动画清单

`format_version 1.8.0` + `geckolib_format_version 2`，8 条 clip，**裸名**（不带 `animation.` 前缀，
与 `uzi/awm/mosin` 一致；Blockbench 的 `create_animation` 会加前缀，落位时统一剥掉）。

| clip | 长度 | 循环 | 驱动骨骼 | 动作概要 |
|---|---|---|---|---|
| `static_idle` | 2.000 s | ✅ | move | 待机呼吸浮动 + 微幅摆动 |
| `draw` | 1.000 s | — | move | 从下方举起，带过冲回弹 |
| `shoot` | 0.600 s | — | move, hammer | 双管齐发后坐（+Z 后退 0.62u + 抬头 9.5°），击锤落下复位 |
| `bolt` | 1.267 s | — | barrel, top_lever, hammer, move | 折开检查再合上（无装弹） |
| `reload_tactical` | 2.600 s | — | 6 骨 | 折开 → 左右各补一发 → 合膛 |
| `reload_empty` | 3.300 s | — | 7 骨 | **主秀**：见下方时序 |
| `ADS_up` / `ADS_down` | 0.180 s | — | move | 进出瞄准姿态 |

### `reload_empty` 折开式换弹时序（3.3 s）

| 时刻 | 事件 |
|---|---|
| 0.00–0.15 | 顶杆向右推开（`top_lever` X 位移 0.42） |
| 0.15–0.55 | 枪管绕铰链下折 **38°**（`barrel`），击锤被压到待击位（−26°），整体枪身下沉前倾 |
| 0.62–1.30 | 抽壳钩顶出两发空壳：沿膛线后退 1.3u → 下坠落 4.6u → 掉出视野 |
| 1.35–2.35 | 两发新弹从枪外下方插入弹膛（错开 0.05 s 依次入膛） |
| 2.75 | 合膛到位并**过冲 +3.5°** |
| 2.87 | 回弹 −1.2° |
| 3.30 | 归零 |

「合膛过冲再回弹」是为了 Q 弹手感刻意加的，不是插值误差。

## 5. 贴图

- 512×512 RGBA，**逐面 UV 图集**（每个面独立矩形，无自动 UV 拉伸），密度 13 px/u。
- 调色板：`gold` 枪管/机匣主金、`goldl` 高光边线/准星珠、`goldd` 肋条/管箍/接缝、
  `brass` 弹壳底/铰链销、`wood`/`woodl`/`woodd` 胡桃木三阶、`steel`/`std` 扳机组与击锤、
  `blk` 托底板、`red` 霰弹壳身、`dk` 膛口内壁与缝隙。
- 每个面按朝向乘明暗系数（up 1.14 / down 0.60 / north 1.00 / south 0.86 / east 0.94 / west 0.80），
  与 `uzi`/`awm` 同一套表，同屏光照一致；边缘压暗 0.76 提供面界线，另叠 ±7% 微噪点破平。
- 自检：**1686/1686 个面的 UV 矩形内都至少有一个 alpha>8 的涂绘像素**（0 个空白面）。

## 6. 落位与规范化

`tools/s686_install.js` 负责把 `build/` 的产物写进资源目录，途中做三件事：

1. **剥掉 `animation.` 前缀** —— Blockbench 的 `create_animation` 会把动画名写成
   `animation.static_idle`，而 GeckoLib 运行时按裸名查找、`tools/check_gun_resources.py:172-175`
   也按裸名比对 `S686Item` 的 `ANIM_` / `TRIGGER_` 常量。
2. **校验通道形状**为「时间 → 三元向量」（per-axis 嵌套会让整次资源重载失败 → 全屏方框）。
3. **逐面 UV 涂绘自检**（见上）。

## 7. 导入注意

- geo：`format_version "1.12.0"`，identifier `geometry.s686`，`texture_width/height = 512`。
- 动画：`format_version "1.8.0"` + `geckolib_format_version 2`。
- 资源路径：`geo/s686.geo.json`、`textures/item/s686.png`、`animations/s686.animation.json`。
- 时长常量（`ceil(clip.animation_length × 20)`）：`DRAW_TICKS=20`、`SHOOT_TICKS=12`、
  `BOLT_TICKS=26`、`RELOAD_TACTICAL_TICKS=52`、`RELOAD_EMPTY_TICKS=66`。
- **没有 `shoot_auto`**：折开式双管无全自动，`S686Item` 不应定义对应的 `ANIM_/TRIGGER_/TICKS` 常量。
- 导出的 geo 与 Blockbench 里看到的相比，**X 轴是镜像的**（GeckoLib 导出器对带 pivot 的元素写 −x，
  旋转的 X/Y 分量同样取反）。这个镜像全局一致，作者空间的 +X 仍是射手右侧，
  与 `uzi`/`awm` 的行为完全相同 —— 看到 `+0.42` 变成 `−0.42` 不是 bug。
