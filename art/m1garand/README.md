# M1 加兰德（M1 Garand，.30-06）— 资产说明

生成链路：`tools/m1_garand_bb_gen.js`（几何 + 512² 图集）→ `tools/m1_garand_bb_anim.js`（动画）
→ Blockbench `geckolib_model` 编解码器导出 → `art/m1garand/m1_garand.{geo,animation}.json`
→ `tools/m1_garand_bb_audit.js`（数值自检）→ `tools/check_gun_resources.py`（接线自检）。

## 文件

| 文件 | 说明 |
|---|---|
| `art/m1garand/m1_garand.bbmodel` | Blockbench 工程源文件（可继续微调，导出前必须先跑自检） |
| `art/m1garand/m1_garand.geo.json` | 几何（GeckoLib Animated Model，14 骨 / 346 方块） |
| `art/m1garand/m1_garand.animation.json` | 动画（6 段，GeckoLib 可直接读） |
| `art/m1garand/m1_garand_geo.png` | 512×512 逐面 UV 图集 |
| `art/m1garand/_anim_raw.json` | 关键帧中间产物 |
| `tools/m1_garand_bb_gen.js` | 几何 + 贴图生成器（在 Blockbench 内经 MCP `risky_eval` 执行） |
| `tools/m1_garand_bb_anim.js` | 动画生成器（同上） |
| `tools/m1_garand_bb_audit.js` | 数值自检（同上，输出 JSON） |
| `tools/check_gun_resources.py` | 接线自检（在仓库根跑，两把枪一起验） |

音效**不在本目录**：这把枪暂时触发 AWM 那批录音，见下文「声音」。

## 贴图缺失导致的"黑块"（2026-09-23 修复）

**症状**：游戏里枪身大片发黑（枪管、木托侧面最明显），但几何、动画、UV 都正常。

**根因**：生成器第 9 步只把图集写到 `art/m1garand/m1_garand_geo.png`，
`src/main/resources/.../textures/item/m1_garand.png` 靠手工拷贝，而资源目录里那份一直是
**更早的、被截断的旧导出**：旧图只画到 V=237，模型 UV 却用到 V=322
→ **1514/2076 个面**（其中 295 个外露面）采到全透明区，在游戏里渲染成纯黑。
线索是文件大小：旧图 149,092 B，与本文档记录的 120,932 B 不符。

**修复**：把生成器的权威图集装回资源目录（旧图留档 `m1_garand.old-resource.bak.png`），
并让生成器第 9 步**同时写 `art/` 与资源目录**，从根上避免再次漂移。

**新增断言**：`check_gun_resources.py` 现在逐面核对 UV 是否落在涂绘像素上
（自己解 PNG，不引入 Pillow）。判据是**每个面的 UV 矩形内至少有一个 alpha>8 的真彩像素**；
旧图上它报 1514 个面，修好后 0 个。顺带修掉了它对刷怪蛋报的 4 条假失败
（`ForgeSpawnEggItem` 没有 GeoModel，本就不是枪）。

**姊妹缺陷（2026-09-23 已修）**：AWM 的图集**同样不完整** —— 1549/2610 面空白，其中 485/890 是外露面
（`scope` 102、`barrel` 89、`scope_wind` 70、`body` 58、`scope_elev` 56、`bolt` 55）。
它的 `art/awm/awm.png` 与资源副本**字节一致**，所以不是漏拷，而是图集自身缺一块
（图只画到 V=388，而模型 UV 用到 V=453）。
按"只回填贴图、不动几何/动画"处理：`tools/awm_tex_fill.py` 用生成器自己的**色板**
（`tools/awm_bb_gen.js` L29-38 的 `MAT`）与**绘制公式**（L296-314）逐像素回填，
只写原本全透明的像素，并断言所有已涂绘像素**逐字节不变**。
材质逐方块判定（用方块自己已涂绘的面反查色板，实测中位误差 3.1），环形件等判不出的
用"同骨多数材质 / 生成器部件尺寸表 / 生成器兜底"补齐，**没有任何一块落到"未知"**。
检查器现在对 AWM 报 **0 空白面**（2610 面全覆盖）。旧图留档 `art/awm/awm.pre-fill.bak.png`，
对比图 `art/awm/tex_fill_compare.png`。

## 实测数字

来自 `tools/m1_garand_bb_audit.js`，`fails: [] warnings: [] ok: true`：

