# 十字弩（Crossbow，弹仓式）— 资产说明

按《美术规范.md》逐面 UV 路线生成：**枪口 −Z / 上 +Y / 右 +X**，原点在机匣一带，**骨骼零旋转**，
几何全部由生成器产出（**275 方块 / 29 骨**，无手工方块）。建模与预览经 **blender-mcp 连 Blender 5.2.1** 落地。

生成链路：

```
tools/crossbow_v1.py        几何 + 512² 逐面 UV 图集 + 7 段动画（boxlib 程序化生成，纯标准库）
        ↓ 直接写盘（两份）
art/crossbow/crossbow.geo.json            ─────────► resources/assets/apocalypse_zombies/geo/
art/crossbow/crossbow.animation.json      ─────────► resources/.../animations/
art/crossbow/crossbow.png (512²)          ─────────► resources/.../textures/models/
tools/crossbow_bb_scene.py  在 Blender 内重建场景 → 套动画姿态 → EEVEE 出 12 张 preview_*.png
        ↓
art/crossbow/blender_build_report.json   BUILD_REPORT（骨数/方块数/面数/bbox/渲染字节数）
art/crossbow/crossbow.blend              可继续手工微调的工程
```

## 文件

| 文件 | 说明 |
|---|---|
| `tools/crossbow_v1.py` | 几何 + 图集 + 动画生成器（含自检；末尾 `sys.exit` 在 Blender 沙箱会被拦，属正常） |
| `tools/crossbow_bb_scene.py` | Blender 场景/渲染脚本（读 geo+anim，出预览与报告） |
| `art/crossbow/crossbow.geo.json` | 几何（GeckoLib Animated Model，29 骨 / 275 方块 / 1650 面） |
| `art/crossbow/crossbow.animation.json` | 动画（7 段，`geckolib_format_version: 2`） |
| `art/crossbow/crossbow.blend` / `blender_build_report.json` | Blender 工程与构建报告 |
| `art/crossbow/preview_*.png` | 12 张 900² 预览（四视图 / 顶视 / 开镜 / 拉弦两帧 / 装填三帧 / 箭匣特写 / 弩机特写） |

## 标定（文献尺寸 → 模型）

| 项目 | 实测值 | 依据 |
|---|---|---|
| 全长 | `Z ∈ [−11.80, 8.55]` = **20.35u = 1.27 格** | 规范成品 1.0~1.5 格 ✓ |
| 弩臂展 | `X ∈ [−10.12, 10.19]` = **20.31u** | 弩弓横于臂前部，弓片装 riser 两端、向后张开 |
| 高 | `Y ∈ [−2.75, 3.96]` = 6.71u | 含瞄准镜光轴与握把下沿 |
| 弩机枢轴 | **`{0, 1.10, −1.60}`** | 牙与悬刀**共用一台转轴**（汉弩机「第一塊與第三塊共用一個轉軸」） |
| 弦静止面 / 拉满内端 | `z = −7.90` → **精确**收敛于牙 `{0, 1.10, −1.60}` | **弦不可拉伸**（半段长恒 10.12）：拉满弓片屈曲 `∓14.05°`、弦骨只转 `∓39.3°`、`scale` 恒 1 |
| 矢长 | **3.02u = 18.9 cm**（八寸） | 汉弩「矢長八寸」；十矢与待发箭同口径 |
| 箭匣 | 十矢，`yslot 1.28 → 2.81`（间距 0.17u） | 《魏氏春秋》「一弩十矢俱發」 |
| 脚踏环 | `ring @ z −11.79…−11.56`，`r 0.30…0.52` | 手拉上弦时以脚蹬踏环撑弦 |
| 弓片截面 | 高(Y) `0.62u→0.46u` = **3.9→2.9 cm**；前后厚(Z) `0.44u→0.24u` = **2.75→1.5 cm** | 实物弓片 3~5 cm；薄在 Z 才弯得动 |
| 密度 / 图集 | `S = 12.0` px/单位，**512×512**（用到 V≈490） | 规范 11~13 ✓ |
| 方块 / 骨骼 | **275 / 29** | ≤600 / ≤40 ✓ |

## 骨树（29 根，pivot 全部在自身几何内，无旋转）

