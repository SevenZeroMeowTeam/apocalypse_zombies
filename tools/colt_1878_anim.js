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
 * 换弹动作链（照真枪折开式霰弹枪的顺序）：
 *   拨开膛杆 → 折开 52° → 退壳 → 左手探腰间弹袋 → 夹回两发 → 推入弹膛 → 合膛（带回弹）
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

/** 折开角（度）。真枪要 50° 以上才露得出弹膛给手指让位。 */
const OPEN = 52;

/** 换弹里"折开—退壳—装弹—合膛"这套骨架，按给定时间表生成；t 是各阶段时刻。 */
function reloadBones(t) {
  return {
    latch: [
      { time: t.latch0, position: [0, 0, 0] },
      { time: t.latch1, position: [0, 0, 0.14] },
      { time: t.openStart, position: [0, 0, 0.14] },
      { time: t.eject, position: [0, 0, 0] },
    ],
    barrel: [
      { time: t.openStart, rotation: [0, 0, 0] },
      { time: t.openMid, rotation: [0, 0, -18] },
      { time: t.openFull, rotation: [0, 0, -OPEN] },
      { time: t.closeStart, rotation: [0, 0, -OPEN] },
      { time: t.closeBump, rotation: [0, 0, 6] },
      { time: t.end, rotation: [0, 0, 0] },
    ],
    shell_upper: [
      { time: t.openFull, position: [0, 0, 0], rotation: [0, 0, 0] },
      { time: t.shellMid, position: [0, 0.26, 0.62], rotation: [0, 0, 40] },
      { time: t.eject, position: [0, 0.06, 1.10], rotation: [0, 0, 110] },
      { time: t.closeStart, position: [0, 0, 0.30], rotation: [0, 0, 160] },
    ],
    hand_l: [
      { time: t.openFull, position: [0, 0, 0] },
      { time: t.handOut, position: [-0.52, 0.18, 0.48] },
      { time: t.handGrab, position: [-0.46, 0.10, 0.40] },
      { time: t.handBack, position: [0.06, -0.04, -0.24] },
      { time: t.round1, position: [0.14, 0.02, -0.38] },
      { time: t.round2, position: [0.10, 0.06, -0.46] },
      { time: t.closeStart, position: [0, 0, 0] },
    ],
    /* 外露双锤（一个骨骼带左右两个锤，绕中轴一起动）：折开时被机构顶回待击位，合膛后落回。
       ⚠️ 符号是**负**的：本文件写的是 Blockbench 编辑器坐标，导出插件会把它沿 X 取反，
       所以这里 −26 才会导出成 geo 里的 +26 —— 与 S686 的 hammer 通道**逐字一致**。
       看着"反了"改成 +26 的话，锤子会朝机匣里倒（穿模）。 */
    hammer_l: [
      { time: t.openStart, rotation: [0, 0, 0] },
      { time: t.openFull, rotation: [-26, 0, 0] },
      { time: t.round2, rotation: [-26, 0, 0] },
      { time: t.closeBump, rotation: [4, 0, 0] },
      { time: t.end, rotation: [0, 0, 0] },
    ],
    bolt_loaded: [
      { time: t.openFull, scale: HIDDEN, position: [0, 0, 0] },
      { time: t.handBack, scale: SHOWN, position: [0, 0, 0] },
      { time: t.round1, scale: SHOWN, position: [0, 0, -0.16] },
      { time: t.round2, scale: SHOWN, position: [0, 0, -0.30] },
      { time: t.closeStart, scale: HIDDEN, position: [0, 0, -0.30] },
    ],
  };
}