| 项 | 值 |
|---|---|
| 全长 | 17.63u = **1.102 格**（bbox Z −13.60 … +4.03；真机 1100mm → 误差 0.17%） |
| 高 / 宽 | 3.37u / 0.92u（真机整体 208.8mm / 45mm；宽度含背带环与导气杆手柄） |
| 方块 / 骨 | 346 / 14 |
| 贴图 | 512×512（导出 PNG 120,932 B） |
| 瞄准线 | `2.80`（= 膛线轴 +31.5mm；前准星刃顶 2.80 与后照门孔心 2.80 互校） |
| 枪口 | `{0, 2.30, −13.60}` |
| 抛壳路径点 | `{0.30, 2.62, −1.63}`（工程空间 +X = 右侧抛壳窗内；窗内中心 748mm） |
| 密度 | `12`（规范值 11~13） |
| 色板 | `MAT.steel/park/parkd/blue/blued/wood/woodd/dark/blk/brs/cpr`，值同 `美术规范.md` 三·1 |

## v6 修正（2026-10-01）：按真机换弹重做四项（A/B/C/D）

用户要求「参考现实 M1 加兰德换弹进行优化或者修改」，四件事一起做：

**A 抽手空档 + 音效重排 + 战术跳壳（纯动画 + 纯 Java）**

- `reload_empty`：新漏夹 **1.2917 s 落位**之后，原来 **1.375 s** 枪机就前冲（只隔 0.083 s = 2 帧）。
  现在推到 **1.4583 s**（落位后 4 帧：松压 + 手撤离），掌根拍到位随之到 **1.75 s**；
  枪身反作用 `body`（1.5417 / 1.8333）与枪机蹭动 `move` 跟着新释放时刻重排。
- `reload_tactical`：补上膛内那发**活弹被抛出去**（复用 `shoot` 的抛壳曲线，0.2917 → 0.6667 s，
  `casing` 全段 scale 0 的旧毛病一并消掉）；枪机释放同口径推后（**1.0417 → 1.2083 s**，
  落位 1.0 s 之后留 5 帧抽手）。
- Java 音效逐条按新节拍重排：叮对齐 **t=11（0.55 s）** = 空夹脱离井口起飞那一瞬
  （**不是**到顶的 0.96 s）；`BOLTCLOSE` 从 t=36（1.80 s）移到 **t=35（1.75 s）**（枪机真正落位）；
  战术段 `MAGIN` 对齐落位 **t=24**、`RECHAMBER_OUT` 移到 t=29（前冲起步）、补一条 t=36 闭锁音。

**B 卡榫真机化（动几何）**

半满漏夹**不会自己掉出来**——手册原话 "Do not relax the rearward pressure on the operating rod
handle until after the clip has been removed"：必须把导气杆拉到底并**保持按住**，左手按机匣
**左侧**的漏夹卡榫销，残夹才脱出。几何新增**第 15 根骨 `clip_latch`**（`tools/m1_garand_latch_geo.py`）：
parent `body`、pivot `(0.32, 1.72, −2.36)`、1 个方块 `origin (0.32, 1.62, −2.46) size (0.09, 0.16, 0.20)`
（贴机匣左侧壁 x=0.32 外凸 0.09u ≈ 5.6 mm；真机卡榫销在左、导气杆在右 —— 本模型导气杆在 −X，
所以销子放 **+X**，左右关系与真机一致）。时序：**0.2917 s 按下**（拉到底之后才按得动）→
**0.7917 s 松开**（新夹进来之前回位），按入 **0.06u = 3.8 mm**（导出空间为 −x）。

**C 行程真机化（纯动画，几何不动）**

原来 `bolt` / `shoot` / 两段换弹都只走 **1.10u = 69 mm**。枪机面要退过漏夹末弹底缘，最小量 =
.30-06 全弹长 **84.8 mm ≈ 1.36u** ⇒ 全部拉到 **1.36u**（`shoot` / `bolt` 按各自峰值等比归一）。
**几何不用改**：枪机组尾面 z −1.760 + 1.36 = −0.400，机匣尾面 z 0.448，余量 0.85u。
（旧注释把 1.10u 写成"模型几何上限"，实测不成立，已订正 —— 门禁里那条断言也改了。）
`M1GarandGeoModel.BOLT_TRAVEL` 同步 1.10 → 1.36，否则第一人称的手会停在手柄中段。

**D 单发补弹 `single_load`（新剪辑 + Java 分支）**

