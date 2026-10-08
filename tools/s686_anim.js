'use strict';
/* ============================================================================
 * Gold Plate - S686 —— 动画（折开式 break-action 换弹）
 *
 * 用法:  node tools/s686_anim.js [--no-export]
 *
 * 与 S686Item.java 的硬契约（check_gun_resources.py 会卡）：
 *   1. S686Item 里每个 ANIM_* 字符串必须在导出的 animation.json 里有同名 clip
 *   2. 6 个 *_TICKS 必须 == ceil(clip.animation_length * 20)
 *   3. 通道形状只能是 { "时间": { post: { vector: [x,y,z] }, lerp_mode } }
 *
 * 折开式换弹时序（真实 S686 / Citori 猎枪）：
 *   顶杆推开 -> 枪管绕铰链下折 38° -> 抽壳钩顶出两发空壳 -> 左手塞入两发新弹
 *   -> 合膛（略过头再回弹）-> 抖动归位
 * ========================================================================== */
const fs = require('fs');
const path = require('path');
const { Bb } = require('./bbmcp_lib.js');

const ROOT = path.resolve(__dirname, '..');

const K = (t, v) => ({ time: t, position: v });   // 位置关键帧
const R = (t, v) => ({ time: t, rotation: v });   // 旋转关键帧

/** 折开角度：绕铰链 X 轴负角 = 枪口向下（右手系里 -Z 方向的点绕 +X 负转即下压） */
const OPEN = -38;
/** 合膛时的过冲角，制造 Q 弹回弹感 */
const OVERSHOOT = 3.5;

/* 弹壳在弹膛内沿 -Z 朝枪口方向；退膛 = 沿 +Z 后退并下坠 */
function shellTrack(sign) {
  return [
    K(0.00, [0, 0, 0]),
    K(0.55, [0, 0, 0]),                       // 折开过程中弹壳还没动
    K(0.80, [0, 0.30 * sign, 1.30]),          // 抽壳：沿膛线后退
    K(1.15, [0, -2.20 * sign, 2.90]),         // 脱出并下坠
    K(1.30, [0, -4.60 * sign, 3.60]),         // 掉出视野
    K(1.35, [0, -1.30 * sign, 2.10]),         // 新弹出现在枪外下方（回位关键帧）
    K(2.00, [0, -0.30 * sign, 0.80]),         // 新弹接近弹膛
    K(2.35, [0, 0, 0]),                       // 到位
    K(3.30, [0, 0, 0]),
  ];
}

/* 折开 / 合膛曲线：开得慢、合得快并带过冲回弹 */
function breakTrack(openAt, holdUntil, closeAt, endAt, overshoot) {
  return [
    R(0.00, [0, 0, 0]),
    R(0.14, [0, 0, 0]),                        // 顶杆先动，枪管未动
    R(openAt, [OPEN, 0, 0]),
    R(holdUntil, [OPEN, 0, 0]),                // 敞开保持（装弹窗口）
    R(closeAt, [overshoot, 0, 0]),             // 合上并过冲
    R(closeAt + 0.12, [-1.2, 0, 0]),           // 回弹
    R(endAt, [0, 0, 0]),
  ];
}

/** 顶杆：向右推开 -> 保持 -> 复位 */
function leverTrack(pushAt, holdUntil, backAt, endAt) {
  return [
    K(0.00, [0, 0, 0]),
    K(pushAt, [0.42, 0, 0]),
    K(holdUntil, [0.42, 0, 0]),
    K(backAt, [0, 0, 0]),
    K(endAt, [0, 0, 0]),
  ];
}

/** 击锤：折开时被压到待击位，合膛后复位 */
function hammerTrack(downAt, holdUntil, upAt, endAt) {
  return [
    R(0.00, [0, 0, 0]),
    R(downAt, [-26, 0, 0]),
    R(holdUntil, [-26, 0, 0]),
    R(upAt, [4, 0, 0]),
    R(endAt, [0, 0, 0]),
  ];
}

/* 整体姿态：换弹时枪身略微下沉、前倾，合膛后弹回 */
function bodyTrack(midAt, endAt, sink, tilt) {
  return {
    position: [K(0.00, [0, 0, 0]), K(midAt, [0, sink, 0.16]), K(endAt, [0, 0, 0])],
    rotation: [R(0.00, [0, 0, 0]), R(midAt, [tilt, 0, 0]), R(endAt, [0, 0, 0])],
  };
}

const ANIM = {};