| 骨 | 父 | pivot | 方块 | 作用 |
|---|---|---|---|---|
| `root` / `move` / `body` | — / root / move | `{0,0,0}` | 0 / 0 / 32 | 根、整体位移、主体 |
| `constraint` / `camera` | body | `{0,1.1,−1.6}` / `{0,2.85,3.6}` | 0 / 0 | GeckoLib 约束与第一人称机位 |
| `limb_l` / `limb_r` | body | `{∓1.62, 1.1, −10.85}` | 12 / 12 | 弩臂（弓片）：10 段切线弧 + 尖端弦槽两颊，绕 Y 屈曲 |
| `string_l` / `string_r` | limb_l/r | `{∓10.12, 1.1, −7.9}` | 2 / 2 | 弓弦两段（半段长 10.12，**只转不伸缩**） |
| `lock_housing` | body | `{0, 1.1, −1.6}` | 9 | 郭（浅盘：底板+四壁+两键+保险） |
| `nut` | lock_housing | `{0, 1.1, −1.6}` | 4 | 牙（承弦钩，鸟首形） |
| `trigger` | lock_housing | `{0, 0.84, −1.6}` | 3 | 悬刀（与牙同轴的转轴） |
| `sight_rear` | lock_housing | `{0, 1.44, −1.41}` | 6 | 望山（表尺，5 道刻度） |
| `magazine` | body | `{0, 2.1, −5.6}` | 16 | 箭匣壳体（带观察窗的侧壁 + 敞口匣底 + 磁石） |
| `mag_r1`…`mag_r10` | magazine | `{0, 1.28…2.81, −6}` | 5×10 | 匣内十矢 |
| `round_in` | body | `{0, 1.03, −6}` | 5 | 待发箭（nock 卧在弦静止线 −7.90、箭尖穿出弩头箭槽） |
| `round_hand` | body | `{−2.6, −1.55, −4.4}` | 5 | 左手新箭（静止与拉弦时 `scale=[0,0,0]` 隐藏） |
| `scope` / `scope_elev` / `scope_wind` | body / scope | `{0,2.85,0}` / `{0,3.15,−0.2}` / `{1.6,2.85,−0.2}` | 99 / 6 / 6 | 瞄准镜 + 高低/风偏调节 |

## 动画（7 段）

| clip | 时长 | 机构依据 |
|---|---|---|
| `static_idle` | 2.0 s | 待机微呼吸；`round_hand` 恒为 `scale=[0,0,0]` |
| `draw` | 1.2 s | 拉弦：`limb_l/r` 屈曲 `0 → ∓14.05°`（尖端向后收 1.9u、向内 0.93u，与真弩一致），`string_l/r` **只转不伸缩**，弦内端逐帧落到牙 `{0,1.10,−1.60}` |
| `shoot` | 0.6 s | 击发：牙绕枢轴释放、弦回收、弓片回弹（`8·rt·(1−rt)` 曲线） |
| `reload_tactical` | 1.6 s | **左手取箭装入弹仓**：`round_hand` 由 `scale 0` 显形 → 抬起（y 1.56）→ 平移入匣顶槽 `{0, 2.81, −6.00}`（与 `mag_r10` 重合）→ `scale 0` 消失 |
| `ADS_up` / `ADS_down` | 0.18 s | 抬镜 / 放镜 |
| `inspect` | 2.6 s | 检视 |

## 文献驱动的几何修正（本轮）

1. **弩机不再被机匣吞没**：机匣在 `z −3.30…−1.30` 敞开成机槽，郭做成浅盘（壁顶 1.06 **低于**弦面 1.09），牙/望山/悬刀/两键全部可见。
2. **补弩身前段箭道槽**：`z −10.55…−5.60` 中间留槽盛箭（文献「臂面刻直槽，以盛箭」），弦从槽沿上方通过，箭匣不再"悬空"。
3. **箭匣开窗**：侧壁改为带窗框的四段 + 玻璃嵌在洞内（两侧对称），匣底只留左右沿、中间是落箭口 → 匣内十矢可见。
4. **弦与弓片尖端齐平**：弓片尖端后缘与弦面 `z −7.90` **精确重合**（原先脱开 0.6u），尖端另加两片钢颊夹出 0.10u 弦槽。
5. **牙与悬刀共轴**：悬刀枢轴由 `{0,−0.60,0.72}` 改为 `{0,0.84,−1.60}`（与牙同轴）。
6. **矢长改为八寸**：`3.2u → 3.02u`（18.9 cm），匣内/待发/手递三处同口径；箭镞**朝前**（原实现把镞画在箭尾端）。
7. **补脚踏环**（stirrup，8 边 ring）。
8. **箭匣容量 4 → 10 矢**，无羽短矢（《天工開物》「去箭尾羽毛，便于由管道射出」），匣底两块磁石吸附铁矢。
9. **弓片 = 连续弧线**（关键，用户「使弓臂连贯」）：原先 3 段轴对齐方块＝阶梯，远看就是三根直棍；现按 `θ(u)=24°·u^1.15` 弧线切 **10 段、每段各自 `rotation` 贴切线**（段间转角 3.3~3.8° 平滑单调、越靠尖端越弯），截面沿长度收细；根部加**金属夹具 + 弓片螺栓**（属 `body`：弓片在夹具里屈曲、夹具不动），弩头加高到 `y 0.78~1.42` 并把中央留成 0.40u 箭道槽让待发箭穿出。
10. **弦不可拉伸的运动学**（关键）：原先拉弦靠 `string.scale.x → 1.182` 硬拉伸、弓片只转 −5° 且**方向反了**（尖端往前跑）；现解 `|尖端(A) − 弦心| = 弦半段长 10.12`（二分），弓片屈曲 `∓14.05°`、弦骨只转、`scale` 恒 1。几何 / 动画 / 自检三处共用 `limb_deg_for` / `string_bone_param` 同一套解算。
11. **待发箭 nock 落到弦线**：原先 nock 在 `z −6.00`（弦从箭杆中段穿过），现 nock 卧 `−7.90`、箭尖 `−10.92` 穿出弩头箭槽。