手册 "To load a single round"：拉到底（抛掉膛内活弹）→ 手放一发送进膛 → 按托弹板 →
手扶着机柄让枪机**可控地**闭锁（不是自由前冲）。新段 **1.5 s / 30 t**：`casing` 走两次
（0.2917 s 抛旧弹、0.7083 s 送新弹），井里的漏夹全程不可见（`clip_in` 不动）。
入口 **Shift+R**：`ReloadPacket` 带 `single` 布尔，`GunItem.beginReload(..., boolean)` 是
`default` 方法（别的枪不碰）。弹药结算 **+1 发**，不是满夹。

**真源链**：本次是**真源 dump + 生成器**双改 —— `art/m1garand/_anim_raw.json` 的 `clip_in`
z 仍留着旧值（0.3 / 1.1 / 1.7…），只补导出产物的话谁重跑一次导出就把横滑带回来。
`tools/m1_reload_real.py`（幂等，`--check` 可验）负责真源侧四项；`_anim_raw.json` 的写盘格式
与生成器 `JSON.stringify(dump, null, 1)` 逐字节同构（1 空格缩进、数字 4 位、整数不写小数点），
所以 diff 只剩真实改动（777 增 / 52 删）。

**核验**：`python tools/check_m1_reload.py` 新增几何余量 / 卡榫机构 / `single_load` 三组断言
（含"漏夹落位后有抽手空档 ≥2 帧"），全部通过；`check_gun_resources.py` / `check_mosin_anim.py` /
`reload_press_vertical.py --check` 同样全绿。

## v5 对齐（2026-09-30）：生成器与 `art` 补成纯竖直

莫辛那次「换弹压入件只走竖直」（见 `art/mosin_nagant/README.md`）顺带翻出 M1 的两笔历史欠账 ——
**出货件与生成器早就各说各话**：

| 事实 | 状态 |
|---|---|
| `src/main/resources/.../m1_garand.animation.json` 的 `clip_in` | **一直是 z = 0**（纯竖直），游戏里观感没问题 |
| `art/m1garand/m1_garand.animation.json` 的同一通道 | z 仍是旧值（0.30 / 1.10 / 1.70 / 0.12 …，共 9 帧） |
| 生成器 `tools/m1_garand_bb_anim.js` 的同一通道 | z 也是旧值（0.28 / 1.12 / 1.85 …） |
| 同一文件里 3 处 `keys()` | **少一个 `]`，整份文件 parse 不过** —— 生成器其实早已跑不起来 |

后果：谁重跑生成器，谁就把「漏夹沿枪身横滑」的毛病带回来（真源名存实亡，历史修复全靠手改 JSON）。

本次：生成器 z 全改 0、补回 3 个 `]`（`node --check` 通过）；`art` 那份对齐出货件的 0 值。
验收：`git diff` 只有 9 行、每行只差 z 一个数；`tools/check_m1_reload.py` 全过；**出货件（`src`）一个字节未动**。

## v4 修正：漏夹井真机标定（2026-09-23）

**症状**：游戏里漏夹（连带弹夹井与漏夹盖）整体**靠前约一个井长** —— 用户在截图里把当前漏夹处
框成红框、把"应该在的位置"框成黄框，注明「弹夹位置不在这个位置在黄色方框位置……
打完滑动后面，压下弹夹自动平移合上，弹壳从黄色方框上方抛出」。

**标定**（`ref_m1_side.png` 逐列分类木/金属，剪影全长 1105mm 定标）：

| 锚点 | 量取值 | 与模型对照 |
|---|---|---|
| 机匣前缘（木护木 → 金属） | 577mm | 模型 519mm（见下"遗留偏差"） |
| 机匣后缘（金属 → 木托颈） | 798mm | 模型 Z(799) ✓ |
| 后照门座 / 拉机柄（op-rod 折柄）前沿 | 700mm | 模型 Z(700) ✓ |
| 闭锁面 = 枪管 24" | 610mm | 井前壁应落在此 |
| 扳机护圈环 | 718–790mm | 真机 LOP 13" → 扳机 ~770mm，与量取互证 |

⇒ **井 = 601…700mm**：前壁 = 闭锁面 610mm，后壁贴后照门座/拉机柄前沿 700mm（模型内可自证的锚点）。
旧值 519…618mm 正好靠前一个井长 —— 成因是 v3 把参考图里"木护木 / 木托颈"的边界当成了机匣前缘，
于是把井前壁钉在机匣前缘上。真机机匣实长 221mm，模型 280mm。

**改动**（`tools/m1_well_shift.py`：几何 + 动画同批，幂等，`--check` 可预演；
对照图由 `tools/m1_well_overlay.py` 生成 → `art/m1garand/well_fix_overlay.png`）：

