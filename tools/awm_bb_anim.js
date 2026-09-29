/* HexaLunar Calamity - AWM animation set (Blockbench, run via MCP risky_eval)
 *
 * 通道铁律: 逐骨 rotation / position / scale，绝不整体缩放（美术规范.md §5）
 * 轴向铁律: 枪口 = -Z | 上 = +Y | +X = 射手右侧 | 16u = 1 block
 * 手上无臂: 模型只有部件；第一人称持枪手臂由游戏玩家手臂渲染，弹匣/枪栓/弹壳/子弹
 *           的动作承担全部"手部"表演。
 *
 * 参考物 = TaCZ 1.1.8 默认枪包 tacz_default_gun 的精密国际AWM（gun id `ai_awp`）：
 *   assets/tacz/animations/ai_awp.animation.json
 *     -> static_idle / shoot / bolt / reload_tactical / reload_empty
 * 换算（美术规范.md §十 的 TaCZ 对照表）: 角度 1:1 直抄；长度 ÷ S_GUN(2.113)；
 *   抛壳镜像到 +X（TaCZ 射手右侧 = -X，MIRROR_X = -1）。
 * 参考数据见 art/awm/tacz_ai_awp_reference.md。
 *
 * 输出: art/awm/_anim_raw.json（Blockbench 关键帧原样 dump），再由
 *       tools/awm_anim_export.py 转成 art/awm/awm.animation.json。
 */