12. **★ 交付坐标约定：Bedrock/GeckoLib 文件是「取反常」（本轮挖出并修掉的真错）**
   生成器内部一切几何/动画都按**右手系**（与 Blender / Minecraft Java 模型同系）求解，自检也在这个空间里断言；
   但 `.geo.json` / `.animation.json` 的**文件格式用的是镜像约定**——实测三方对照（Blockbench 5.2.1 + GeckoLib Animation Utils）：
   - **立方体坐标 / 骨骼 pivot：X 取反**（文件 `limb_r` origin.x=1.56 → 工程 `from.x=−2.53`；`string_r` pivot 10.12 → −10.12）
   - **旋转：X、Y 取反**（文件 `draw` limb_r Y=−14.05 → 工程 animator +14.05）
   - **动画位置通道：X 取反**（文件 `round_hand` x=−2.6 → 工程 +2.6），Y/Z 不变
   依据：GeckoLib 源码 `BakedAnimationsAdapter.java:221-223`「rotation values are negated for the X and Y axes」；
   Blockbench 侧插件源码同款注释「Blockbench now implicitly inverts rotation and position keyframes on export and import」。
   **修正前**：生成器直写右手系值 ⇒ 游戏里整机 X 镜像 + 旋转取反 ⇒ **拉弦会朝前屈曲**（Blockbench 实测尖端 z 由 −7.90 跑到 −10.85）。
   **修正后**：写出前统一转成文件约定（`game_convention_geo` / `game_convention_anims`，接在 `write_all` 前，内部数值与自检不受影响）：
   文件 `limb_r` origin.x=**−2.5302**、`draw` limb_r Y=**+14.0511**、`round_hand` x=**+2.6**。
   ⚠ 该约定对**所有** Bedrock/GeckoLib 资产生效：其它武器的生成器若同样直写右手系值，需套同一转换。

## 复现与校验

```bash
# 生成器自检 + 两份产物落盘（纯标准库，bash 直接跑；也可在 Blender 内经 MCP runpy）
cd /f/mcmod && python3 tools/crossbow_v1.py
#   期望：pack density = 12 / 方块=275 骨=29 / 全部通过（0 错误）
# 校验交付约定（应打印 limb_r origin.x=-2.5302 / draw limb_r Y=+14.0511 / round_hand x=+2.6）
cd /f/mcmod && python3 -c "import json;g=json.load(open('art/crossbow/crossbow.geo.json',encoding='utf-8'));b={x['name']:x for x in g['minecraft:geometry'][0]['bones']};print(b['limb_r']['cubes'][0]['origin'],b['limb_r']['pivot']);a=json.load(open('art/crossbow/crossbow.animation.json',encoding='utf-8'));d=a['animations']['draw']['bones'];print({n:d[n]['rotation'][sorted(d[n]['rotation'],key=float)[-1]] for n in ('limb_l','limb_r')})"
# 场景重建 + 12 张预览 + 报告
#   runpy.run_path('F:/mcmod/tools/crossbow_bb_scene.py', run_name='__main__')
#   期望：BUILD_REPORT {bones:29, cubes:275, faces:1650, errors:[]}
```

本仓 **没有** `tools/art_audit.py`（文档里的那个验收门槛在本仓不存在），验收 = **生成器自检 + `BUILD_REPORT` + 预览图**。
数值化的"部件悬空"检查（各骨方块到其它骨方块的最小 AABB 距离）应只有 `round_hand` 超 0.25u —— 它由 `static_idle` 的
`scale=[0,0,0]` 隐藏，属设计而非缺陷。

## 许可

几何 / 贴图 / 动画均为本模组原创（生成器产出），可随分发包发布。
本目录不含任何第三方资产；其他武器的第三方资产许可见各自 `README.md`（TaCZ 资产为 CC BY-NC-ND 4.0）。