| 对象 | 改动 | 说明 |
|---|---|---|
| 井组 5 方块 `well_l/r/f/b` + `well_cav` | Δz **+1.312u（+82mm）** | 井 → Z −3.984…−2.400 |
| 机匣桥面 `brg_top` | 起端 Z(652) → **Z(700)** | 井口让开，桥面改从井后壁起 |
| 漏夹盖 `cover`（3 方块） | Δz +1.312u | pivot 留在 Z(799)（机匣后端上缘 = 固定基准，动作纯平移） |
| 漏夹 `clip_in`（56 方块） | Δz +1.312u | pivot = 自身中心，随几何 → Z −3.312 |
| 弹壳 `casing`（24 方块） | Δz **−0.752u（−47mm）** | 静止位从抛壳窗后沿外（795mm）移到窗内中心（748mm） |
| `clip_in` 动画（两段换弹） | 旋转清零 + 位移 x **与 z** 归零 | 用户要求「平移」：装填不得翻转、也不得横滑（蓝轴 = 前后）；y 保留，仍是垂直压入。出货件当时已是 z=0，生成器与 `art` 到 2026-09-30 才补齐（见 v5） |
| `M1GarandGeoModel.CLIP`（Java） | z −4.60 → **−3.29** | 手部按压目标点 |
| `bolt_chan`（枪机通道） | **不动** | 首版工具误把它当井内腔搬走，已回填并加断言 |

**落位核对**：漏夹 z −3.924…−2.564 ⊂ 井 −3.984…−2.400；漏夹盖 z −3.984…−2.400 正压井口；
弹壳 z −2.112…−1.212 ⊂ 抛壳窗 −2.400…−0.880。三处同源把关：工具内不变量断言、
`check_gun_resources.py`（接线）、`m1_garand_bb_audit.js` 的装配合位（新加"弹壳必须在抛壳窗内"）。

**遗留偏差（本次未动）**：模型机匣前缘仍在 519mm（真机 577mm），机匣比真机长 58mm ——
那是枪管/护木/枪机整段的既有排布，改它要动上百方块与贴图 UV，不在本次范围。

## v3 重做：按真机 1:1（v2 的三处结构性失真）

v2 的几何是**估的**，实测后误差很大。v3 全部坐标来自 `ref_m1_side.png`（维基共享官方侧视图）
**逐列量取**，定标：剪影全长 2281px = 1100mm。

| v2 失真 | 真机 | v2 | v3 |
|---|---|---|---|
| 机匣位置 | 577–798mm（实长 221mm） | 706–919mm（枪管长 19cm、托颈短 19cm） | 519–799mm（280mm；v4 只修了井，见"遗留偏差"） |
| 瞄准线 | 膛线轴 +31.5mm | `3.10`（+50mm，高估 19mm） | `2.80`（+31.5mm） |
| 高 / 宽 | 208.8mm / 45mm | 3.76u / 1.72u | 3.37u / 0.92u |

同批修掉的真实缺陷：

- **枪管被护木包住**：真机除枪口冠面外枪管全在护木/导气筒内，v2 露着裸枪管。
- **上护木做成圆管**（图元 `ring`）而不再是一块方木；下护木沿 Z 六段细分锥面（无「梯田」台阶）。
- **木纹按世界坐标采样**，跨方块连续 —— 整根托读成一块木头，不是一叠木板。
- **托底下沉**：真机托底下缘 −176.5mm（−0.52u），v2 是平的。
- **机匣尾座补上**：799–827mm 那段真机是金属，v2 空缺（机匣与托颈之间露缝）。
- **导气杆推到与护木侧面齐平**（X 0.28–0.42）：v2 埋在木托里，加兰德最好认的特征看不见。
- **漏夹井改 100mm（519–618mm）**、漏夹 85mm 正好落位；v2 井 133mm，漏夹尾部越出井体。
  ⚠️ **v4 已修正为 601–700mm** —— 519–618 是按"机匣前缘 = 木/木边界"推的，靠前一个井长，见上一节。
- **抛壳几何在 +X 抛壳窗内**（工程空间 +X = 射手右侧，见下文手性说明）。

## 规范对齐（`美术规范.md`）

