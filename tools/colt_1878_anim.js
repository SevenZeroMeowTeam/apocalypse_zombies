'use strict';
/* ============================================================================
 * Coach Gun（短管双管霰弹枪）—— 动画（通过 blockbench-mcp 下发）
 *
 * 用法: node tools/colt_1878_anim.js [--reset]
 *
 * ★ 名字必须与 S686Item 里的常量**逐字一致**（裸名，不带 "animation." 前缀）：
 *     ANIM_IDLE            = "static_idle"
 *     ANIM_DRAW            = "draw"
 *     ANIM_SHOOT           = "shoot"
 *     ANIM_BOLT            = "bolt"
 *     ANIM_RELOAD_TACTICAL = "reload_tactical"
 *     ANIM_RELOAD_EMPTY    = "reload_empty"
 *     ANIM_ADS_UP          = "ADS_up"
 *     ANIM_ADS_DOWN        = "ADS_down"
 *   原因：短管喷在 Java 侧**继承 S686Item**（它的行为几乎全是可覆盖的方法，省掉 952 行复制），
 *   而动画名常量是跨枪共用的 public static final —— 所以动画名字沿用 S686 那八个，
 *   但**时长是另一套**：本文件每条片段的 animation_length 都被 Colt1878Item.actionLength
 *   与 tools/check_gun_resources.py 拿 tick 数对着核（改这里就必须改那边）。
 *
 * 换弹是本枪的卖点：**刻意做慢**
 *     reload_tactical  3.00 s = 60 tick   （S686 是 1.95 s / 39 tick）
 *     reload_empty     3.60 s = 72 tick   （S686 是 2.475 s / 50 tick）
 *   tools/colt_1878_install.js 里有门禁锁住这两条。
 *
 * 换弹动作链 —— 照**真枪**（原型 Colt Model 1878 / 侧并排折开式 + extractor）来：
 *   拇指横向拨顶杆 → 枪管绕铰链向下折开 → extractor 顶起空壳 → 甩腕抖掉壳
 *   → 右手从弹带取两发 → 两发同时塞进两个弹膛 → 枪管上抬合膛，顶杆自动回中
 *   研究来源与量到的尺寸记在 art/colt_1878/README.md。
 *
 * ⚠️ v1 的三处硬伤（用户指出"换弹不对"之后逐个量出来的，别再犯）：
 *   1. 折开写成了绕 **Z** 轴（[0,0,-52]）。Z 是枪管长轴，绕它转只是**枪身滚转**，
 *      看着根本不像折开。正确的是绕 **X**（铰链那根横轴），方向用 tools/colt_1878_hinge_probe.js 量过。
 *   2. 顶杆写成沿枪轴前后推（position z）。真枪的 top lever 是**横向**拨的。
 *   3. 左手 hand_l 挂在 body 下 —— 它是握前托的，必须挂 barrel 下，否则枪管一折开
 *      手就留在原地、脱离前托飘着。（待装弹 bolt_loaded 同理。）
 *
 * 折开的**表现方式**（第二版，按用户要求改的）：不再是"枪管向下折"，而是
 *   **机匣+枪托绕铰链向上翻、枪管在世界坐标里纹丝不动**。
 *   相对角同样是 62°（弹膛照样露出来），但第一人称里枪管不会甩出画面中心。
 *   实现是 body 转 −OPEN、barrel 转 +OPEN —— 两个骨绕**同一个 pivot**（铰链）
 *   反向转，正好抵消。符号与"枪管真的没动"由 tools/colt_1878_fold_probe.js 量过。
 *   连带约束：**shoot / static_idle / ADS_* 都不许再给 barrel 或 body 转角**，
 *   后坐与呼吸一律用 move 的位移表达，否则枪管又会相对机匣动。
 *
 * 外露击锤（hammer_l）是本枪与 S686 最显眼的分野，所以必须动起来：折开时被机构顶回待击位
 * （rotation.x = +26°，与 S686 的 hammer 通道同一套符号：正 = 向后倒 = 待击），
 * 合膛后落回 0°；射击瞬间弹到 +30° 再落回。
 *
 * 跑完会 geckolib_validate_model + geckolib_export_animations 到 build/colt_1878.animation.json，
 * 再用 node tools/colt_1878_install.js 规范化落位（--no-export 可只改 Blockbench 不落盘）。
 *
 * 坐标：create_animation 用 Blockbench 编辑器坐标（与 geo 文件的镜像约定差一个 X 取反），
 * 由导出插件自己转，这里不要手工取反。
 * 关键帧形状：同一通道**至少两个关键帧** —— 只给一个时 Blockbench 会导出成退化的
 * {"vector":[...]}（没有时间层），GeckoLib 读不了。
 * ========================================================================== */