/* ---------------- static_idle 待机：轻微呼吸浮动，循环 ---------------- */
ANIM.static_idle = {
  length: 2.0, loop: true,
  bones: {
    move: {
      position: [K(0.0, [0, 0, 0]), K(0.5, [0, -0.05, 0]), K(1.0, [0, 0, 0]), K(1.5, [0, -0.05, 0]), K(2.0, [0, 0, 0])],
      rotation: [R(0.0, [0, 0, 0]), R(0.5, [0.8, 0.5, 0]), R(1.0, [0, 0, 0]), R(1.5, [0.8, -0.5, 0]), R(2.0, [0, 0, 0])],
    },
  },
};

/* ---------------- draw 抽枪：从下方举起并轻微过冲 ---------------- */
ANIM.draw = {
  length: 1.0,
  bones: {
    move: {
      position: [K(0.0, [0, -6.5, 1.2]), K(0.6, [0, -0.5, 0]), K(0.8, [0, 0.22, 0]), K(1.0, [0, 0, 0])],
      rotation: [R(0.0, [-24, 0, -6]), R(0.6, [-3, 0, 0]), R(0.8, [2.4, 0, 0]), R(1.0, [0, 0, 0])],
    },
  },
};

/* ---------------- shoot 射击：双管齐发的强烈后坐 ---------------- */
ANIM.shoot = {
  length: 0.6,
  bones: {
    move: {
      position: [K(0.0, [0, 0, 0]), K(0.05, [0, 0.30, 0.62]), K(0.16, [0, 0.16, 0.38]), K(0.36, [0, 0.03, 0.07]), K(0.6, [0, 0, 0])],
      rotation: [R(0.0, [0, 0, 0]), R(0.05, [9.5, 0, 0]), R(0.16, [5.0, 0, 0]), R(0.36, [1.0, 0, 0]), R(0.6, [0, 0, 0])],
    },
    hammer: {
      rotation: [R(0.0, [0, 0, 0]), R(0.04, [-30, 0, 0]), R(0.30, [-30, 0, 0]), R(0.52, [3, 0, 0]), R(0.6, [0, 0, 0])],
    },
  },
};

/* ---------------- bolt 开膛检查：折开 -> 合上（不装弹） ---------------- */
ANIM.bolt = {
  length: 1.2667,
  bones: {
    barrel: { rotation: breakTrack(0.42, 0.62, 1.02, 1.2667, OVERSHOOT * 0.7) },
    top_lever: { position: leverTrack(0.10, 0.95, 1.12, 1.2667) },
    hammer: { rotation: hammerTrack(0.36, 0.95, 1.10, 1.2667) },
    move: bodyTrack(0.60, 1.2667, -0.30, 3.0),
  },
};

/* ---------------- reload_tactical 战术换弹：折开补弹后合上 ---------------- */
ANIM.reload_tactical = {
  length: 2.6,
  bones: {
    barrel: { rotation: breakTrack(0.50, 1.55, 2.05, 2.6, OVERSHOOT) },
    top_lever: { position: leverTrack(0.10, 2.00, 2.22, 2.6) },
    hammer: { rotation: hammerTrack(0.42, 2.00, 2.20, 2.6) },
    shell_upper: { position: [K(0.0, [0, 0, 0]), K(1.62, [0, 0, 0]), K(1.72, [0, -1.1, 1.5]), K(1.98, [0, 0, 0]), K(2.6, [0, 0, 0])] },
    shell_lower: { position: [K(0.0, [0, 0, 0]), K(1.68, [0, 0, 0]), K(1.78, [0, 1.1, 1.5]), K(2.02, [0, 0, 0]), K(2.6, [0, 0, 0])] },
    move: bodyTrack(1.20, 2.6, -0.34, 3.6),
  },
};

/* ---------------- reload_empty 空仓换弹（主秀）：折开 -> 抽双壳 -> 装双弹 -> 合膛 ---------------- */
ANIM.reload_empty = {
  length: 3.3,
  bones: {
    barrel: { rotation: breakTrack(0.55, 2.30, 2.75, 3.3, OVERSHOOT) },
    top_lever: { position: leverTrack(0.15, 2.55, 2.78, 3.3) },
    hammer: { rotation: hammerTrack(0.46, 2.55, 2.76, 3.3) },
    shell_upper: { position: shellTrack(1) },
    shell_lower: { position: shellTrack(1).map((k, i, arr) => ({ time: i === arr.length - 1 ? 3.3 : k.time + 0.05, position: k.position })) },
    extractor: { position: [K(0.0, [0, 0, 0]), K(0.62, [0, 0, 0]), K(0.82, [0, 0, 0.55]), K(1.20, [0, 0, 0.30]), K(1.32, [0, 0, 0]), K(3.3, [0, 0, 0])] },
    move: bodyTrack(1.35, 3.3, -0.42, 4.6),
  },
};