- 16u = 1 block；枪口 = **−Z**，上 = **+Y**，原点 = **机匣中心**。
- 圆形件一律由图元生成（枪管及其附件 102 个方块是分段圆管 + 环，无手工拼圆）。
- 动画只用骨骼 **rotation / position**；隐藏件用**本骨** `scale 0`（漏夹 / 弹壳 / 新弹），从不整体缩放。
- 骨名：`root / move / body / barrel / bolt / cover / clip_in / magazine / casing / trigger / stock /
  additional_magazine / constraint / camera`（后三个是 TaCZ 约定的挂载空组，导出时保持空）。

**X 手性（重要，容易看错）**：Blockbench **工程空间**与导出的 `geo.json` **X 相反** ——
工程里 `bolt` pivot `+0.26`，geo 里是 `−0.26`；`casing` 同理 `+0.30 → −0.30`（Y/Z 不变，是纯 X 镜像）。
所以导出后枪栓与抛壳窗和 AWM 同在 **−X** 侧，两把枪手性一致，导气杆手柄落在**射手右侧**——
正是真加兰德的样子。`美术规范.md` 换算表里「+X = 射手右侧」与发布数据不符，与 AWM 的待办 8 是同一条。

## 动画（7 段，全部原创）

| 名称 | 时长 | 循环 | 说明 |
|---|---|---|---|
| `static_idle` | 2.0 s | loop | 持枪待机 |
| `draw` | 1.0 s | once | 掏枪（尚未接线） |
| `shoot` | 0.6 s | once | 后坐 + **枪机自循环**：真加兰德半自动，导气杆随每发自己前后走一遍（**全行程 1.36u**），不需要额外拉栓动作 |
| `bolt` | 1.1 s | once | 手动拉导气杆（纯平移，**全行程 1.36u**） |
| `reload_empty` | 3.0 s | once | 空仓：**先把枪机拉到底并挂住**（不拉到底，井口被枪机挡死，漏夹压不进去）→ 漏夹盖抬起 → 空漏夹向上弹飞（真机标志性的 **ping**）→ 新漏夹自上而下压入弹夹井（**纯平移，不翻转**）→ 盖合 → **落位后留 4 帧抽手**（松压 + 手撤离）→ 枪机被漏夹**自动释放**前冲 → 掌根拍拉机柄后端到位闭锁（1.75 s） |
| `reload_tactical` | 2.6 s | once | 未空仓：**先拉到底并保持按住**（松手残夹会掉，手册原文见 v6）→ 膛内**活弹被抛出** → 左手**按下卡榫销**（`clip_latch`，0.2917 s）→ 残夹脱出 → 新漏夹自上而下压入（**纯平移**）→ **松卡榫**（0.7917 s）→ 留 5 帧抽手 → 枪机自动前冲 → 拍到位闭锁 |
| `single_load` | 1.5 s | once | 单发补弹（Shift+R）：拉到底、抛掉膛内活弹 → 手放一发送进膛 → **扶着机柄可控闭锁**（不是自由前冲）；不动漏夹 |

**与 TaCZ 的关系和 AWM 不同**：动作**取名**沿用通用步枪那套，但运动按**真机机构**重写，
**没有逐键转录** TaCZ 的任何数据（`grep -i tacz tools/m1_garand_bb_*.js` 只剩「空组命名约定」一处）。
上面两段换弹的机构描述就是脚本的行为依据。

**真机依据（2026-09-23 换弹 / 拉栓微调）**：动作顺序按 M1 加兰德野战手册"装填"四步 ——
① 右手握导气杆手柄拉到底（枪机后退并挂住）② 漏夹对准弹夹井垂直压下直到卡住
③ 松手，枪机被漏夹**自动释放**、自由前冲 ④ 必要时用右手掌根拍拉机柄后端确保闭锁。
**关键修正**：旧版两段换弹都把枪机留在闭锁位、只动漏夹，而真机此时井口被枪机挡死 —— 压不下去。
现在两段都是"先拉到底并保持 → 漏夹到位 → 才自动前冲"，第 ④ 步做成前冲末端的减速节拍
（`0.88 → 0.5 → 0.2 → 0.06 → 0`，读数取自导出后的 JSON）。枪机后退量见 **v6**：
全行程 **1.36u = 85 mm**（.30-06 全弹长 84.8 mm 是"退过末弹底缘"的下限）；旧值 1.10u = 69 mm 不够，
当时误当成"几何上限"。