const fs = require('fs');
const path = require('path');
const { Bb } = require('./bbmcp_lib.js');

const HIDDEN = [0, 0, 0];
const SHOWN = [1, 1, 1];

/* 折开角（度）—— 绕 **X 轴**，负值 = 枪口向下折。
 *
 * ⚠️ 这里原本是 v1 最大的一个错：写的 rotation [0, 0, -52]，也就是绕 **Z**。
 * 而 Z 是枪管长轴，绕它转是**枪身滚转**，跟"折开"毫无关系。
 * 方向不要靠推理，用 tools/colt_1878_hinge_probe.js 量（读枪管 cube 的世界矩阵平移）：
 *     X −62°  → 枪口端 y 从 +0.276 掉到 −7.105   ← 真的是朝下折
 *     X +62°  → y 涨到 +6.825                    ← 朝上翘
 *     Z −52°  → y 几乎不动、x 从 −0.306 跑到 +0.429  ← 只是滚转
 * 真枪要 50° 以上才露得出弹膛给手指让位，62° 是折开式霰弹枪常见的停位。 */
const OPEN = 62;

/* 甩腕（退壳）时整枪向下一顿的幅度。extractor 只能把壳顶起几毫米，
 * 壳是**靠这一下甩出去**的 —— 真枪退壳从来不是"自动抛出"。 */
const FLICK = -0.15;

/** 换弹里"推顶杆—折开—退壳—装弹—合膛"这套骨架，按给定时间表生成；t 是各阶段时刻。
 *
 * 真实流程（原型 Colt Model 1878 / 侧并排折开式 + extractor）：
 *   1. 拇指把顶杆（top lever）**横向**拨到射手右侧，解除闭锁
 *   2. 左手压住前托、右手抬托颈，枪管绕铰链向下折开 —— 枪口朝下，弹膛口朝上后方
 *   3. extractor 把两发空壳顶起几毫米（它**不抛壳**，会抛壳的是 ejector）；再甩腕把壳抖掉
 *   4. 右手从弹带取两发
 *   5. 两发**同时**塞进两个弹膛，拇指推到底
 *   6. 枪管上抬合膛，顶杆自动回中，"咔"一下到位
 *
 * 三处照真枪改掉的关键点（v1 全错）：
 *   · latch（顶杆）走 **x 轴** —— 真枪是横向拨，不是沿枪轴前后推
 *   · 折开绕 **X 轴**（理由见 OPEN 的注）
 *   · 退壳方向是枪管**局部 +Z**（弹膛口那一侧），不是在世界坐标里拍脑袋定的"后上方"
 */
