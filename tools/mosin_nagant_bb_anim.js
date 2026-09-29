/* 莫辛-纳甘 M91/30 —— 动画生成器（在 Blockbench 内跑，MCP risky_eval）
 *
 * 机制依据（莫辛-纳甘 M91/30）：
 *   直拉机柄：提柄（绕膛线轴 +Z 转 80°）→ 后拉（沿 +Z 滑 1.55u，待击块露出机匣）→ 抛壳 →
 *             前推（推弹入膛）→ 压柄归位。真机手柄为直杆，旋转轴就是膛线轴。
 *   固定弹仓：5 发，桥夹/单发压入都从机匣前环顶面的装填桥下去；压弹时枪身下压、口朝下（文献姿态）。
 *   装填节奏参考 TaCZ kar98k（reload_loop 0.6833s/轮，reload_intro 0.75s、reload_end 0.9833s、bolt 1.2667s）。
 *
 * 片段清单（长度 x 20 向上取整 = Java 的 *_TICKS 契约，规范八）：
 *   static_idle     2.00s loop  40t
 *   draw            0.90s once  18t
 *   shoot           0.60s once  12t
 *   bolt            1.10s once  22t
 *   reload_tactical 3.60s once  72t   （弹仓已有 2 发，补 3 发）
 *   reload_empty    4.40s once  88t   （空仓，逐发压入 5 发）
 *   inspect         2.60s once  52t
 *
 * 跑法（MCP risky_eval）：
 *   (function(){var fs=require('fs');return (0,eval)(fs.readFileSync('F:/mcmod/tools/mosin_nagant_bb_anim.js','utf8'));})()
 */