**导出链**：MCP 的 `geckolib_*` 导出工具在本机工程状态下被禁用，改用确定性链路：
`tools/m1_garand_bb_anim.js`（生成器顺手把原始关键帧写进 `art/m1garand/_anim_raw.json`）
→ `tools/m1_anim_export.py`（raw dump → GeckoLib JSON，复刻插件导出规则：24 fps 吸附、
单键通道写静态缩写、多键写 `post` + `lerp_mode`、左右手系翻转 position `[−x,y,z]` / rotation `[−x,−y,z]`）。
**转换器的正确性用"未改动的动画必须逐字节重现出厂文件"来验证**：`static_idle` / `draw` / `bolt`
三段与改动前逐字节一致，`shoot` 只差枪机通道、两段换弹是预期重写 —— 差异全部可解释才写盘。

**踩过的坑**：关键帧是在**导出时**才按 24 fps 吸附（半点进位），相隔 < 1/24 s 的两个键会在导出时并到
同一帧而被丢掉。旧漏夹"消失"与新漏夹"出现"那对 `scale` 键（0.98 / 1.02）正好一起落到第 24 帧，
表现为漏夹永不消失、位置从"飞走"插值回"压入"划出一道弧。现在**生成器写入时就吸附并检测撞帧**
（撞帧打 `KEYFRAME COLLISION` 警告），这对键直接写成帧对齐的 `1.0` / `25/24`。

**v6 起不再是"演绎"**：战术换弹按真机机构做（拉到底并保持 → 抛活弹 → 按卡榫 → 残夹脱出 →
新夹压入 → 松卡榫 → 抽手 → 前冲）；半满漏夹**不能**直接补满这件事仍然成立，但玩家有了手册里的
**单发补弹**（Shift+R，`single_load`）：不动漏夹，只在膛里加一发。两条路都保住了。

**时长契约**：Java 的 `*_TICKS` 必须等于 clip 长度 × 20 —— `tools/check_gun_resources.py` 逐条核，
当前 `shoot 12 / bolt 22 / reload_tactical 52 / reload_empty 60 / single_load 30` 全部相等。
改动画时长必须同一个提交里改 Java。

## 自检

数值自检在 Blockbench 内跑（MCP `risky_eval`）：

```bash
python tools/bbmcp_call.py call risky_eval '{"code":"(function(){var fs=require(\"fs\");return (0,eval)(fs.readFileSync(\"F:/mcmod/tools/m1_garand_bb_audit.js\",\"utf8\"));})()"}'
```

覆盖：锚点核对 / pivot 到自身几何最近距离 ≤ 4u / 抛壳点在 +X / 骨骼旋转为零 / 方块与骨骼预算。

**它抓到过一个真 bug**：扳机（`trigger`）最初按「相对骨枢轴的局部坐标」填，整根落到护圈**下方**，
又被那 6° 旋转带到护圈**后面**（实测 Z 最小 −0.34，护圈内腔只到 0.34）。改成三段**绝对坐标**、去掉旋转后
落在护圈内腔 `X ±0.09 / Y 0.36…1.28 / Z 0.42…0.68`，pivot 一并移到 `(0, 1.30, 0.60)`。
为此加了**装配合位**断言（含入式检查：关键件必须落在容器腔内），这类错现在会在改动**之前**就变红。

接线自检在仓库根跑，两把枪一起验：

```bash
python tools/check_gun_resources.py     # 路径存在 / 骨名对齐 / ANIM_ 常量 / 512² / damage_type / lang / 时长契约
python tools/check_m1_reload.py         # M1 换弹/拉栓机构自检：真机顺序不变量（先拉到底→漏夹到位→自动前冲→拍击）
                                        #   + 全行程 1.36u 与几何余量 + 卡榫机构 + single_load
                                        #   + 落位后有抽手空档（≥2 帧）+ scale 只出现 0/1（禁止整体缩放）
```

## Java 侧（已接入）

| 文件 | 作用 |
|---|---|
| `item/GunItem.java` | **枪械接口**：余弹 / 弹匣容量 / 开镜 FOV / 抬枪时长 / 是否画镜筒 / 抬枪位移 / 第一人称放大 / 开火 / 换弹。发包、HUD、开镜只认它，所以加枪不用碰管道 |
| `item/M1GarandItem.java` | `extends Item implements GeoItem, GunItem`；服务端权威状态机（弹药、动作锁、命中判定），时长常量与 clip 同源 |
| `client/model/M1GarandGeoModel.java` | `GeoModel<M1GarandItem>`，三条路径显式指向 `geo/` `animations/` `textures/item/` |
| `client/renderer/M1GarandItemRenderer.java` | `GeoItemRenderer<M1GarandItem>`；手持取景由 `models/item/m1_garand.json` 的 `display` 控制，开镜时照枪自己的 `adsX()/adsY()` 抬枪，第一人称另按 `M1GarandItem.FIRST_PERSON_SCALE` 整体放大（加在姿态链上游，只作用于第一人称） |
| `client/GunAimState.java` | 纯客户端瞄准状态（原 `AWMClientState` 泛化而来，改成认 `GunItem`：FOV 与抬枪时长都由枪给） |
| `network/FirePacket.java` / `network/ReloadPacket.java` | 只认 `GunItem`，因此 M1 与 AWM 共用同一套请求 |
| `registry/ModItems.java` | 注册 `apocalypse_zombies:m1_garand`，加入原版「战斗」创造栏 |
| `data/apocalypse_zombies/damage_type/m1_garand_bullet.json` | 专属伤害类型 + 死亡讯息 |
| `models/item/m1_garand.json` | `parent: builtin/entity` + 各视角 `display` 变换 |