function reloadBones(t) {
  return {
    latch: [
      { time: t.t0, position: [0, 0, 0] },
      { time: t.lever, position: [-0.13, 0, 0] },
      { time: t.unlock, position: [-0.13, 0, 0] },
      { time: t.leverBack, position: [0, 0, 0] },
    ],
    /* 折开 —— **机匣+枪托绕铰链向上翻，枪管在世界坐标里纹丝不动**。
     *
     * 做法：body 转 −OPEN、barrel 转 +OPEN。两者绕的是**同一个 pivot**（铰链，见
     * tools/colt_1878_geo.js 里 body 的 pivot），反向角恰好抵消 ⇒ 枪管链
     * （barrel / forend / shell_upper / hand_l / bolt_loaded）在世界上完全不动。
     * 符号由 tools/colt_1878_fold_probe.js 量过：body −62 / barrel +62 那一行，
     * 枪管 cube 的世界坐标与 rest **逐位相同**（[-0.306, 0.276, -9.044]）。
     *
     * 为什么不是"枪管向下折"（真枪的样子）：第一人称里枪管一垂就甩出画面中心，
     * 观感像枪塌了。用户要的是枪管稳在画面里、机匣和托往上翻开 —— 相对角一样是 62°，
     * 弹膛照样露出来，但视线的落点不跑。 */
    body: [
      { time: t.openStart, rotation: [0, 0, 0] },
      { time: t.openMid, rotation: [-OPEN * 0.45, 0, 0] },
      { time: t.openFull, rotation: [-OPEN, 0, 0] },
      { time: t.closeStart, rotation: [-OPEN, 0, 0] },
      { time: t.closeBump, rotation: [7, 0, 0] },
      { time: t.closeSettle, rotation: [0, 0, 0] },
      { time: t.end, rotation: [0, 0, 0] },
    ],
    barrel: [
      { time: t.openStart, rotation: [0, 0, 0] },
      { time: t.openMid, rotation: [OPEN * 0.45, 0, 0] },
      { time: t.openFull, rotation: [OPEN, 0, 0] },
      { time: t.closeStart, rotation: [OPEN, 0, 0] },
      { time: t.closeBump, rotation: [-7, 0, 0] },
      { time: t.closeSettle, rotation: [0, 0, 0] },
      { time: t.end, rotation: [0, 0, 0] },
    ],
    /* 甩腕 + 合膛冲击：都是整枪的小幅位移 */
    move: [
      { time: t.openFull, position: [0, 0, 0] },
      { time: t.flick, position: [0, FLICK, 0.05] },
      { time: t.shellOut, position: [0, 0.03, -0.01] },
      { time: t.ammoUp, position: [0, 0, 0] },
      { time: t.closeStart, position: [0, 0, 0] },
      { time: t.closeBump, position: [0, FLICK * 0.4, 0.04] },
      { time: t.closeSettle, position: [0, 0, 0] },
      { time: t.end, position: [0, 0, 0] },
    ],
    /* 空壳（shell_upper 挂在 barrel 下）：沿**局部 +Z** 出膛 —— 那正是弹膛口的方向，
       折开后它在世界上朝上后方，与真枪退壳方向一致。
       0.16 u ≈ 10 mm，和真枪 extractor 的几毫米行程同一量级。
       注意每个关键帧都必须带 scale：只给两头的话 GeckoLib 会拿第一个 scale 往回外推，
       整个折开段都会是隐藏的。 */
    shell_upper: [
      { time: t.openStart, position: [0, 0, 0], rotation: [0, 0, 0], scale: SHOWN },
      { time: t.openFull, position: [0, 0, 0], rotation: [0, 0, 0], scale: SHOWN },
      { time: t.extract, position: [0, 0.02, 0.16], rotation: [0, 0, 0], scale: SHOWN },
      { time: t.flick, position: [0, 0.07, 0.36], rotation: [-14, 0, 0], scale: SHOWN },
      { time: t.shellOut, position: [0, 0.26, 1.10], rotation: [-56, 0, 22], scale: SHOWN },
      { time: t.shellGone, position: [0, 0.54, 2.30], rotation: [-100, 0, 40], scale: HIDDEN },
      { time: t.end, position: [0, 0.54, 2.30], rotation: [-100, 0, 40], scale: HIDDEN },
    ],
    /* 左手握在前托上 —— 而前托和 hand_l 自己都挂在 barrel 下，所以折开时手**自动**
       跟着枪管走，不需要任何补偿。（v1 把 hand_l 挂在 body 下，枪管一折手就留在原地、
       脱离前托飘在半空。）这里只留合膛那一下的反作用微动。 */
    hand_l: [
      { time: t.openFull, position: [0, 0, 0] },
      { time: t.closeStart, position: [0, 0, 0] },
      { time: t.closeBump, position: [0, -0.04, 0.03] },
      { time: t.closeSettle, position: [0, 0, 0] },
      { time: t.end, position: [0, 0, 0] },
    ],
    /* 外露双锤（一个骨骼带左右两个锤，绕中轴一起动）：折开时被机构顶回待击位，合膛后落回。
       ⚠️ 符号是**负**的：本文件写的是 Blockbench 编辑器坐标，导出插件会把它沿 X 取反，
       所以这里 −26 才会导出成 geo 里的 +26 —— 与 S686 的 hammer 通道**逐字一致**。
       看着"反了"改成 +26 的话，锤子会朝机匣里倒（穿模）。 */
    hammer_l: [
      { time: t.openStart, rotation: [0, 0, 0] },
      { time: t.openFull, rotation: [-26, 0, 0] },
      { time: t.seated, rotation: [-26, 0, 0] },
      { time: t.closeBump, rotation: [4, 0, 0] },
      { time: t.hammerSettle, rotation: [0, 0, 0] },
      { time: t.end, rotation: [0, 0, 0] },
    ],
    /* 待装的两发（同样挂 barrel 下，所以"推入弹膛"就是把位置推回 0）。
       手从枪下方把弹送到弹膛口，再沿膛轴推到底 —— 局部 +Z 是弹膛口方向。 */
    bolt_loaded: [
      { time: t.ammoUp, scale: HIDDEN, position: [0, -0.55, 0.55] },
      { time: t.ammoVis, scale: SHOWN, position: [0, -0.50, 0.50] },
      { time: t.ammoIn, scale: SHOWN, position: [0, -0.34, 0.34] },
      { time: t.seat, scale: SHOWN, position: [0, -0.05, 0.05] },
      { time: t.seated, scale: SHOWN, position: [0, 0, 0] },
      { time: t.end, scale: SHOWN, position: [0, 0, 0] },
    ],
  };
}