const ANIMS = [
  {
    name: 'static_idle',
    loop: true,
    animation_length: 2.0,
    bones: {
      move: [{ time: 0.0, position: [0, 0, 0] }, { time: 1.0, position: [0, -0.06, 0] }, { time: 2.0, position: [0, 0, 0] }],
      body: [{ time: 0.0, rotation: [0, 0, 0] }, { time: 1.0, rotation: [1.2, 0, 0] }, { time: 2.0, rotation: [0, 0, 0] }],
      // 双管的重量让枪口有一丝下垂
      barrel: [{ time: 0.0, rotation: [0, 0, 0] }, { time: 1.0, rotation: [0.6, 0, 0] }, { time: 2.0, rotation: [0, 0, 0] }],
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
      barrel: [
        { time: 0.0, rotation: [0, 0, 0] }, { time: 0.08, rotation: [0, 0, 8] },
        { time: 0.30, rotation: [0, 0, -2.5] }, { time: 0.45, rotation: [0, 0, 1] }, { time: 0.60, rotation: [0, 0, 0] },
      ],
      move: [
        { time: 0.0, position: [0, 0, 0] }, { time: 0.08, position: [0, -0.05, 0.18] },
        { time: 0.30, position: [0, -0.02, -0.03] }, { time: 0.60, position: [0, 0, 0] },
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
        { time: 0.00, position: [0, 0, 0] }, { time: 0.20, position: [0, 0, 0.14] },
        { time: 0.40, position: [0, 0, 0.14] }, { time: 0.90, position: [0, 0, 0] },
      ],
      barrel: [
        { time: 0.20, rotation: [0, 0, 0] }, { time: 0.60, rotation: [0, 0, -OPEN] },
        { time: 1.05, rotation: [0, 0, -OPEN] }, { time: 1.28, rotation: [0, 0, 6] },
        { time: 1.40, rotation: [0, 0, 0] },
      ],
      shell_upper: [
        { time: 0.60, position: [0, 0, 0], rotation: [0, 0, 0] },
        { time: 0.82, position: [0, 0.26, 0.62], rotation: [0, 0, 40] },
        { time: 1.05, position: [0, 0.06, 1.10], rotation: [0, 0, 110] },
      ],
      /* 折开把两个锤顶回待击位，合膛后落回（符号同 reloadBones 的注） */
      hammer_l: [
        { time: 0.20, rotation: [0, 0, 0] }, { time: 0.60, rotation: [-26, 0, 0] },
        { time: 1.05, rotation: [-26, 0, 0] }, { time: 1.20, rotation: [4, 0, 0] },
        { time: 1.36, rotation: [0, 0, 0] },
      ],
    },
  },
  {
    /* 有弹时换弹：3.00 s = 60 tick（S686 是 1.95 s / 39 tick）—— 本枪"换弹慢"的主力 */
    name: 'reload_tactical',
    loop: false,
    animation_length: 3.0,
    bones: reloadBones({
      latch0: 0.00, latch1: 0.18, openStart: 0.30, openMid: 0.54, openFull: 0.90,
      shellMid: 1.15, eject: 1.35, handOut: 1.35, handGrab: 1.60, handBack: 1.88,
      round1: 2.20, round2: 2.42, closeStart: 2.60, closeBump: 2.86, end: 3.00,
    }),
  },
  {
    /* 空仓换弹：3.60 s = 72 tick（S686 是 2.475 s / 50 tick）。
     * 比有弹版多的是"退壳更彻底 + 手在弹袋里多摸一下" —— 这一段刻意拉长。 */
    name: 'reload_empty',
    loop: false,
    animation_length: 3.6,
    bones: reloadBones({
      latch0: 0.00, latch1: 0.22, openStart: 0.38, openMid: 0.66, openFull: 1.08,
      shellMid: 1.38, eject: 1.62, handOut: 1.70, handGrab: 2.02, handBack: 2.34,
      round1: 2.68, round2: 2.94, closeStart: 3.14, closeBump: 3.42, end: 3.60,
    }),
  },
  {
    /* 举枪到瞄准位（铁瞄，所以只是把枪端平抬到眼前） */
    name: 'ADS_up',
    loop: false,
    animation_length: 0.22,
    bones: {
      move: [{ time: 0.0, position: [0, 0, 0] }, { time: 0.22, position: [0, 0.06, -0.05] }],
      body: [{ time: 0.0, rotation: [0, 0, 0] }, { time: 0.22, rotation: [-1.5, 0, 0] }],
    },
  },
  {
    name: 'ADS_down',
    loop: false,
    animation_length: 0.18,
    bones: {
      move: [{ time: 0.0, position: [0, 0.06, -0.05] }, { time: 0.18, position: [0, 0, 0] }],
      body: [{ time: 0.0, rotation: [-1.5, 0, 0] }, { time: 0.18, rotation: [0, 0, 0] }],
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