(function () {

  var report = { steps: [], warns: [], fails: [], clips: {} };
  function step(s) { report.steps.push(s); }
  function warn(s) { report.warns.push(s); }
  function fail(s) { report.fails.push(s); }

  if (typeof Undo === 'undefined' || typeof Project === 'undefined' || typeof Keyframe === 'undefined') {
    return { ok: false, fails: ['不在 Blockbench 作用域'] };
  }

  // ---------------------------------------------------------------- 0. 骨骼校验
  // 注意：BB 5.2 里项目自带的 root 组不在 Group.all（那根骨由 geo 自带，本片集不驱动它），
  //       所以这里只列真正要驱动的骨。
  var NEED = ['move', 'body', 'bolt', 'rear_sight', 'magazine', 'floorplate', 'follower', 'trigger',
              'casing', 'round_in', 'mag_r1', 'mag_r2', 'mag_r3', 'mag_r4', 'mag_r5'];
  var G = {};
  NEED.forEach(function (n) {
    G[n] = Group.all.find(function (g) { return g.name === n; });
    if (!G[n]) fail('找不到骨骼 ' + n + '（先跑 mosin_nagant_bb_gen.js）');
  });
  if (report.fails.length) return { ok: false, fails: report.fails };

  // ---------------------------------------------------------------- 1. 清旧动画
  var old = (typeof Animation !== 'undefined' && Animation.all) ? Animation.all.slice() : [];
  try { Undo.initEdit({ outliner: false, animations: old }); }
  catch (e) { try { Undo.initEdit({ outliner: false }); } catch (e2) {} }
  old.forEach(function (a) { try { a.remove(); } catch (e) {} });
  step('清旧动画：' + old.length + ' 条');

  // ---------------------------------------------------------------- 2. 工具
  function clip(name, len, loop) {
    var a = new Animation({ name: name, loop: loop || 'once', animation_length: len, bones: {} });
    a.add();
    try { a.length = len; } catch (e) {}                       // 陷阱：length 才是运行时字段
    if (typeof a.setLength === 'function') { try { a.setLength(len); } catch (e) {} }
    try { a.select(); } catch (e) { warn(name + ' select: ' + e.message); }
    // 陷阱：select() 只把"上一条动画里存在的骨"塞进 Timeline —— 手动补全，否则时间轴看不到骨
    try {
      Timeline.animators = Object.keys(a.animators).map(function (u) { return a.animators[u]; });
      Timeline.animators.forEach(function (an) { an.selected = true; });
    } catch (e) { warn(name + ' Timeline: ' + e.message); }
    report.clips[name] = { length: len, loop: loop || 'once', ticks: Math.ceil(len * 20), bones: {}, keys: 0 };
    return a;
  }
  function K(a, bone, channel, time, vec, interp) {
    var g = G[bone];
    if (!g) { fail(a.name + ' 无骨骼 ' + bone); return; }
    var an = a.animators[g.uuid];
    if (!an) { // 兜底：即使 select() 没建，也手动建 animator
      an = new BoneAnimator(g.uuid, a);
      a.animators[g.uuid] = an;
    }
    var kf = new Keyframe({
      channel: channel,
      time: time,
      interpolation: interp || 'linear',
      data_points: [{ x: vec[0], y: vec[1], z: vec[2] }]
    }, null, an);
    try { an.pushKeyframe(kf); } catch (e) { fail(a.name + '.' + bone + '.' + channel + '@' + time + ' → ' + e.message); }
    var info = report.clips[a.name];
    if (info) {
      info.keys++;
      info.bones[bone] = (info.bones[bone] || 0) + 1;
    }
  }
  // 一整个通道固定不动（TaCZ 惯例：每条片段把它需要的骨都钉住，避免上一条片段的残留值）
  function Kconst(a, bone, channel, vec, interp) { K(a, bone, channel, 0, vec, interp); }
  var CAT = 'catmullrom', LIN = 'linear';
  var S0 = [0, 0, 0], S1 = [1, 1, 1];

  // 静止态必须钉住的"隐藏件"：弹壳、待压入的弹
  function pinSafety(a) {
    Kconst(a, 'casing', 'scale', S0);
    Kconst(a, 'round_in', 'scale', S0);
    Kconst(a, 'casing', 'position', S0);
    Kconst(a, 'casing', 'rotation', S0);
  }

  // ================================================================ 3. static_idle（2.00s loop）
  (function () {
    var a = clip('static_idle', 2.0, 'loop');
    K(a, 'move', 'rotation', 0.0, [0, 0, 0], CAT);
    K(a, 'move', 'rotation', 0.5, [-0.45, -0.25, 0], CAT);
    K(a, 'move', 'rotation', 1.0, [-0.12, -0.45, 0], CAT);
    K(a, 'move', 'rotation', 1.5, [0.30, -0.16, 0], CAT);
    K(a, 'move', 'rotation', 2.0, [0, 0, 0], CAT);
    K(a, 'move', 'position', 0.0, [0, 0, 0], CAT);
    K(a, 'move', 'position', 0.6, [0, -0.030, 0], CAT);
    K(a, 'move', 'position', 1.3, [0, 0, 0], CAT);
    K(a, 'move', 'position', 1.7, [0, 0.022, 0], CAT);
    K(a, 'move', 'position', 2.0, [0, 0, 0], CAT);
    K(a, 'body', 'rotation', 0.0, [0, 0, 0], CAT);
    K(a, 'body', 'rotation', 1.0, [-0.15, 0, 0], CAT);
    K(a, 'body', 'rotation', 2.0, [0, 0, 0], CAT);
    Kconst(a, 'bolt', 'rotation', S0);
    Kconst(a, 'bolt', 'position', S0);
    Kconst(a, 'trigger', 'rotation', S0);
    Kconst(a, 'rear_sight', 'rotation', S0);
    Kconst(a, 'follower', 'position', S0);
    Kconst(a, 'magazine', 'rotation', S0);
    pinSafety(a);
  })();

  // ================================================================ 4. draw（0.90s once）
  (function () {
    var a = clip('draw', 0.9, 'once');
    K(a, 'move', 'position', 0.00, [0, -2.40, -0.50], LIN);
    K(a, 'move', 'position', 0.45, [0, 0.06, 0.06], LIN);
    K(a, 'move', 'position', 0.75, [0, 0, 0], LIN);
    K(a, 'move', 'position', 0.90, [0, 0, 0], LIN);
    K(a, 'move', 'rotation', 0.00, [-18, 10, 3], CAT);
    K(a, 'move', 'rotation', 0.50, [0.8, -1.6, 0], CAT);
    K(a, 'move', 'rotation', 0.80, [0, 0, 0], CAT);
    K(a, 'body', 'rotation', 0.00, [0, -7, 0], CAT);
    K(a, 'body', 'rotation', 0.55, [0, 0, 0], CAT);
    Kconst(a, 'bolt', 'position', S0);
    Kconst(a, 'bolt', 'rotation', S0);
    Kconst(a, 'trigger', 'rotation', S0);
    Kconst(a, 'rear_sight', 'rotation', S0);
    pinSafety(a);
  })();

  // ================================================================ 5. shoot（0.60s once）
  (function () {
    var a = clip('shoot', 0.6, 'once');
    K(a, 'move', 'position', 0.000, [0, 0, 0], LIN);
    K(a, 'move', 'position', 0.055, [0, 0.090, 0.440], LIN);   // 后坐：向上向后
    K(a, 'move', 'position', 0.160, [0, 0.030, 0.140], LIN);
    K(a, 'move', 'position', 0.300, [0, 0, 0.020], LIN);
    K(a, 'move', 'position', 0.600, [0, 0, 0], LIN);
    K(a, 'move', 'rotation', 0.000, [0, 0, 0], LIN);
    K(a, 'move', 'rotation', 0.060, [3.2, -1.4, 1.1], LIN);     // rotX 正 = 枪口抬
    K(a, 'move', 'rotation', 0.180, [1.1, -0.5, 0.4], LIN);
    K(a, 'move', 'rotation', 0.400, [0, 0, 0], LIN);
    K(a, 'body', 'rotation', 0.000, [0, 0, 0], LIN);
    K(a, 'body', 'rotation', 0.070, [-1.2, 0.6, 0], LIN);
    K(a, 'body', 'rotation', 0.350, [0, 0, 0], LIN);
    K(a, 'trigger', 'rotation', 0.000, [0, 0, 0], LIN);
    K(a, 'trigger', 'rotation', 0.030, [-6, 0, 0], LIN);        // 负 = 扣向后方
    K(a, 'trigger', 'rotation', 0.090, [-6, 0, 0], LIN);
    K(a, 'trigger', 'rotation', 0.240, [0, 0, 0], LIN);
    Kconst(a, 'bolt', 'position', S0);
    Kconst(a, 'bolt', 'rotation', S0);
    Kconst(a, 'rear_sight', 'rotation', S0);
    pinSafety(a);                                               // 莫辛是栓动：弹壳在 bolt 片段抛，不在 shoot
  })();

  // ================================================================ 6. bolt（1.10s once）提→拉→抛→推→压
  (function () {
    var a = clip('bolt', 1.1, 'once');
    // 提柄：绕膛线轴 +80°（手柄在 +X，正向旋转抬柄）
    K(a, 'bolt', 'rotation', 0.00, [0, 0, 0], LIN);
    K(a, 'bolt', 'rotation', 0.19, [0, 0, 80], LIN);
    K(a, 'bolt', 'rotation', 0.68, [0, 0, 80], LIN);
    K(a, 'bolt', 'rotation', 0.86, [0, 0, 0], LIN);
    // 后拉 1.55u（真机行程 ~90mm），推回
    K(a, 'bolt', 'position', 0.00, [0, 0, 0], LIN);
    K(a, 'bolt', 'position', 0.19, [0, 0, 0], LIN);
    K(a, 'bolt', 'position', 0.43, [0, 0, 1.55], LIN);
    K(a, 'bolt', 'position', 0.55, [0, 0, 1.55], LIN);
    K(a, 'bolt', 'position', 0.74, [0, 0, 0], LIN);
    // 弹壳：静止位就在抛壳锚点 (0.90, 2.10, -1.95)，后拉到位后出现并翻出去
    // 真机：固定抛壳挺在枪机退到位（后拉到底）才把弹壳挑出去，所以出现时刻必须晚于后拉到位
    K(a, 'casing', 'scale', 0.00, S0, LIN);
    K(a, 'casing', 'scale', 0.40, S0, LIN);
    K(a, 'casing', 'scale', 0.44, S1, LIN);
    K(a, 'casing', 'scale', 0.62, S1, LIN);
    K(a, 'casing', 'scale', 0.66, S0, LIN);
    K(a, 'casing', 'position', 0.44, [0, 0, 0], LIN);
    K(a, 'casing', 'position', 0.58, [0.50, 0.85, 0.30], LIN);
    K(a, 'casing', 'position', 0.66, [0.85, 0.55, 0.10], LIN);
    K(a, 'casing', 'rotation', 0.44, [0, 0, 0], LIN);
    K(a, 'casing', 'rotation', 0.58, [60, -160, -40], LIN);
    K(a, 'casing', 'rotation', 0.66, [150, -330, -95], LIN);
    // 枪身随动作一沉一顶
    K(a, 'move', 'position', 0.00, [0, 0, 0], CAT);
    K(a, 'move', 'position', 0.38, [0, -0.055, 0.130], CAT);
    K(a, 'move', 'position', 0.85, [0, 0, 0], CAT);
    K(a, 'move', 'rotation', 0.00, [0, 0, 0], CAT);
    K(a, 'move', 'rotation', 0.38, [0.8, -1.6, 2.4], CAT);
    K(a, 'move', 'rotation', 0.90, [0, 0, 0], CAT);
    Kconst(a, 'trigger', 'rotation', S0);
    Kconst(a, 'rear_sight', 'rotation', S0);
    Kconst(a, 'round_in', 'scale', S0);
    Kconst(a, 'follower', 'position', S0);
  })();

  // ================================================================ 7. 压弹动作段（reload_* 共用）
  //   弹仓内 5 发位置（与生成器 ROUND_STACK 对应）：mag_r1/r2 = 上层、mag_r3/r4 = 中层、mag_r5 = 底层
  var ORDER = [5, 4, 3, 2, 1];                 // 第 1 发压到底层，第 5 发留在最上层
  // 托弹板随弹堆下降：0 发时顶在仓口，满 5 发时到底（真机弹簧压缩）
  function followerKeys(a, tAt, seq) {
    // seq: [{t, y}] 递增的台阶
    K(a, 'follower', 'position', 0.0, [0, 0.82, 0], LIN);
    seq.forEach(function (s) { K(a, 'follower', 'position', s.t, [0, s.y, 0], LIN); });
  }
  function insertRound(a, i, t0, slot) {
    // 待压入的弹：机匣装填桥上方 → 压下 → 沉入弹仓
    var bone = 'round_in';
    K(a, bone, 'scale', 0.0, S0, LIN);
    K(a, bone, 'scale', t0 - 0.04, S0, LIN);
    K(a, bone, 'scale', t0 + 0.02, S1, LIN);
    K(a, bone, 'scale', t0 + 0.40, S1, LIN);
    K(a, bone, 'scale', t0 + 0.46, S0, LIN);
    K(a, bone, 'position', t0 - 0.02, [0, 0.75, -0.30], LIN);
    K(a, bone, 'position', t0 + 0.16, [0, 0.10, 0.00], LIN);
    K(a, bone, 'position', t0 + 0.34, [0, -0.55, 1.05], LIN);
    K(a, bone, 'position', t0 + 0.44, [0, -1.15, 2.45], LIN);
    // 落到位的那一发：出现（弹仓里，外面看不见，但拆解/开托底时是对的）
    var mn = 'mag_r' + slot;
    Kconst(a, mn, 'scale', S0);
    K(a, mn, 'scale', t0 + 0.42, S0, LIN);
    K(a, mn, 'scale', t0 + 0.47, S1, LIN);
    a.__inserts = (a.__inserts || 0) + 1;
  }

  // ================================================================ 8. reload_empty（4.40s）空仓逐发压 5 发
  (function () {
    var a = clip('reload_empty', 4.4, 'once');
    // 提栓、后拉到位并保持
    K(a, 'bolt', 'rotation', 0.00, [0, 0, 0], LIN);
    K(a, 'bolt', 'rotation', 0.20, [0, 0, 80], LIN);
    K(a, 'bolt', 'rotation', 3.95, [0, 0, 80], LIN);
    K(a, 'bolt', 'rotation', 4.36, [0, 0, 0], LIN);
    K(a, 'bolt', 'position', 0.00, [0, 0, 0], LIN);
    K(a, 'bolt', 'position', 0.20, [0, 0, 0], LIN);
    K(a, 'bolt', 'position', 0.45, [0, 0, 1.55], LIN);
    K(a, 'bolt', 'position', 4.10, [0, 0, 1.55], LIN);
    K(a, 'bolt', 'position', 4.28, [0, 0, 0], LIN);
    // 枪身下压、口朝下（旋转 rotX 负 = 枪口低）
    K(a, 'move', 'rotation', 0.00, [0, 0, 0], CAT);
    K(a, 'move', 'rotation', 0.65, [-9, -4, 3], CAT);
    K(a, 'move', 'rotation', 3.75, [-9, -4, 3], CAT);
    K(a, 'move', 'rotation', 4.25, [0, 0, 0], CAT);
    K(a, 'move', 'position', 0.00, [0, 0, 0], CAT);
    K(a, 'move', 'position', 0.70, [0, -0.180, 0.300], CAT);
    K(a, 'move', 'position', 3.80, [0, -0.180, 0.300], CAT);
    K(a, 'move', 'position', 4.15, [0, -0.050, 0.080], CAT);
    K(a, 'move', 'position', 4.40, [0, 0, 0], CAT);
    K(a, 'body', 'rotation', 0.00, [0, 0, 0], CAT);
    K(a, 'body', 'rotation', 0.70, [0, 3.5, 0], CAT);
    K(a, 'body', 'rotation', 4.10, [0, 0, 0], CAT);
    // 5 发，0.60s 一节，从 0.80s 开始
    var T0 = 0.80, CAD = 0.60;
    for (var i = 0; i < 5; i++) insertRound(a, i, T0 + CAD * i, ORDER[i]);
    followerKeys(a, 0, [
      { t: 1.24, y: 0.50 }, { t: 2.44, y: 0.24 }, { t: 3.64, y: 0.00 }
    ]);
    Kconst(a, 'trigger', 'rotation', S0);
    Kconst(a, 'rear_sight', 'rotation', S0);
    Kconst(a, 'casing', 'scale', S0);                 // 空仓：没有弹壳要抛
    Kconst(a, 'casing', 'position', S0);
    Kconst(a, 'casing', 'rotation', S0);
    Kconst(a, 'floorplate', 'rotation', S0);
    Kconst(a, 'magazine', 'rotation', S0);
  })();

  // ================================================================ 9. reload_tactical（3.60s）仓里还有 2 发，补 3 发
  (function () {
    var a = clip('reload_tactical', 3.6, 'once');
    // 已有 2 发：上层两发可见（mag_r1/r2），底层为空（mag_r3/r4/r5 隐藏）
    ['mag_r1', 'mag_r2'].forEach(function (n) { Kconst(a, n, 'scale', S1); });
    K(a, 'bolt', 'rotation', 0.00, [0, 0, 0], LIN);
    K(a, 'bolt', 'rotation', 0.18, [0, 0, 80], LIN);
    K(a, 'bolt', 'rotation', 3.15, [0, 0, 80], LIN);
    K(a, 'bolt', 'rotation', 3.48, [0, 0, 0], LIN);
    K(a, 'bolt', 'position', 0.00, [0, 0, 0], LIN);
    K(a, 'bolt', 'position', 0.18, [0, 0, 0], LIN);
    K(a, 'bolt', 'position', 0.40, [0, 0, 1.35], LIN);
    K(a, 'bolt', 'position', 3.30, [0, 0, 1.35], LIN);
    K(a, 'bolt', 'position', 3.44, [0, 0, 0], LIN);
    K(a, 'move', 'rotation', 0.00, [0, 0, 0], CAT);
    K(a, 'move', 'rotation', 0.55, [-7, -3, 2], CAT);
    K(a, 'move', 'rotation', 2.95, [-7, -3, 2], CAT);
    K(a, 'move', 'rotation', 3.35, [0, 0, 0], CAT);
    K(a, 'move', 'position', 0.00, [0, 0, 0], CAT);
    K(a, 'move', 'position', 0.60, [0, -0.150, 0.240], CAT);
    K(a, 'move', 'position', 3.00, [0, -0.150, 0.240], CAT);
    K(a, 'move', 'position', 3.30, [0, -0.040, 0.060], CAT);
    K(a, 'move', 'position', 3.60, [0, 0, 0], CAT);
    K(a, 'body', 'rotation', 0.00, [0, 0, 0], CAT);
    K(a, 'body', 'rotation', 0.60, [0, 3.0, 0], CAT);
    K(a, 'body', 'rotation', 3.20, [0, 0, 0], CAT);
    var T0 = 0.68, CAD = 0.55;
    for (var i = 0; i < 3; i++) insertRound(a, i, T0 + CAD * i, ORDER[i]);   // mag_r5 → mag_r4 → mag_r3
    followerKeys(a, 0, [{ t: 1.34, y: 0.48 }, { t: 2.44, y: 0.00 }]);
    Kconst(a, 'trigger', 'rotation', S0);
    Kconst(a, 'rear_sight', 'rotation', S0);
    Kconst(a, 'casing', 'scale', S0);
    Kconst(a, 'casing', 'position', S0);
    Kconst(a, 'casing', 'rotation', S0);
    Kconst(a, 'floorplate', 'rotation', S0);
  })();

  // ================================================================ 10. inspect（2.60s once）
  (function () {
    var a = clip('inspect', 2.6, 'once');
    K(a, 'move', 'position', 0.00, [0, 0, 0], CAT);
    K(a, 'move', 'position', 0.40, [0, 0.30, 0.35], CAT);
    K(a, 'move', 'position', 2.10, [0, 0.30, 0.35], CAT);
    K(a, 'move', 'position', 2.60, [0, 0, 0], CAT);
    K(a, 'move', 'rotation', 0.00, [0, 0, 0], CAT);
    K(a, 'move', 'rotation', 0.55, [0, -32, 0], CAT);
    K(a, 'move', 'rotation', 1.15, [0, -32, 0], CAT);
    K(a, 'move', 'rotation', 1.75, [0, 26, 0], CAT);
    K(a, 'move', 'rotation', 2.35, [0, 0, 0], CAT);
    // 顺手把栓半开一下，看看机匣里面
    K(a, 'bolt', 'rotation', 0.00, [0, 0, 0], LIN);
    K(a, 'bolt', 'rotation', 1.35, [0, 0, 42], LIN);
    K(a, 'bolt', 'rotation', 1.68, [0, 0, 42], LIN);
    K(a, 'bolt', 'rotation', 2.00, [0, 0, 0], LIN);
    K(a, 'bolt', 'position', 0.00, [0, 0, 0], LIN);
    K(a, 'bolt', 'position', 1.40, [0, 0, 0.30], LIN);
    K(a, 'bolt', 'position', 1.70, [0, 0, 0.30], LIN);
    K(a, 'bolt', 'position', 1.95, [0, 0, 0], LIN);
    Kconst(a, 'trigger', 'rotation', S0);
    Kconst(a, 'rear_sight', 'rotation', S0);
    Kconst(a, 'follower', 'position', S0);
    pinSafety(a);
  })();

  step('片段：' + Object.keys(report.clips).length + ' 条');
  report.ok = report.fails.length === 0;
  try { Canvas.updateAll(); } catch (e) {}
  Undo.finishEdit('mosin_nagant 动画生成');

  var summary = { ok: report.ok, steps: report.steps, warns: report.warns, fails: report.fails, clips: {} };
  Object.keys(report.clips).forEach(function (n) {
    var c = report.clips[n];
    summary.clips[n] = { length: c.length, ticks: c.ticks, loop: c.loop, keys: c.keys, bones: Object.keys(c.bones).length,
                         driven: Object.keys(c.bones) };
  });
  return summary;
})()