(function () {
  var DUMP_PATH = 'F:/mcmod/art/awm/_anim_raw.json';
  var out = { steps: [], warnings: [] };
  var G = {};
  Group.all.forEach(function (g) { G[g.name] = g; });

  /* ---------- 0. wipe previous animations ---------- */
  try {
    Project.animations.slice().forEach(function (a) { if (a.remove) a.remove(); });
  } catch (e) { out.warnings.push('clean:' + e.message); }
  try { Animation.all.length = 0; } catch (e2) {}
  try { Project.animations.length = 0; } catch (e3) {}
  out.steps.push('cleared animations');

  function makeAnim(name, length, loop) {
    var a = new Animation({ name: name, loop: loop, animation_length: length, length: length, bones: {} });
    a.add();
    a.length = length;
    if (a.setLength) a.setLength(length);
    out.steps.push('anim ' + name + ' len ' + a.length + ' ' + loop);
    return a;
  }

  /* K(anim, bone, channel, time, [x,y,z], interpolation) */
  function K(a, bone, channel, time, vals, interp) {
    var g = G[bone];
    if (!g) { out.warnings.push('missing bone ' + bone); return null; }
    var an = a.getBoneAnimator(g);
    if (!an) { out.warnings.push('no animator ' + bone); return null; }
    var k = new Keyframe({
      channel: channel,
      time: time,
      interpolation: interp || 'linear',
      data_points: [{ x: vals[0], y: vals[1], z: vals[2] }]
    }, null, an);
    an.pushKeyframe(k);
    return k;
  }

  var S = 'catmullrom';

  /* ================================================================
   * 1. static_idle — 手持待机（loop, 2.0 s）
   *    没有臂骨，所以"手持"只体现在整枪微幅呼吸/晃动 + 所有活动部件归位。
   * ================================================================ */
  var idle = makeAnim('static_idle', 2.0, 'loop');
  K(idle, 'move', 'rotation', 0.00, [0.00, 0.00, 0.00], S);
  K(idle, 'move', 'rotation', 0.50, [0.55, 0.30, 0.00], S);
  K(idle, 'move', 'rotation', 1.00, [0.15, 0.55, 0.00], S);
  K(idle, 'move', 'rotation', 1.50, [-0.35, 0.20, 0.00], S);
  K(idle, 'move', 'rotation', 2.00, [0.00, 0.00, 0.00], S);
  K(idle, 'move', 'position', 0.00, [0.00, 0.00, 0.00], S);
  K(idle, 'move', 'position', 0.50, [0.02, -0.06, 0.04], S);
  K(idle, 'move', 'position', 1.00, [0.00, -0.09, 0.00], S);
  K(idle, 'move', 'position', 1.50, [-0.02, -0.04, -0.03], S);
  K(idle, 'move', 'position', 2.00, [0.00, 0.00, 0.00], S);
  K(idle, 'body', 'rotation', 0.00, [0.00, 0.00, 0.00], S);
  K(idle, 'body', 'rotation', 1.00, [-0.25, 0.00, 0.00], S);
  K(idle, 'body', 'rotation', 2.00, [0.00, 0.00, 0.00], S);
  /* 静止态：弹壳 / 待入膛子弹 scale 0（收进机匣内不渲染），弹匣在位，备用弹匣挂在井侧 */
  K(idle, 'casing', 'scale', 0.00, [0, 0, 0]);
  K(idle, 'casing', 'position', 0.00, [0, 0, 0]);
  K(idle, 'round_in', 'scale', 0.00, [0, 0, 0]);
  K(idle, 'round_in', 'position', 0.00, [0, 0, 0]);
  K(idle, 'magazine', 'position', 0.00, [0, 0, 0]);
  K(idle, 'magazine', 'rotation', 0.00, [0, 0, 0]);
  K(idle, 'mag_spare', 'position', 0.00, [0, 0, 0]);
  K(idle, 'mag_spare', 'rotation', 0.00, [0, 0, 0]);
  K(idle, 'bolt', 'position', 0.00, [0, 0, 0]);
  K(idle, 'bolt', 'rotation', 0.00, [0, 0, 0]);

  /* ================================================================
   * 2. shoot — 后坐（once, 0.85 s）  [TaCZ shoot.root 直抄]
   *    峰值 -7.95° 抬枪口 / 后坐 +2.80u（÷2.113 = 1.33u），0.6-0.8 s 回位。
   * ================================================================ */
  var sh = makeAnim('shoot', 0.85, 'once');
  var SHOT_R = [[0.00, [0, 0, 0]], [0.10, [-7.95, 0.78, -0.49]], [0.20, [-6.25, 0.49, 0.95]],
                [0.30, [-5.71, -0.30, -0.66]], [0.40, [-5.20, -0.42, -0.15]],
                [0.50, [-3.03, -0.24, -0.15]], [0.60, [0.15, 0.01, 0.01]], [0.80, [0, 0, 0]]];
  var SHOT_P = [[0.00, [0, 0, 0]], [0.10, [0, 0.56, 1.33]], [0.20, [0, 0.52, 0.87]],
                [0.30, [0, 0.42, 0.80]], [0.40, [0, 0.22, 0.43]], [0.50, [0, 0.01, 0.08]],
                [0.60, [0, -0.10, -0.13]], [0.80, [0, 0, 0]]];
  SHOT_R.forEach(function (k) { K(sh, 'move', 'rotation', k[0], k[1], S); });
  SHOT_P.forEach(function (k) { K(sh, 'move', 'position', k[0], k[1], S); });
  K(sh, 'body', 'rotation', 0.00, [0, 0, 0], S);
  K(sh, 'body', 'rotation', 0.10, [-1.60, 0, 0], S);
  K(sh, 'body', 'rotation', 0.70, [0, 0, 0], S);
  K(sh, 'body', 'rotation', 0.85, [0, 0, 0]);
  K(sh, 'casing', 'scale', 0.00, [0, 0, 0]);
  K(sh, 'round_in', 'scale', 0.00, [0, 0, 0]);

  /* ================================================================
   * 3. bolt — 拉栓（once, 1.2667 s）  [TaCZ bolt 时间轴 1:1]
   *    TaCZ: bolt_rotate Z 0.25→0.35 抬把 60°，0.85 复位；
   *          bolt_group 后退 +4.60u（÷2.113 = +2.18）；
   *          root 峰值 [4.09,-3.79,10.17] @0.40，1.2 s 回位。
   *    TaCZ 把抛壳交给游戏实体；这里模型自带 casing：
   *          抽壳 → 出抛壳窗（AWP_EJECT 0.92,1.50,-2.50）→ 向 +X 上翻飞出，
   *          同时 round_in 被栓顶进膛。
   * ================================================================ */
  var bolt = makeAnim('bolt', 1.2667, 'once');
  var BOLT_R = [[0.00, [0, 0, 0]], [0.20, [3.41, -2.88, 7.20]], [0.40, [4.09, -3.79, 10.17]],
                [0.60, [4.10, -3.31, 8.18]], [0.80, [2.87, -2.48, 6.97]],
                [1.00, [0.92, -0.85, 2.70]], [1.20, [0, 0, 0]], [1.2667, [0, 0, 0]]];
  var BOLT_P = [[0.00, [0, 0, 0]], [0.20, [0, -0.26, 0.04]], [0.40, [0, -0.18, -0.04]],
                [0.60, [0, -0.33, -0.11]], [0.80, [0, -0.28, -0.16]],
                [1.00, [0, -0.07, -0.07]], [1.20, [0, 0, 0]], [1.2667, [0, 0, 0]]];
  BOLT_R.forEach(function (k) { K(bolt, 'move', 'rotation', k[0], k[1], S); });
  BOLT_P.forEach(function (k) { K(bolt, 'move', 'position', k[0], k[1], S); });

  K(bolt, 'bolt', 'rotation', 0.00, [0, 0, 0]);
  K(bolt, 'bolt', 'rotation', 0.24, [0, 0, 0]);
  K(bolt, 'bolt', 'rotation', 0.34, [0, 0, 60]);
  K(bolt, 'bolt', 'rotation', 0.78, [0, 0, 60]);
  K(bolt, 'bolt', 'rotation', 0.90, [0, 0, 0]);
  K(bolt, 'bolt', 'rotation', 1.2667, [0, 0, 0]);
  K(bolt, 'bolt', 'position', 0.00, [0, 0, 0]);
  K(bolt, 'bolt', 'position', 0.24, [0, 0, 0]);
  K(bolt, 'bolt', 'position', 0.35, [0, 0, 0]);
  K(bolt, 'bolt', 'position', 0.47, [0, 0, 2.18]);
  K(bolt, 'bolt', 'position', 0.67, [0, 0, 2.18]);
  K(bolt, 'bolt', 'position', 0.90, [0, 0, 0]);
  K(bolt, 'bolt', 'position', 1.2667, [0, 0, 0]);

  /* 空弹壳：随栓后退被抽出（仍在机匣内），越过抛壳窗后向 +X 上方翻飞出画面 */
  K(bolt, 'casing', 'scale', 0.00, [0, 0, 0]);
  K(bolt, 'casing', 'scale', 0.50, [1, 1, 1]);
  K(bolt, 'casing', 'scale', 1.10, [1, 1, 1]);
  K(bolt, 'casing', 'scale', 1.20, [0, 0, 0]);
  K(bolt, 'casing', 'scale', 1.2667, [0, 0, 0]);
  K(bolt, 'casing', 'position', 0.00, [0, 0, 0]);
  K(bolt, 'casing', 'position', 0.50, [0, 0, 0]);
  K(bolt, 'casing', 'position', 0.60, [0, 0, 1.05]);
  K(bolt, 'casing', 'position', 0.72, [0.85, 0.20, 0.62]);
  K(bolt, 'casing', 'position', 0.90, [2.40, 1.60, 0.32], S);
  K(bolt, 'casing', 'position', 1.06, [4.80, 3.60, 0.12], S);
  K(bolt, 'casing', 'position', 1.20, [6.20, 4.60, 0.00], S);
  K(bolt, 'casing', 'position', 1.2667, [6.20, 4.60, 0.00]);
  K(bolt, 'casing', 'rotation', 0.00, [0, 0, 0]);
  K(bolt, 'casing', 'rotation', 0.60, [0, 0, 0]);
  K(bolt, 'casing', 'rotation', 0.90, [0, 260, 0], S);
  K(bolt, 'casing', 'rotation', 1.06, [0, 560, 0], S);
  K(bolt, 'casing', 'rotation', 1.20, [0, 700, 0], S);
  K(bolt, 'casing', 'rotation', 1.2667, [0, 700, 0]);

  /* 新子弹：抛壳后由栓从弹匣口顶进膛（先在抛壳窗可见，再推进膛内消失） */
  K(bolt, 'round_in', 'scale', 0.00, [0, 0, 0]);
  K(bolt, 'round_in', 'scale', 0.62, [1, 1, 1]);
  K(bolt, 'round_in', 'scale', 1.15, [1, 1, 1]);
  K(bolt, 'round_in', 'scale', 1.2667, [0, 0, 0]);
  K(bolt, 'round_in', 'position', 0.00, [0, 0, 0]);
  K(bolt, 'round_in', 'position', 0.62, [0, 0, 0]);
  K(bolt, 'round_in', 'position', 0.74, [0.45, 0, 1.70]);
  K(bolt, 'round_in', 'position', 0.92, [0.45, 0, 0.20]);
  K(bolt, 'round_in', 'position', 1.06, [0.10, 0, -1.30]);
  K(bolt, 'round_in', 'position', 1.20, [0.02, 0.02, -2.40]);
  K(bolt, 'round_in', 'position', 1.2667, [0.02, 0.02, -2.40]);
  K(bolt, 'round_in', 'rotation', 0.00, [0, 0, 0]);
  K(bolt, 'round_in', 'rotation', 1.2667, [0, 0, 0]);

  /* ================================================================
   * 4. reload_tactical — 战术换弹（once, 3.0 s）  [TaCZ reload_tactical.root 直抄]
   *    膛内留一发：只换弹匣，不拉栓、不抛壳、不上膛。
   * ================================================================ */
  var rl = makeAnim('reload_tactical', 3.0, 'once');
  var TAC_R = [[0.00, [0, 0, 0]], [0.25, [-8.19, -2.37, -17.12]], [0.50, [-10.25, -2.88, -19.10]],
               [0.75, [-8.73, -2.88, -18.26]], [1.00, [-7.38, -2.79, -18.29]], [1.25, [-6.99, -2.82, -19.71]],
               [1.50, [-7.72, -4.59, -24.91]], [1.75, [-7.64, -4.58, -25.74]], [2.00, [-8.50, -3.17, -16.16]],
               [2.25, [-1.01, -1.24, -12.95]], [2.50, [-0.84, 0.01, 0.10]], [2.75, [0.22, 0.48, -0.28]],
               [3.00, [0, 0, 0]]];
  var TAC_P = [[0.00, [0, 0, 0]], [0.25, [0, -0.35, -0.03]], [0.50, [0, -0.17, 0.08]],
               [0.75, [-0.06, -0.10, 0.12]], [1.00, [0.07, -0.29, 0.10]], [1.25, [0.09, -0.47, 0.12]],
               [1.50, [0.13, -0.29, 0.12]], [1.75, [0.13, -0.14, 0.12]], [2.00, [0.09, -0.38, 0.12]],
               [2.25, [0, -0.52, 0.42]], [2.50, [0, -0.28, -0.50]], [2.75, [0, -0.04, 0.13]],
               [3.00, [0, 0, 0]]];
  TAC_R.forEach(function (k) { K(rl, 'move', 'rotation', k[0], k[1], S); });
  TAC_P.forEach(function (k) { K(rl, 'move', 'position', k[0], k[1], S); });
  K(rl, 'body', 'rotation', 0.00, [0, 0, 0], S);
  K(rl, 'body', 'rotation', 0.60, [-1.20, 0, 0], S);
  K(rl, 'body', 'rotation', 2.20, [0, 0, 0], S);
  K(rl, 'body', 'rotation', 3.00, [0, 0, 0]);

  /* 弹匣：出井 → 掉出画面 → 新匣上行入井（同一根骨；出画之后再回来＝换了新匣） */
  var MAG_P = [[0.00, [0, 0, 0]], [0.50, [0, 0, 0]], [0.62, [0, -0.55, 0.15]], [0.80, [0, -2.60, 0.35]],
               [1.00, [-1.80, -7.20, 0.60]], [1.15, [-2.40, -10.40, 0.80]], [1.30, [-1.90, -8.60, 0.70]],
               [1.50, [-0.60, -4.60, 0.40]], [1.72, [-0.05, -0.75, 0.12]], [1.84, [0, 0.12, 0]],
               [1.95, [0, 0, 0]], [3.00, [0, 0, 0]]];
  var MAG_R = [[0.00, [0, 0, 0]], [0.50, [0, 0, 0]], [0.62, [-6, 0, 0]], [0.80, [-16, 0, -4]],
               [1.00, [-34, 0, -12]], [1.15, [-40, 0, -16]], [1.30, [-28, 0, -10]],
               [1.50, [-12, 0, -4]], [1.72, [-2, 0, -1]], [1.84, [0, 0, 0]],
               [1.95, [0, 0, 0]], [3.00, [0, 0, 0]]];
  MAG_P.forEach(function (k) { K(rl, 'magazine', 'position', k[0], k[1], S); });
  MAG_R.forEach(function (k) { K(rl, 'magazine', 'rotation', k[0], k[1], S); });

  /* 备用弹匣（挂在弹匣井左侧、常驻可见）：被抽走的参与动作，末了归位 */
  K(rl, 'mag_spare', 'position', 0.00, [0, 0, 0]);
  K(rl, 'mag_spare', 'position', 0.35, [0, 0, 0]);
  K(rl, 'mag_spare', 'position', 0.60, [0, 0.30, -0.25], S);
  K(rl, 'mag_spare', 'position', 0.90, [0.15, 0.75, -0.45], S);
  K(rl, 'mag_spare', 'position', 1.30, [0.15, 0.75, -0.45], S);
  K(rl, 'mag_spare', 'position', 1.65, [0, 0.30, -0.20], S);
  K(rl, 'mag_spare', 'position', 1.90, [0, 0, 0], S);
  K(rl, 'mag_spare', 'position', 3.00, [0, 0, 0]);
  K(rl, 'mag_spare', 'rotation', 0.00, [0, 0, 0]);
  K(rl, 'mag_spare', 'rotation', 0.60, [4, 0, -8], S);
  K(rl, 'mag_spare', 'rotation', 0.90, [10, 0, -16], S);
  K(rl, 'mag_spare', 'rotation', 1.30, [10, 0, -16], S);
  K(rl, 'mag_spare', 'rotation', 1.65, [4, 0, -8], S);
  K(rl, 'mag_spare', 'rotation', 1.90, [0, 0, 0], S);
  K(rl, 'mag_spare', 'rotation', 3.00, [0, 0, 0]);

  /* 战术换弹：枪栓不动、不抛壳、膛内那发留着 */
  K(rl, 'bolt', 'position', 0.00, [0, 0, 0]);
  K(rl, 'bolt', 'position', 3.00, [0, 0, 0]);
  K(rl, 'bolt', 'rotation', 0.00, [0, 0, 0]);
  K(rl, 'bolt', 'rotation', 3.00, [0, 0, 0]);
  K(rl, 'casing', 'scale', 0.00, [0, 0, 0]);
  K(rl, 'round_in', 'scale', 0.00, [0, 0, 0]);

  /* ================================================================
   * 5. reload_empty — 空仓换弹（once, 3.7167 s）  [TaCZ reload_empty 时间轴 1:1]
   *    0.00-2.10 换弹匣（枪身左倾压低，让出弹匣井）
   *    2.45-3.70 拉栓抛壳 + 上膛闭栓（枪身反向倒向抛壳窗一侧）
   *    ＝"打完最后一发 → 换弹夹 → 拉一下栓退出空弹壳 → 上弹"。
   * ================================================================ */
  var re = makeAnim('reload_empty', 3.7167, 'once');
  var EMP_R = [[0.00, [0, 0, 0]], [0.25, [-7.90, -3.41, -11.83]], [0.50, [-11.26, -5.60, -21.05]],
               [0.75, [-10.40, -4.55, -17.43]], [1.00, [-10.18, -5.10, -18.48]], [1.25, [-10.34, -4.96, -17.71]],
               [1.50, [-11.10, -5.14, -18.57]], [1.75, [-11.72, -5.38, -19.64]], [2.00, [-11.49, -5.34, -21.10]],
               [2.25, [-6.28, -3.67, -14.05]], [2.50, [4.04, -5.71, 12.14]], [2.75, [4.04, -5.37, 11.26]],
               [3.00, [1.86, -5.61, 7.55]], [3.25, [0.86, -2.59, 3.68]], [3.50, [0, 0, 0]],
               [3.7167, [0, 0, 0]]];
  var EMP_P = [[0.00, [0, 0, 0]], [0.25, [-0.22, -0.18, -0.03]], [0.50, [-0.17, -0.39, -0.17]],
               [0.75, [-0.07, -0.59, -0.15]], [1.00, [-0.29, -0.54, -0.15]], [1.25, [-0.29, -0.65, -0.15]],
               [1.50, [-0.21, -0.62, -0.15]], [1.75, [-0.18, -0.46, -0.15]], [2.00, [-0.15, -0.44, -0.15]],
               [2.25, [-0.14, -0.53, -0.15]], [2.50, [-0.17, -0.69, -0.51]], [2.75, [-0.18, -0.59, -0.69]],
               [3.00, [-0.10, -0.79, -0.71]], [3.25, [-0.08, -0.65, -0.62]], [3.50, [0, 0, 0]],
               [3.7167, [0, 0, 0]]];
  EMP_R.forEach(function (k) { K(re, 'move', 'rotation', k[0], k[1], S); });
  EMP_P.forEach(function (k) { K(re, 'move', 'position', k[0], k[1], S); });
  K(re, 'body', 'rotation', 0.00, [0, 0, 0], S);
  K(re, 'body', 'rotation', 0.50, [-1.40, 0, 0], S);
  K(re, 'body', 'rotation', 2.20, [0, 0, 0], S);
  K(re, 'body', 'rotation', 2.60, [-1.10, 0, 0], S);
  K(re, 'body', 'rotation', 3.30, [0, 0, 0], S);
  K(re, 'body', 'rotation', 3.7167, [0, 0, 0]);

  /* 弹匣：0.72 出井 → 1.25 掉出画面 → 1.40 新匣上行 → 1.94 入井 → 2.05 到位 */
  var EMAG_P = [[0.00, [0, 0, 0]], [0.60, [0, 0, 0]], [0.72, [0, -0.55, 0.15]], [0.90, [0, -2.60, 0.35]],
                [1.10, [-1.80, -7.20, 0.60]], [1.25, [-2.40, -10.40, 0.80]], [1.40, [-1.90, -8.60, 0.70]],
                [1.60, [-0.60, -4.60, 0.40]], [1.82, [-0.05, -0.75, 0.12]], [1.94, [0, 0.12, 0]],
                [2.05, [0, 0, 0]], [3.7167, [0, 0, 0]]];
  var EMAG_R = [[0.00, [0, 0, 0]], [0.60, [0, 0, 0]], [0.72, [-6, 0, 0]], [0.90, [-16, 0, -4]],
                [1.10, [-34, 0, -12]], [1.25, [-40, 0, -16]], [1.40, [-28, 0, -10]],
                [1.60, [-12, 0, -4]], [1.82, [-2, 0, -1]], [1.94, [0, 0, 0]],
                [2.05, [0, 0, 0]], [3.7167, [0, 0, 0]]];
  EMAG_P.forEach(function (k) { K(re, 'magazine', 'position', k[0], k[1], S); });
  EMAG_R.forEach(function (k) { K(re, 'magazine', 'rotation', k[0], k[1], S); });

  K(re, 'mag_spare', 'position', 0.00, [0, 0, 0]);
  K(re, 'mag_spare', 'position', 0.45, [0, 0, 0]);
  K(re, 'mag_spare', 'position', 0.70, [0, 0.30, -0.25], S);
  K(re, 'mag_spare', 'position', 1.00, [0.15, 0.75, -0.45], S);
  K(re, 'mag_spare', 'position', 1.45, [0.15, 0.75, -0.45], S);
  K(re, 'mag_spare', 'position', 1.75, [0, 0.30, -0.20], S);
  K(re, 'mag_spare', 'position', 2.00, [0, 0, 0], S);
  K(re, 'mag_spare', 'position', 3.7167, [0, 0, 0]);
  K(re, 'mag_spare', 'rotation', 0.00, [0, 0, 0]);
  K(re, 'mag_spare', 'rotation', 0.70, [4, 0, -8], S);
  K(re, 'mag_spare', 'rotation', 1.00, [10, 0, -16], S);
  K(re, 'mag_spare', 'rotation', 1.45, [10, 0, -16], S);
  K(re, 'mag_spare', 'rotation', 1.75, [4, 0, -8], S);
  K(re, 'mag_spare', 'rotation', 2.00, [0, 0, 0], S);
  K(re, 'mag_spare', 'rotation', 3.7167, [0, 0, 0]);

  /* 枪栓：2.62 抬把 60° → 2.64~3.10 后退 2.18u → 3.45 闭锁 */
  K(re, 'bolt', 'rotation', 0.00, [0, 0, 0]);
  K(re, 'bolt', 'rotation', 2.40, [0, 0, 0]);
  K(re, 'bolt', 'rotation', 2.62, [0, 0, 60]);
  K(re, 'bolt', 'rotation', 3.10, [0, 0, 60]);
  K(re, 'bolt', 'rotation', 3.45, [0, 0, 0]);
  K(re, 'bolt', 'rotation', 3.7167, [0, 0, 0]);
  K(re, 'bolt', 'position', 0.00, [0, 0, 0]);
  K(re, 'bolt', 'position', 2.40, [0, 0, 0]);
  K(re, 'bolt', 'position', 2.64, [0, 0, 2.18]);
  K(re, 'bolt', 'position', 3.10, [0, 0, 2.18]);
  K(re, 'bolt', 'position', 3.45, [0, 0, 0]);
  K(re, 'bolt', 'position', 3.7167, [0, 0, 0]);

  /* 空弹壳：2.46 现形 → 2.62 抽出 → 2.76 出抛壳窗 → 向 +X 上翻飞出画面 → 3.55 隐藏 */
  K(re, 'casing', 'scale', 0.00, [0, 0, 0]);
  K(re, 'casing', 'scale', 2.45, [0, 0, 0]);
  K(re, 'casing', 'scale', 2.46, [1, 1, 1]);
  K(re, 'casing', 'scale', 3.40, [1, 1, 1]);
  K(re, 'casing', 'scale', 3.55, [0, 0, 0]);
  K(re, 'casing', 'scale', 3.7167, [0, 0, 0]);
  K(re, 'casing', 'position', 0.00, [0, 0, 0]);
  K(re, 'casing', 'position', 2.45, [0, 0, 0]);
  K(re, 'casing', 'position', 2.62, [0, 0, 1.10]);
  K(re, 'casing', 'position', 2.76, [0.85, 0.20, 0.62]);
  K(re, 'casing', 'position', 2.96, [2.40, 1.70, 0.32], S);
  K(re, 'casing', 'position', 3.16, [4.80, 3.70, 0.12], S);
  K(re, 'casing', 'position', 3.45, [6.20, 4.70, 0.00], S);
  K(re, 'casing', 'position', 3.7167, [6.20, 4.70, 0.00]);
  K(re, 'casing', 'rotation', 0.00, [0, 0, 0]);
  K(re, 'casing', 'rotation', 2.62, [0, 0, 0]);
  K(re, 'casing', 'rotation', 2.96, [0, 300, 0], S);
  K(re, 'casing', 'rotation', 3.16, [0, 700, 0], S);
  K(re, 'casing', 'rotation', 3.45, [0, 900, 0], S);
  K(re, 'casing', 'rotation', 3.7167, [0, 900, 0]);

  /* 新子弹：3.05 在抛壳窗现身 → 3.35 被栓顶进膛 → 3.65 入膛隐藏 */
  K(re, 'round_in', 'scale', 0.00, [0, 0, 0]);
  K(re, 'round_in', 'scale', 3.04, [0, 0, 0]);
  K(re, 'round_in', 'scale', 3.05, [1, 1, 1]);
  K(re, 'round_in', 'scale', 3.60, [1, 1, 1]);
  K(re, 'round_in', 'scale', 3.65, [0, 0, 0]);
  K(re, 'round_in', 'scale', 3.7167, [0, 0, 0]);
  K(re, 'round_in', 'position', 0.00, [0, 0, 0]);
  K(re, 'round_in', 'position', 3.05, [0, 0, 0]);
  K(re, 'round_in', 'position', 3.20, [0.45, 0, 1.70]);
  K(re, 'round_in', 'position', 3.35, [0.45, 0, 0.20]);
  K(re, 'round_in', 'position', 3.50, [0.10, 0, -1.30]);
  K(re, 'round_in', 'position', 3.65, [0.02, 0.02, -2.40]);
  K(re, 'round_in', 'position', 3.7167, [0.02, 0.02, -2.40]);
  K(re, 'round_in', 'rotation', 0.00, [0, 0, 0]);
  K(re, 'round_in', 'rotation', 3.7167, [0, 0, 0]);

  /* ---------- 6. dump + verify ---------- */
  var dump = { name: 'awm', anims: [] };
  Animation.all.forEach(function (a) {
    var bones = {};
    Object.keys(a.animators || {}).forEach(function (uuid) {
      var an = a.animators[uuid];
      var chans = {};
      ['rotation', 'position', 'scale'].forEach(function (ch) {
        var arr = an[ch];
        if (!arr || !arr.length) { return; }
        var m = {};
        arr.forEach(function (k) {
          var dp = (k.data_points && k.data_points[0]) || {};
          m[String(k.time)] = { v: [dp.x || 0, dp.y || 0, dp.z || 0], i: k.interpolation || '' };
        });
        chans[ch] = m;
      });
      if (Object.keys(chans).length) { bones[an.name] = chans; }
    });
    dump.anims.push({ name: a.name, length: a.length, loop: a.loop, bones: bones });
  });

  out.animations = Animation.all.map(function (a) {
    var bones = Object.keys(a.animators || {});
    var keys = 0;
    bones.forEach(function (u) {
      var an2 = a.animators[u];
      ['rotation', 'position', 'scale'].forEach(function (c) { if (an2[c]) { keys += an2[c].length; } });
    });
    return { name: a.name, length: a.length, loop: a.loop, bones: bones.length, keys: keys };
  });
  out.total_animations = Animation.all.length;

  var dumpFs = null;
  try {
    if (typeof globalThis !== 'undefined' && globalThis.__awm_fs__) { dumpFs = globalThis.__awm_fs__; }
    else if (typeof require === 'function') { dumpFs = require('fs'); }
  } catch (eFs) { out.warnings.push('fs lookup:' + eFs.message); }
  try {
    dumpFs.writeFileSync(DUMP_PATH, JSON.stringify(dump, null, 1), 'utf8');
    out.dump = DUMP_PATH + ' (' + JSON.stringify(dump).length + ' bytes)';
  } catch (e5) { out.warnings.push('dump:' + e5.message); }

  try {
    if (Animation.all[0]) {
      Animation.all[0].select();
      Timeline.setTime(0.5);
      if (typeof Animator !== 'undefined' && Animator.preview) { Animator.preview(); }
      if (Canvas.updateAllBones) { Canvas.updateAllBones(); }
    }
  } catch (e4) { out.warnings.push('preview:' + e4.message); }
  if (typeof Preview !== 'undefined') { Preview.all.forEach(function (v) { if (v.canvas) { v.render(); } }); }
  return out;
})()