NBT 字段与 AWM 同名同义：`Ammo / Pending / PendingAt / Action / ActionAt / LockedUntil`。

**半自动的实现差别**：AWM 打一发要接一段 `bolt`；M1 的 `shoot` clip 自带枪机循环，
所以 `tryFire` 只记一个 `ACTION_SHOOT`（拿它的机械音效与 0.6 s 锁），**不**再排拉栓动作。
打空仓时只出空击声，不排任何动作。

## 声音（借用，见仓库根 `NOTICE.md`）

这把枪**没有**自己的录音，全部触发 `registry/ModSounds` 里那批 TaCZ AWM 文件（CC BY-NC-ND 4.0）：
枪声 `awm_shoot` / `awm_shoot_3p`（射手听近版，64 格内其他玩家听远版），拉栓四音，换弹八音，
空仓的「叮」用 AWM 的 `awm_reload_eject` 顶替。**时刻表在 `M1GarandItem.java`**，与 clip 对齐，
所以音效永远落在动作上——但**音色不是加兰德**，这是明知的临时状态。

换成真加兰德录音只需要改资源：加 `sounds/m1_garand/*.ogg` + `sounds.json` 事件 id，
把 `M1GarandItem` 里四张表改指过去，**Java 逻辑一行不用动**。

## 游戏内自检

```
/give @s apocalypse_zombies:m1_garand
```

- **左键** = 开火，0.6 s 一发（12 ticks），按住按此节奏连发；打空只出空击声。
- **右键（按住）** = 机瞄：0.2 s 抬枪，视场角收到 **50°**；机瞄不画镜筒、**保留原版准星**。
- **R** = 换弹：膛内有弹走 `reload_tactical`（2.6 s，含卡榫与抛活弹），打空走 `reload_empty`（3.0 s，含 ping 与自动闭锁）。
- **Shift + R** = **单发补弹**（`single_load`，1.5 s）：不换漏夹，只在膛里加一发（余弹 +1，上限 8）。
- 静止时 `static_idle` 循环。

弹道是真判定：从眼睛拉一条 160 格射线，先撞方块，沿途最多穿透 **2** 个生物；
伤害分档 40 格内 15 / 120 格内 13 / 再远 10，爆头 ×2（命中点高于目标身高 82% 即算）。

**这些数字是本项目自己定的，不是转录**：M1 用 .30-06 M2 普通弹，射程与穿透都低于 AWM 的 .338 拉普阿，
所以取 15/13/10 配 2 穿透、160 格，与 AWM 的 24/21/15 配 4 穿透、256 格拉开档次。

## 待办

1. **`WeaponMount` 常量类**（`美术规范.md` 要求与几何 pivot 一一对应同步），值取自 geo 空间：

   **（v4 重测）** 表内为 `src/main/resources/.../geo/m1_garand.geo.json` 的 pivot 实测值（发布空间，X 已镜像；
   Blockbench 工程空间 X 取反）。旧表是 v2 时期的估计值，与模型对不上，已按模型逐骨重取：

   | 常量 | geo 值 |
   |---|---|
   | `WeaponMount.ROOT` / `MOVE_PIVOT` | `(0, 1.90, −3.06)` |
   | `WeaponMount.MUZZLE` | `(0, 2.30, −13.60)` |
   | `WeaponMount.SIGHT_Y` | `2.80` |
   | `WeaponMount.EJECT`（`casing` pivot，弹壳中心） | `(−0.30, 2.62, −1.63)` |
   | `WeaponMount.BOLT_PIVOT` | `(−0.26, 2.49, −2.60)` |
   | `WeaponMount.COVER_PIVOT` | `(0, 2.56, −0.82)` |
   | `WeaponMount.CLIP_PIVOT` | `(0, 2.20, −3.31)` |
   | `WeaponMount.MAGAZINE_PIVOT` | `(0, 1.40, −2.72)` |
   | `WeaponMount.TRIGGER_PIVOT` | `(0, 1.47, −0.70)` |
   | `WeaponMount.STOCK_PIVOT` | `(0, 1.87, −0.37)` |
   | `WeaponMount.BARREL_PIVOT` | `(0, 2.30, −5.30)` |

   Java 侧取用时符号规则与 AWM 的 `WeaponMount` 表一致（X 取反），目前 AWM 那套也还没落成类。