/*
 * 换弹两段整体加速（1.1.55 起）：reload_tactical 2.6 s -> 1.95 s、reload_empty 3.3 s -> 2.475 s。
 *
 * 放在这里统一缩放，而不是把上面几十个时间字面量逐个手改 —— 上面那些 0.50 / 1.55 / 2.05 / 2.6
 * 之类的数字改漏一个，就会让动画与 S686Item 的 *_TICKS、以及 RELOAD_*_SOUNDS 的时刻表错开。
 * 那两处（json 与 Java）用的是同一个倍率，见 S686Item 的换弹常量注释。
 */
const RELOAD_SPEED = 0.75;

function speedUpReload(clip, factor) {
  clip.length = Math.round(clip.length * factor * 1000) / 1000;
  for (const bone of Object.values(clip.bones ?? {})) {
    for (const track of Object.values(bone)) {
      if (Array.isArray(track)) {
        for (const key of track) {
          if (typeof key.time === 'number') {
            key.time = Math.round(key.time * factor * 1000) / 1000;
          }
        }
      }
    }
  }
  return clip;
}

speedUpReload(ANIM.reload_tactical, RELOAD_SPEED);
speedUpReload(ANIM.reload_empty, RELOAD_SPEED);

/* ---------------- ADS_up / ADS_down 瞄准进出 ---------------- */
ANIM.ADS_up = {
  length: 0.18,
  bones: {
    move: {
      position: [K(0.0, [0, 0, 0]), K(0.18, [0, -0.30, -0.22])],
      rotation: [R(0.0, [0, 0, 0]), R(0.18, [0, 0, 0])],
    },
  },
};
ANIM.ADS_down = {
  length: 0.18,
  bones: {
    move: {
      position: [K(0.0, [0, -0.30, -0.22]), K(0.18, [0, 0, 0])],
      rotation: [R(0.0, [0, 0, 0]), R(0.18, [0, 0, 0])],
    },
  },
};

/* ============================ 下发 ============================ */
async function main() {
  const noExport = process.argv.includes('--no-export');
  const bb = await Bb.connect();

  /* 幂等：清掉同名旧动画（没有专用工具，用最小 risky_eval） */
  const clear = await bb.t('risky_eval', {
    code: '(function(){var n=0;Animation.all.slice().forEach(function(a){if(a.remove){a.remove();n++;}});return {removed:n};})()',
  });
  console.log('[clear]', clear.text.slice(0, 200));

  await bb.t('geckolib_set_project_settings', { modid: 'apocalypse_zombies', model_type: 'Item', model_identifier: 's686' });

  const report = { clips: [], errors: [] };
  for (const [name, def] of Object.entries(ANIM)) {
    const bones = {};
    for (const [bone, ch] of Object.entries(def.bones)) {
      /* create_animation 的 bones 结构是 { 骨名: [关键帧...] }，位置与旋转必须合进同一数组 */
      const merged = new Map();
      for (const k of (ch.position || [])) { const t = +k.time.toFixed(4); merged.set(t, Object.assign(merged.get(t) || { time: t }, { position: k.position })); }
      for (const k of (ch.rotation || [])) { const t = +k.time.toFixed(4); merged.set(t, Object.assign(merged.get(t) || { time: t }, { rotation: k.rotation })); }
      bones[bone] = [...merged.values()].sort((a, b) => a.time - b.time);
    }
    const args = { name, loop: !!def.loop, animation_length: def.length, bones };
    const r = await bb.t('create_animation', args);
    report.clips.push({ name, length: def.length, loop: !!def.loop, bones: Object.keys(bones), resp: r.text.slice(0, 200) });
    console.log(`[anim] ${name}  ${def.length}s  bones=${Object.keys(bones).join(',')}`);
  }

  const v = await bb.t('geckolib_validate_model', { include_animations: true });
  report.validate = v.text.slice(0, 4000);
  console.log('[validate]', v.text.slice(0, 700));

  if (!noExport) {
    const out = path.join(ROOT, 'build', 's686.animation.json');
    const e = await bb.t('geckolib_export_animations', { path: out, mode: 'compile', max_content_length: 0 });
    report.export = e.text.slice(0, 600);
    console.log('[export]', e.text.slice(0, 300));
    if (fs.existsSync(out)) {
      const j = JSON.parse(fs.readFileSync(out, 'utf8'));
      report.exported = {
        bytes: fs.statSync(out).size,
        format_version: j.format_version,
        geckolib_format_version: j.geckolib_format_version,
        clips: Object.fromEntries(Object.entries(j.animations || {}).map(([k, a]) => [k, { length: a.animation_length, loop: a.loop, bones: Object.keys(a.bones || {}).length }])),
      };
      console.log('[exported]', JSON.stringify(report.exported.clips));
    }
  }

  fs.writeFileSync(path.join(ROOT, 'build', 's686_anim.json'), JSON.stringify(report, null, 1));
  console.log('\n回报 -> build/s686_anim.json');
}

main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