const ANIMS = [
  {
    name: 'static_idle',
    loop: true,
    animation_length: 2.0,
    bones: {
      /* 待机只让**整枪**在手里微微起伏，枪管一动不动（body / barrel 都不写通道）。
         原来那两条 body 1.2° 与 barrel −0.6° 会让枪管相对机匣轻微摇摆，与"枪管不动"冲突。 */
      move: [
        { time: 0.0, position: [0, 0, 0] },
        { time: 1.0, position: [0, -0.055, 0.03] },
        { time: 2.0, position: [0, 0, 0] },
      ],
    },
  },
  {
    name: 'draw',
    loop: false,
    animation_length: 0.8,
    bones: {
      move: [{ time: 0.0, position: [0, -1.10, 0.55] }, { time: 0.6, position: [0, 0.06, 0] }, { time: 0.8, position: [0, 0, 0] }],
      body: [{ time: 0.0, rotation: [16, 0, 0] }, { time: 0.6, rotation: [-3, 0, 0] }, { time: 0.8, rotation: [0, 0, 0] }],
    },
  },
  {
    name: 'shoot',
    loop: false,
    animation_length: 0.6,
    bones: {
      /* 后坐 = **整枪向上微抬 + 向后推**，枪管自己不做任何转动（用户点名要的）。
         让 barrel 单独转的话，枪管相对机匣动 —— 第一人称里看着像枪管在抖；
         而后坐上跳本来就是整把枪的事，用 move 的位移表达才对。 */
      move: [
        { time: 0.0, position: [0, 0, 0] }, { time: 0.08, position: [0, 0.075, 0.20] },
        { time: 0.30, position: [0, 0.015, -0.03] }, { time: 0.45, position: [0, -0.005, 0.01] },
        { time: 0.60, position: [0, 0, 0] },
      ],
      /* 击锤：扣扳机瞬间弹开，停在后坐里，再落回 —— 与 S686 的 hammer 同一条曲线
         （符号见 reloadBones 里 hammer_l 的注：编辑器坐标要写负的） */
      hammer_l: [
        { time: 0.0, rotation: [0, 0, 0] }, { time: 0.0417, rotation: [-30, 0, 0] },
        { time: 0.2917, rotation: [-30, 0, 0] }, { time: 0.50, rotation: [3, 0, 0] },
        { time: 0.5833, rotation: [0, 0, 0] },
      ],
    },
  },
  {
    /* 折开退壳（不含装弹）：1.4 s。用于"打空了但不想换弹"的检视/排障动作 */
    name: 'bolt',
    loop: false,
    animation_length: 1.4,
    bones: {
      latch: [
        { time: 0.00, position: [0, 0, 0] }, { time: 0.12, position: [-0.13, 0, 0] },
        { time: 0.30, position: [-0.13, 0, 0] }, { time: 0.44, position: [0, 0, 0] },
      ],
      /* 折开：机匣+枪托上翻、barrel 反向补偿 —— 与 reloadBones 同一套（见那里的注） */
      body: [
        { time: 0.28, rotation: [0, 0, 0] }, { time: 0.70, rotation: [-OPEN, 0, 0] },
        { time: 1.06, rotation: [-OPEN, 0, 0] }, { time: 1.26, rotation: [7, 0, 0] },
        { time: 1.38, rotation: [0, 0, 0] },
      ],
      barrel: [
        { time: 0.28, rotation: [0, 0, 0] }, { time: 0.70, rotation: [OPEN, 0, 0] },
        { time: 1.06, rotation: [OPEN, 0, 0] }, { time: 1.26, rotation: [-7, 0, 0] },
        { time: 1.38, rotation: [0, 0, 0] },
      ],
      move: [
        { time: 0.70, position: [0, 0, 0] }, { time: 0.88, position: [0, FLICK, 0.05] },
        { time: 1.00, position: [0, 0.03, -0.01] }, { time: 1.14, position: [0, 0, 0] },
        { time: 1.26, position: [0, FLICK * 0.4, 0.04] }, { time: 1.38, position: [0, 0, 0] },
      ],
      shell_upper: [
        { time: 0.28, position: [0, 0, 0], rotation: [0, 0, 0], scale: SHOWN },
        { time: 0.70, position: [0, 0, 0], rotation: [0, 0, 0], scale: SHOWN },
        { time: 0.84, position: [0, 0.02, 0.16], rotation: [0, 0, 0], scale: SHOWN },
        { time: 0.92, position: [0, 0.07, 0.36], rotation: [-14, 0, 0], scale: SHOWN },
        { time: 1.06, position: [0, 0.26, 1.10], rotation: [-56, 0, 22], scale: SHOWN },
        { time: 1.24, position: [0, 0.54, 2.30], rotation: [-100, 0, 40], scale: HIDDEN },
      ],
      /* 折开把两个锤顶回待击位，合膛后落回（符号同 reloadBones 的注） */
      hammer_l: [
        { time: 0.28, rotation: [0, 0, 0] }, { time: 0.70, rotation: [-26, 0, 0] },
        { time: 1.06, rotation: [-26, 0, 0] }, { time: 1.26, rotation: [4, 0, 0] },
        { time: 1.38, rotation: [0, 0, 0] },
      ],
    },
  },
  {
    /* 有弹时换弹：3.00 s = 60 tick（S686 是 1.95 s / 39 tick）—— 本枪"换弹慢"的主力 */
    name: 'reload_tactical',
    loop: false,
    animation_length: 3.0,
    bones: reloadBones({
      t0: 0.00, lever: 0.10, unlock: 0.26, leverBack: 0.40,
      openStart: 0.26, openMid: 0.46, openFull: 0.68,
      extract: 0.80, flick: 0.92, shellOut: 1.06, shellGone: 1.26,
      ammoUp: 1.32, ammoVis: 1.40, ammoIn: 1.54, seat: 1.76, seated: 1.90,
      closeStart: 1.96, closeBump: 2.24, closeSettle: 2.40, hammerSettle: 2.48,
      end: 3.00,
    }),
  },
  {
    /* 空仓换弹：3.60 s = 72 tick（S686 是 2.475 s / 50 tick）。
     * 比有弹版多的是"两发壳都得退、壳胀了要抠一下、手在弹带里多摸一趟" —— 各段整体放慢。 */
    name: 'reload_empty',
    loop: false,
    animation_length: 3.6,
    bones: reloadBones({
      t0: 0.00, lever: 0.12, unlock: 0.32, leverBack: 0.50,
      openStart: 0.32, openMid: 0.58, openFull: 0.86,
      extract: 1.06, flick: 1.24, shellOut: 1.42, shellGone: 1.66,
      ammoUp: 1.78, ammoVis: 1.90, ammoIn: 2.14, seat: 2.48, seated: 2.68,
      closeStart: 2.80, closeBump: 3.14, closeSettle: 3.32, hammerSettle: 3.42,
      end: 3.60,
    }),
  },
  {
    /* 举枪到瞄准位（铁瞄，所以只是把枪端平抬到眼前） */
    name: 'ADS_up',
    loop: false,
    animation_length: 0.22,
    bones: {
      /* 只走整枪位移，不给 body 转角 —— 一给 body 转角，枪管就相对机匣动了 */
      move: [{ time: 0.0, position: [0, 0, 0] }, { time: 0.22, position: [0, 0.06, -0.05] }],
    },
  },
  {
    name: 'ADS_down',
    loop: false,
    animation_length: 0.18,
    bones: {
      move: [{ time: 0.0, position: [0, 0.06, -0.05] }, { time: 0.18, position: [0, 0, 0] }],
    },
  },
];