2. 第一人称尺寸由三个数共同决定，都是**按几何算出来的起始值**，进游戏按手感微调：
   `models/item/m1_garand.json` 的 `display.firstperson_*`（基础 `scale 0.82`）、
   `M1GarandItem.FIRST_PERSON_SCALE`（第一人称再整体放大 1.25×）、
   `M1GarandItem.ADS_X / ADS_Y`（开镜抬升：内收 0.475 格、上抬 0.346 格）。
   机瞄要求"照门孔心—准星刃顶"与视轴**共线**，三件事缺一不可：
   ① hip 姿态的偏航/俯仰/滚转必须归零（`GunPose.matrix` 里那三项随 aim 线性消失）；
   ② 物品模型 `display` 的 `rotation`（2° 俯仰 / 4° 偏航，绕在姿态链**内侧**）必须被精确抵消 ——
      不抵消的话前后照门永远只是"平行但偏轴"，偏 4.47°，这一项**任何位移都消不掉**（只会随距离放大）；
   ③ 只有在 ①② 之后，`ADS_X / ADS_Y` 才是一次纯屏幕位移：由 `tools/pose_measure.py` 量算
      （当前残差 ≤0.001 格），`tools/check_gun_resources.py` 还会逐枪核验 `adsPitch()/adsYaw()`
      与 `models/item/*.json` 里 `display` 的 rotation 逐字一致。
   放大系数作用在姿态链**上游**，`ADS_*` 在其下游会跟着一起放大 —— 所以调放大**不必重测** `ADS_*`；
   反之若改 `display` 的 scale 来放大，枪体会变而姿态不变，镜轴被顶偏。
   持枪（hip）落点由 `GunPose.HIP_DX / HIP_DY` 控制，当前 (−0.10, +0.08) 格 ——
   握把与右手略收进画面右下角，`pose_measure.py` 会打印"握把/照门"的 NDC 坐标供取舍
   （画面右缘 = +1.78、下缘 = −1.00）；当前值让右手与换弹动作刚好在画面边缘露出来。
   别处不要再加缩放（`美术规范.md` §5：动骨骼，不动整模）。
3. 加兰德音色（见「声音」）。
4. `draw` / `put_away` / `inspect` 未做（AWM 有十段，M1 目前**七段**：v6 加了 `single_load`）；
   `static_idle` 是静止的，持枪摆动同样缺一套程序化微动（同 AWM 待办 7）。
5. `美术规范.md` 手性那行待修订（同 AWM 待办 8）。

## 来源与许可

| 内容 | 来源 | 许可 | 处置 |
|---|---|---|---|
| 几何、贴图、UV 图集、蒙皮划分 | 本项目自己生成（`tools/m1_garand_bb_gen.js`） | 本项目自己的许可 | 可进分发产物 |
| 七段动画数据 | 本项目自己编（按真机机构，动作集取名沿用 TaCZ 惯例） | 本项目自己的许可 | **可进分发产物**（与 AWM 的 ai_awp 转录不同） |
| `M1GarandItem` 触发的音效 | TaCZ 枪包 `tacz_sounds/ai_awp/` 原样副本 | CC BY-NC-ND 4.0 | **未修改副本**，只留在开发自用包，不进 `-clean.jar` |
| 手感/弹道数值（8 发、aim 0.2 s、FOV 50、伤害 15/13/10、穿透 2） | 本项目自定 + 参考枪械常识 | 数值本身不受版权保护 | — |

**TaCZ 不是本模组的依赖，也不随本模组分发**：它只是开发期参照与临时借音。
分发用的 `-clean.jar` 里有几何、贴图、动画，但没有那批 `.ogg`——所以本枪在分发版里是**静音**的，
需要配一个 CC0 枪声包或自行录制，替换方式见「声音」一节。完整说明见仓库根 **`NOTICE.md`**。
