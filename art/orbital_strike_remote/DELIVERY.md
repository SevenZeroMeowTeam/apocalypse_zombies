# 1.2.5 交付台账 —— 轨道打击遥控器（天基炮，科幻武器）

出货日期：2026-10-17
产物：`apocalypse_zombies-1.2.5.jar`

## 用户原话

1. `新增科幻武器开关手持开关选取地区，添加炫酷的特效，从宇宙之外发射动画及破坏地形`
2. `可以对生物造成大量伤害有几率秒杀`

## 资产清单（本目录）

| 文件 | 尺寸 | 用途 |
| --- | --- | --- |
| `textures/item/orbital_strike_remote.png` | 16×16 RGBA | 物品栏 / 手持图标：一个卫星通信器（顶部红色信号灯 + 金属机身 + 青色屏幕 + 深色底座） |

> 本资产**不走 GeckoLib 通道**（无 geo/、无 .bbmodel、无动画），是普通 16×16 物品图标。
> `tools/art_audit.py` 的 A~G 体检项只覆盖 `geo/` 目录，所以这个资产不参与该体检 ——
> 它的「自检」是 `tools/art_audit.py` 不认识的普通 PNG 尺寸/透明度校验，见下。

## 生成方式

`tools/` 下没有专用脚本：图标由 PowerShell + `System.Drawing` 一次画成，画法已固化在
1.2.5 出货脚本里（16×16 逐像素表：`0`=透明/`1`=深灰边线/`2`=金属灰/`3`=青蓝屏边/`4`=青白高亮/`5`=红色信号灯）。
可复现的像素表与代码在 `tools/_deploy_125.py` 的 `draw_icon()` 里；重新生成即得到同名同尺寸的 PNG。

## 代码侧对应

- 物品注册：`registry/ModItems.java` 的 `ORBITAL_STRIKE_REMOTE`
- 物品行为：`item/OrbitalStrikeRemoteItem.java`（右键 use → 取准星 BLOCK → 调度）
- 服务端主循环：`event/OrbitalStrikeManager.java`（锁定 → 下落 → 落地，摧毁 + AOE + 秒杀）
- 客户端视觉：`client/renderer/OrbitalStrikeHighlighter.java`（选区立方体 + 光柱 + 圆环/冲击波）
- 网络包：`network/OrbitalStrikePacket.java`（S2C，目标点 + 半径 + 锁定 tick）
- 配置：`Config.java` 的 `orbital_strike` 段（7 项，全可一键关）

## 校验

- `tools/art_audit.py` 无新增坏项（该资产不在其覆盖范围）。
- 出货门禁 `tools/_deploy_125.py`：图标是 16×16、RGBA、有透明像素；jar 内包含
  `OrbitalStrikeRemoteItem` / `OrbitalStrikeManager` / `OrbitalStrikeHighlighter` / `OrbitalStrikePacket`
  四个新符号；`mods.toml` 版本 = 1.2.5。

## 未做 / 未验证

- **未在真实客户端实测**：选区立方体、下落光柱、地面冲击波、秒杀判定都只过了静态编译，
  没有在游戏里看过一眼。需要进游戏验证（见 readme 1.2.5 的「验证」段）。
- 图标是 16×16 手画像素图，放大后边缘会有锯齿 —— 原版风格一致，不额外处理。
