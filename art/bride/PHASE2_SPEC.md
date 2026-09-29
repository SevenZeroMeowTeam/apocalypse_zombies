# 美女僵尸 Phase 2 规格书（GeckoLib 真骨骼 + 重做得更美观）

> 任务书里写不下的长规格放这里。动手前先读完本文，再读 `meishu.md` 与十字弩的既有管线。

## 0. 一句话目标
把 BrideZombie 从 Phase 1 的原版盒子模型，升级成 **GeckoLib 真骨骼** 模型；外观要比现在**更美观**
（更精致的婚服/发髻/裙摆/腰线与手臂），走「生成器 → Blockbench 重做/精修 → Java GeoModel 换模型」的完整管线，
产出可编译、可部署、可从同一份 JSON 渲出预览图的成品。

## 1. 工程事实
- 仓库：`F:\mcmod`（Forge 1.20.1，包 `com.apocalypse.zombies`，命名空间 `apocalypse_zombies`）
- 构建：`cd /f/mcmod && ./gradlew build`（挂住时按技能里的处方处理；日志只看 ASCII 标记）
- 部署：`./gradlew build` 后把 `build/libs/apocalypse_zombies-1.1.5.jar` 覆盖到
  `C:/Users/Administrator/Desktop/.minecraft/versions/1.20.1-Forge_47.4.23-2/mods/`（备份成非 `.jar` 后缀），核对 md5
- Blockbench 5.2.1 在 `D:\Blockbench`，MCP 插件 1.8.1，端点 `http://localhost:3000/bb-mcp`，用 `mcp__blockbench__*` 工具；
  `risky_eval` 可执行 JS，但**同一段 code 串有缓存**，重跑要换标记串
- Blender 5.2.1 在 `D:/Blender/blender.exe`（`--factory-startup -b -P <脚本>` 无头渲染），也可用 Blender MCP

## 2. 必读的既有实现（照抄工程结构，不要另起一套）
- `meishu.md`（美术规范）：16u=1Block；-Z=正面、+Y=上、+X=右（铁律）；曲面部走 Generate Shape 思路；
  动画必须骨骼驱动 Translation/Rotation，**禁止整模型缩放**（显隐只用 scale 0/1）；rest 姿态全部骨骼零旋转
- **十字弩 = 本仓 GeckoLib 管线的样板**：`tools/crossbow_v2.py`（生成器）、
  `src/main/resources/assets/apocalypse_zombies/geo/crossbow.geo.json`、`animations/crossbow.animation.json`、
  `client/model/*GeoModel.java`、`client/renderer/*Renderer.java`、`ClientModBusEvents` 的注册写法
- Phase 1 视觉层（要被替换）：`client/model/BrideModel.java`、对应 renderer、`tools/bride_zombie_skin.js`（皮肤生成脚本）、
  `art/bride/bride_zombie_scene.py`（Blender 无头渲染脚本）
- 单位换算：**16u = 1 Block ⇒ 1u = 1px = 6.25cm**

## 3. 胸部规格（用户已定案，不许回退）
- 旧版 3宽×3高×2深（前伸 2px）已被用户否掉，理由是读起来像"胸前挂两块方板"。
- **现行规格：每瓣 2 宽 × 3 高 × 1 深，相对躯干正面只前伸 1px（≈6.25cm，占躯干厚 4px 的 25%），两瓣间留 1px 中缝，左右对称。**
- 重做时可以换成多块拼出的更圆润体块，但**凸出量上限仍是相对躯干正面 1px**，且不许用整模型缩放造效果。
- UV 必须自洽（两瓣 UV 不许相叠），左右镜像正确（内侧领口肤色 / 外侧发丝这类细节的镜像方向要对）。

## 4. 边界（绝对不许碰）
- 十字弩的一切文件（`tools/crossbow_v2.py`、`geo/crossbow.geo.json`、`crossbow.animation.json`、弩相关 Java/资源）
- BrideZombie 实体的 id / 类名、**三套技能轮转与召唤的逻辑与数值**、lang key、掉落表、音效注册
- 你只换「视觉层」：model + renderer + 对应 geo / anim / 贴图资源（贴图路径可换，但要同步所有引用）
- 不要在 `art/bride/` 之外改渲染脚本

## 5. 交付物
1. 生成器 `tools/bride_v2.py`：产 geo + animation JSON，确定性可复跑，自带自检并打印 sha256
2. `src/main/resources/assets/apocalypse_zombies/geo/bride_zombie.geo.json` + `animations/bride_zombie.animation.json`
3. 贴图（含生成脚本；尺寸与 geo UV 自洽，路径改动要同步 Java）
4. Java：`GeoModel` + `GeoEntityRenderer`，并在 `ClientModBusEvents` 注册；替换掉旧模型/渲染器的使用
5. `art/bride/*.bbmodel`（Blockbench 工程）+ 从**同一份 geo JSON + 同一张贴图**渲出的预览图

## 6. 动画组（必须齐全）
- 静置 / 行走（至少一套基础循环）
- **三套技能轮转各自的动作**（与现有技能逻辑一一对应，名字要与 Java 触发处一致）
- 召唤动作
- rest 姿态所有骨骼零旋转；全部骨骼驱动（Translation/Rotation）；显隐只用 scale 0/1

## 7. 验收（每项都要给可核对的命令输出，不要只写"通过"）
1. `./gradlew build` 成功；jar 覆盖进 mods 目录，且 mods 里 jar 的 md5 == `build/libs` 产物 md5
2. jar 内能列出：新 geo json、animation json、贴图 png，以及重编后的 GeoModel/Renderer class
3. 动画组齐全、clip 名与 Java 触发处逐字一致（契约校验脚本，参考弩的写法）
4. Blender 无头从同一份 geo + 同一张贴图渲出：全身正/侧/四分之三 + 胸部特写，落到 `F:\mcmod\art\bride\`；
   交付时给出图片**绝对路径**。禁止手工摆拍或换模型冒充
5. Blockbench 里打开 geo 做一次校验（骨骼数/尺寸/UV 无越界），`.bbmodel` 存到 `F:\mcmod\art\bride\`
6. 生成器可复跑出同样结果（`art/` ↔ `src/` 两份 sha256 一致）

## 8. 汇报格式
中文；包含：改了/新增了哪些文件（绝对路径）、每条验收的**实际命令输出摘要**、
胸部在新模型里的实际数值、预览图绝对路径、以及没做/被阻塞的部分。**不要编造输出，拿不到就明说。**