async function main() {
  const bb = await Bb.connect();
  const tools = await bb.listTools();
  if (!tools.includes('create_animation')) {
    throw new Error('MCP 缺少 create_animation（项目没打开？）');
  }

  /* 先清掉同名片段再建：不带这一步，Blockbench 会把新片段命名成 shoot2 / bolt2 …，
   * 导出的 json 里于是两套并存 —— 落位脚本挑的是**不带后缀**那套（也就是上一次的旧内容），
   * 改动画的人就会看到一个"改了没生效"的怪现象。跑过一次真实踩坑，所以默认就清。 */
  const names = JSON.stringify(ANIMS.map((a) => a.name));
  const clean = await bb.t('risky_eval', {
    code: '(function(){var names=' + names + ';var n=0;Animation.all.slice().forEach(function(a){'
      + 'var nm=String(a.name||"").replace(/^animation\./,"");'
      + 'if(names.indexOf(nm)>=0&&a.remove){a.remove();n++;}});'
      + 'return {removed:n};})()',
  });
  console.log('[clean]', clean.text.slice(0, 200));

  if (process.argv.includes('--reset')) {
    const r = await bb.t('risky_eval', {
      code: '(function(){var n=0;Animation.all.slice().forEach(function(a){if(a.remove){a.remove();n++;}});'
        + 'Animation.all.length=0;if(typeof Animator!=="undefined"&&Animator.animations)Animator.animations.length=0;'
        + 'return {removed:n};})()',
    });
    console.log('[reset]', r.text.slice(0, 200));
  }

  for (const a of ANIMS) {
    const r = await bb.t('create_animation', a);
    console.log(`[anim] ${a.name.padEnd(17)} ${String(a.animation_length).padStart(4)}s = ${String(Math.round(a.animation_length * 20)).padStart(2)} tick  loop=${a.loop}  bones=${Object.keys(a.bones).join(',')}`);
  }

  const v = await bb.t('geckolib_validate_model', { include_animations: true });
  console.log('[validate]', v.text.slice(0, 700));

  if (!process.argv.includes('--no-export')) {
    const out = path.join(__dirname, '..', 'build', 'colt_1878.animation.json');
    const e = await bb.t('geckolib_export_animations', { path: out, mode: 'compile', max_content_length: 0 });
    console.log('[export]', e.text.slice(0, 300));
    if (fs.existsSync(out)) {
      const j = JSON.parse(fs.readFileSync(out, 'utf8'));
      console.log('[exported]', JSON.stringify(Object.fromEntries(Object.entries(j.animations || {})
        .map(([k, a]) => [k, { len: a.animation_length, bones: Object.keys(a.bones || {}) }]))));
    }
  }
}

main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
