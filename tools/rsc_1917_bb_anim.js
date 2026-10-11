/* HexaLunar Calamity - RSC M1917（法国半自动步枪）动画集
 * 在 Blockbench 里经 MCP risky_eval 跑（见 tools/rsc_1917_anim.py 的包装）。
 *
 * 通道铁律：逐骨 rotation / position（隐藏件用**本骨** scale 0），绝不整体缩放（美术规范.md §5）
 * 轴向铁律：枪口 = -Z | 上 = +Y | +X = 射手右侧 | 位置单位 = 模型单位 u | 16u = 1 block
 * 符号（按本模型几何实测，非推导）：
 *   move/body 的 rotX **为正 = 抬枪口**（枪口在 -Z，rotX>0 时 y' = -z·sinθ > 0）
 *   position 的 +Z = 向后（朝托底）、+Y = 向上
 *   mag_cover 的 rotX **为正 = 盖向后下方转开**（铰链在**前端**：rotX>0 时盖尾 y' = -z·sinθ < 0）
 *   bolt 的 position +Z = 后拉（真机行程 85mm = 1.36u）
 *   clip 的 position +Y = 自下往上插进弹匣（**纯平移，不带翻转**——用户在 M1 上明确过这条）
 *
 * ★ 动作按**真 RSC M1917**走，而不是照抄 M1 加兰德 ★
 *   1) 供弹 = 5 发漏夹**从下方**插进固定弹匣；弹匣盖铰链在**前端**，松开卡榫后向前下方敞开。
 *      ⇒ 卸空漏夹/插新漏夹**不需要动枪机**（枪机在弹匣箱上方，不挡井口）——
 *        这是与 M1 最本质的差别（M1 是从机匣上方压入，必须先拉机柄到底）。
 *   2) 空仓换弹（真机手册顺序）：
 *      ①左手离托 → ②按下弹匣盖卡榫、盖向前下方敞开 → ③废漏夹掉出 →
 *      ④新漏夹自下往上插到位 → ⑤合盖 → ⑥拉一次拉机柄送弹入膛、松手闭锁。
 *   3) M1917 **没有空仓挂机**（M1918 才有）⇒ 最后一发打完后枪机自动复进、停在闭锁位；
 *      empty 的最后一发（shoot_last）因此也是"打完 → 枪机往返 → 停闭锁"，
 *      换弹起手不用先"补拉一次"（M1 没这个自由度，它有挂机）。
 *   4) 半自动循环 = 每发导气活塞推枪机走一个**全行程** 1.36u（要越过漏夹里剩余弹的底缘）。
 *
 * 骨骼（几何 tools/rsc_1917_geo.js 为准）：
 *   root → move → body{ barrier? 见下 } · stock
 *   body → barrel / forend(→hand_l) / cover / bolt / mag_cover / clip / clip_empty /
 *          casing / round_in / trigger / safety / magazine
 *
 * 隐藏件（本骨 scale 0）：casing（抛壳）、clip_empty（空漏夹）、round_in（单发补弹那发）
 * cover = 可拆钢盖（野战分解才取下），本套片段里它是静止件。
 */
(function () {
  var DUMP = 'F:/mcmod/art/rsc_1917/_anim_raw.json';
  var out = { steps: [], warnings: [] };
  var G = {};
  Group.all.forEach(function (g) { G[g.name] = g; });

  /* ---------- 0. 清掉旧动画 ---------- */
  try { Project.animations.slice().forEach(function (a) { if (a.remove) a.remove(); }); } catch (e) { out.warnings.push('clean:' + e.message); }
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
  var seenKeys = {};
  function K(a, bone, channel, time, vals, interp) {
    var g = G[bone];
    if (!g) { out.warnings.push('missing bone ' + bone); return null; }
    var an = a.getBoneAnimator(g);
    if (!an) { out.warnings.push('no animator ' + bone); return null; }
    /* 导出按 24fps 吸附关键帧（Math.round）。这里先吸附：两个相隔 <1/24s 的键
       会在导出时并到同一帧被丢掉（换弹里"旧漏夹消失/新漏夹出现"的 scale 开关就吃过这个亏）。 */
    var t = Math.round(time * 24) / 24;
    var id = a.name + '|' + bone + '|' + channel + '|' + t;
    if (seenKeys[id]) out.warnings.push('KEYFRAME COLLISION ' + id);
    seenKeys[id] = true;
    var k = new Keyframe({ channel: channel, time: t, interpolation: interp || 'linear',
                           data_points: [{ x: vals[0], y: vals[1], z: vals[2] }] }, null, an);
    an.pushKeyframe(k);
    return k;
  }
  var S = 'catmullrom';
  function keys(a, bone, ch, list, interp) { list.forEach(function (k) { K(a, bone, ch, k[0], k[1], interp || S); }); }
  function rest(a, t, bones) {
    bones.forEach(function (b) {
      K(a, b, 'position', t, [0, 0, 0]);
      K(a, b, 'rotation', t, [0, 0, 0]);
    });
  }
  var RESTBONES = ['cover', 'magazine', 'additional_magazine', 'trigger', 'safety', 'clip', 'clip_empty', 'round_in'];
  /* 静止位：抛壳/空漏夹/单发弹都没有；弹匣里是满漏夹 */
  function statics(a, t) { rest(a, t, RESTBONES); }
  function hide(a, t) {
    K(a, 'casing', 'scale', t, [0, 0, 0]);
    K(a, 'clip_empty', 'scale', t, [0, 0, 0]);
    K(a, 'round_in', 'scale', t, [0, 0, 0]);
    K(a, 'clip', 'scale', t, [1, 1, 1]);
  }
  var BOLT = 1.36;                 /* 真机行程 85mm */

  /* ================================================================
   * 1. static_idle —— 持枪待机（loop, 2.0s）
   *    手持姿势就在这里：枪身轻微呼吸摆动 + 左手托在前托下（hand_l 骨）。
   * ================================================================ */
  var idle = makeAnim('static_idle', 2.0, 'loop');
  keys(idle, 'move', 'rotation', [[0, [0, 0, 0]], [0.5, [0.40, 0.22, 0]], [1.0, [0.10, 0.40, 0]],
                                  [1.5, [-0.26, 0.14, 0]], [2.0, [0, 0, 0]]]);
  keys(idle, 'move', 'position', [[0, [0, 0, 0]], [0.5, [0.02, -0.05, 0.03]], [1.0, [0, -0.08, 0]],
                                  [1.5, [-0.02, -0.03, -0.02]], [2.0, [0, 0, 0]]]);
  keys(idle, 'body', 'rotation', [[0, [0, 0, 0]], [1.0, [-0.20, 0, 0]], [2.0, [0, 0, 0]]]);
  keys(idle, 'bolt', 'position', [[0, [0, 0, 0]], [2.0, [0, 0, 0]]]);
  keys(idle, 'barrel', 'rotation', [[0, [0, 0, 0]], [1.0, [0.06, 0, 0]], [2.0, [0, 0, 0]]]);
  statics(idle, 0); hide(idle, 0);
  K(idle, 'mag_cover', 'rotation', 0, [0, 0, 0]); K(idle, 'mag_cover', 'position', 0, [0, 0, 0]);
  K(idle, 'trigger', 'rotation', 0, [0, 0, 0]); K(idle, 'trigger', 'rotation', 2.0, [0, 0, 0]);

  /* ================================================================
   * 2. draw —— 出枪到位（once, 1.0s）
   *    从下后方抬起、枪口从下往上压到水平；到位前枪机轻轻坐实一下（闭锁感）。
   * ================================================================ */
  var dr = makeAnim('draw', 1.0, 'once');
  keys(dr, 'move', 'position', [[0, [0, -2.20, 0.90]], [0.35, [0, -0.35, 0.12]], [0.55, [0, 0.06, -0.04]], [0.9, [0, 0, 0]]]);
  keys(dr, 'move', 'rotation', [[0, [-14.0, 3.0, 4.0]], [0.35, [-3.0, 1.0, 1.0]], [0.55, [1.2, -0.4, 0]], [0.9, [0, 0, 0]]]);
  keys(dr, 'body', 'rotation', [[0, [2.40, 0, 0]], [0.5, [-0.60, 0, 0]], [0.9, [0, 0, 0]]]);
  keys(dr, 'mag_cover', 'rotation', [[0, [0, 0, 0]], [0.9, [0, 0, 0]]]);
  statics(dr, 0); hide(dr, 0);
  /* 枪机：从微微后开的位置坐实（真机装上漏夹后是自由前冲闭锁的，这里给一个"坐实"） */
  keys(dr, 'bolt', 'position', [[0, [0, 0, 0.42]], [0.30, [0, 0, 0.46]], [0.55, [0, 0, 0.04]], [0.62, [0, 0, 0]], [0.9, [0, 0, 0]]]);

  /* ================================================================
   * 3. shoot —— 单发后坐（once, 0.6s）半自动：导气活塞自动推一个全行程
   * ================================================================ */
  var sh = makeAnim('shoot', 0.6, 'once');
  keys(sh, 'move', 'rotation', [[0, [0, 0, 0]], [0.05, [2.60, 0.30, 0]], [0.12, [1.90, -0.20, 0]],
                                [0.22, [0.70, 0.10, 0]], [0.35, [-0.25, 0, 0]], [0.5, [0, 0, 0]], [0.6, [0, 0, 0]]]);
  keys(sh, 'move', 'position', [[0, [0, 0, 0]], [0.05, [0, 0.28, 0.62]], [0.12, [0, 0.24, 0.44]],
                                [0.22, [0, 0.12, 0.20]], [0.35, [0, -0.04, -0.06]], [0.5, [0, 0, 0]], [0.6, [0, 0, 0]]]);
  keys(sh, 'body', 'rotation', [[0, [0, 0, 0]], [0.05, [-1.10, 0, 0]], [0.40, [0, 0, 0]], [0.6, [0, 0, 0]]]);
  keys(sh, 'barrel', 'rotation', [[0, [0, 0, 0]], [0.05, [-0.30, 0, 0]], [0.30, [0, 0, 0]], [0.6, [0, 0, 0]]]);
  /* 扳机：扣下去 → 松开 */
  keys(sh, 'trigger', 'rotation', [[0, [0, 0, 0]], [0.03, [7.0, 0, 0]], [0.12, [7.0, 0, 0]], [0.30, [0, 0, 0]], [0.6, [0, 0, 0]]]);
  /* 枪机全行程 */
  keys(sh, 'bolt', 'position', [[0, [0, 0, 0]], [0.05, [0, 0, BOLT * 0.68]], [0.075, [0, 0, BOLT]],
                                [0.14, [0, 0, 0.24]], [0.20, [0, 0, 0]], [0.6, [0, 0, 0]]]);
  /* 抛壳：8mm 勒贝尔空壳从 +X 抛壳窗翻飞出去 */
  keys(sh, 'casing', 'position', [[0, [0, 0, 0]], [0.075, [0, 0.04, 0.02]], [0.12, [0.35, 0.55, 0.10]],
                                  [0.20, [0.95, 1.55, 0.50]], [0.35, [1.90, 2.60, 1.30]], [0.45, [2.60, 3.40, 1.90]]]);
  keys(sh, 'casing', 'rotation', [[0, [0, 0, 0]], [0.12, [-25, 0, -40]], [0.20, [-70, 0, -160]],
                                  [0.35, [-140, 0, -320]], [0.45, [-190, 0, -430]]]);
  K(sh, 'casing', 'scale', 0, [0, 0, 0]); K(sh, 'casing', 'scale', 0.075, [1, 1, 1]); K(sh, 'casing', 'scale', 0.45, [0, 0, 0]);
  statics(sh, 0);
  K(sh, 'clip_empty', 'scale', 0, [0, 0, 0]); K(sh, 'round_in', 'scale', 0, [0, 0, 0]);
  K(sh, 'clip', 'scale', 0, [1, 1, 1]); K(sh, 'mag_cover', 'rotation', 0, [0, 0, 0]);

  /* ================================================================
   * 4. shoot_last —— 最后一发（once, 1.2s）
   *    M1917 **无空仓挂机**：打完枪机照样复进、停在闭锁位；空漏夹仍被合着的弹匣盖兜在匣里
   *    （要等换弹时开盖才掉出来）—— 与 M1 加兰德"最后一发后枪机挂住 + 漏夹弹飞"完全不同。
   * ================================================================ */
  var sl = makeAnim('shoot_last', 1.2, 'once');
  keys(sl, 'move', 'rotation', [[0, [0, 0, 0]], [0.05, [2.60, 0.30, 0]], [0.12, [1.90, -0.20, 0]],
                                [0.22, [0.70, 0.10, 0]], [0.35, [-0.25, 0, 0]], [0.6, [0, 0, 0]], [1.2, [0, 0, 0]]]);
  keys(sl, 'move', 'position', [[0, [0, 0, 0]], [0.05, [0, 0.28, 0.62]], [0.12, [0, 0.24, 0.44]],
                                [0.22, [0, 0.12, 0.20]], [0.35, [0, -0.04, -0.06]], [0.6, [0, 0, 0]], [1.2, [0, 0, 0]]]);
  keys(sl, 'body', 'rotation', [[0, [0, 0, 0]], [0.05, [-1.10, 0, 0]], [0.40, [0, 0, 0]], [1.2, [0, 0, 0]]]);
  keys(sl, 'trigger', 'rotation', [[0, [0, 0, 0]], [0.03, [7.0, 0, 0]], [0.12, [7.0, 0, 0]], [0.30, [0, 0, 0]], [1.2, [0, 0, 0]]]);
  /* 枪机：全行程 → 复进 → 闭锁停住（不挂机） */
  keys(sl, 'bolt', 'position', [[0, [0, 0, 0]], [0.05, [0, 0, BOLT * 0.68]], [0.075, [0, 0, BOLT]],
                                [0.16, [0, 0, 0.30]], [0.26, [0, 0, 0]], [1.2, [0, 0, 0]]]);
  keys(sl, 'casing', 'position', [[0, [0, 0, 0]], [0.075, [0, 0.04, 0.02]], [0.12, [0.35, 0.55, 0.10]],
                                  [0.20, [0.95, 1.55, 0.50]], [0.35, [1.90, 2.60, 1.30]], [0.5, [2.60, 3.40, 1.90]]]);
  keys(sl, 'casing', 'rotation', [[0, [0, 0, 0]], [0.12, [-25, 0, -40]], [0.20, [-70, 0, -160]],
                                  [0.35, [-140, 0, -320]], [0.5, [-190, 0, -430]]]);
  K(sl, 'casing', 'scale', 0, [0, 0, 0]); K(sl, 'casing', 'scale', 0.075, [1, 1, 1]); K(sl, 'casing', 'scale', 0.5, [0, 0, 0]);
  /* 这一发之后匣里空了 ⇒ 视觉上换成空漏夹（在匣里，盖上盖看不见，为下一次换弹接力） */
  K(sl, 'clip', 'scale', 0, [1, 1, 1]); K(sl, 'clip', 'scale', 0.10, [0, 0, 0]);
  K(sl, 'clip_empty', 'scale', 0, [0, 0, 0]); K(sl, 'clip_empty', 'scale', 0.125, [1, 1, 1]);
  K(sl, 'round_in', 'scale', 0, [0, 0, 0]);
  rest(sl, 0, ['cover', 'magazine', 'additional_magazine', 'safety']);
  K(sl, 'mag_cover', 'rotation', 0, [0, 0, 0]); K(sl, 'magazine', 'position', 0, [0, 0, 0]);

  /* ================================================================
   * 5. bolt —— 手动拉栓（once, 1.1s）
   *    真机行程 85mm = 1.36u，纯平移（拉机柄在机匣右侧，经弯曲传动杆直连枪机，不旋转）
   * ================================================================ */
  var bo = makeAnim('bolt', 1.1, 'once');
  keys(bo, 'bolt', 'position', [[0, [0, 0, 0]], [0.18, [0, 0, 0.36]], [0.42, [0, 0, BOLT]], [0.62, [0, 0, BOLT]],
                                [0.80, [0, 0, 0.08]], [0.90, [0, 0, 0]], [1.1, [0, 0, 0]]]);
  keys(bo, 'move', 'rotation', [[0, [0, 0, 0]], [0.40, [-1.40, 0.50, 0]], [0.85, [0.30, 0, 0]], [1.1, [0, 0, 0]]]);
  keys(bo, 'move', 'position', [[0, [0, 0, 0]], [0.40, [0.10, -0.06, 0.16]], [0.90, [0, 0, 0]], [1.1, [0, 0, 0]]]);
  keys(bo, 'body', 'rotation', [[0, [0, 0, 0]], [0.42, [0.80, 0, 0]], [0.90, [0, 0, 0]], [1.1, [0, 0, 0]]]);
  /* 抽壳：枪机退到位时弹壳脱出抛壳窗 */
  K(bo, 'casing', 'scale', 0, [0, 0, 0]); K(bo, 'casing', 'scale', 0.42, [1, 1, 1]);
  keys(bo, 'casing', 'position', [[0.42, [0, 0, 0]], [0.50, [0.42, 0.60, 0.14]], [0.62, [1.10, 1.70, 0.55]],
                                  [0.80, [2.10, 2.90, 1.40]], [0.95, [2.90, 3.70, 2.10]]]);
  keys(bo, 'casing', 'rotation', [[0.42, [0, 0, 0]], [0.62, [-90, 0, -180]], [0.80, [-200, 0, -400]], [0.95, [-280, 0, -540]]]);
  K(bo, 'casing', 'scale', 0.95, [0, 0, 0]);
  statics(bo, 0);
  K(bo, 'clip', 'scale', 0, [1, 1, 1]); K(bo, 'clip_empty', 'scale', 0, [0, 0, 0]); K(bo, 'round_in', 'scale', 0, [0, 0, 0]);
  K(bo, 'mag_cover', 'rotation', 0, [0, 0, 0]);

  /* ================================================================
   * 6. reload_tactical —— 未空仓换弹（once, 2.6s）
   *    真机：枪机不挡井口 ⇒ 不必先拉栓。整段 =
   *      0.10-0.30 右手按下弹匣盖卡榫（真机在护圈前下方）
   *      0.28-0.46 盖绕**前端铰链**向前下方敞开 60°
   *      0.46-0.62 残漏夹自行掉出（弹匣里剩几发就掉几发，这里整块掉）
   *      0.62-1.00 新漏夹自下往上插到位（纯平移）、1.02 微弹一下坐实
   *      1.00-1.16 合盖、卡榫回位
   *      1.24-1.86 拉一次拉机柄送弹入膛、松手闭锁
   *      1.86-2.60 回 rest
   * ================================================================ */
  var rt = makeAnim('reload_tactical', 2.6, 'once');
  /* 弹匣盖：绕前端铰链旋转开合（pivot 在 geo 里，位置不动） */
  keys(rt, 'mag_cover', 'rotation', [[0, [0, 0, 0]], [0.28, [0, 0, 0]], [0.46, [60, 0, 0]],
                                     [1.00, [60, 0, 0]], [1.16, [0, 0, 0]], [2.6, [0, 0, 0]]]);
  /* 卡榫（bone safety = 护圈前下方的盖卡榫 + 机匣左后保险，同骨）：按下 → 回位 */
  keys(rt, 'safety', 'position', [[0, [0, 0, 0]], [0.14, [0, -0.055, 0]], [0.30, [0, -0.055, 0]],
                                  [0.52, [0, 0, 0]], [2.6, [0, 0, 0]]]);
  /* 残漏夹：0.46 整块消失 → 空漏夹骨接棒掉出 → 1.02 消失 */
  K(rt, 'clip', 'scale', 0, [1, 1, 1]); K(rt, 'clip', 'scale', 0.46, [0, 0, 0]);
  K(rt, 'clip_empty', 'scale', 0, [0, 0, 0]);
  K(rt, 'clip_empty', 'scale', 0.484, [1, 1, 1]);
  keys(rt, 'clip_empty', 'position', [[0.484, [0, 0, 0]], [0.62, [0, -1.55, 0]], [0.86, [0, -3.10, 0]]]);
  keys(rt, 'clip_empty', 'rotation', [[0.484, [0, 0, 0]], [0.62, [22, 0, -14]], [0.86, [46, 0, -30]]]);
  K(rt, 'clip_empty', 'scale', 1.00, [0, 0, 0]);
  /* 新漏夹：自下往上，纯平移（rotation 全 0，x/z 位移全 0） */
  K(rt, 'clip', 'scale', 0.708, [1, 1, 1]);
  keys(rt, 'clip', 'position', [[0.708, [0, -2.30, 0]], [0.86, [0, -0.95, 0]], [0.99, [0, -0.03, 0]],
                                [1.04, [0, 0.06, 0]], [1.12, [0, 0, 0]], [2.6, [0, 0, 0]]]);
  keys(rt, 'clip', 'rotation', [[0.708, [0, 0, 0]], [1.12, [0, 0, 0]], [2.6, [0, 0, 0]]]);
  /* 枪机：送弹入膛（拉到底 → 松手闭锁 → 坐实） */
  keys(rt, 'bolt', 'position', [[0, [0, 0, 0]], [1.20, [0, 0, 0]], [1.42, [0, 0, BOLT]], [1.56, [0, 0, BOLT * 0.85]],
                                [1.68, [0, 0, 0.16]], [1.74, [0, 0, 0]], [2.6, [0, 0, 0]]]);
  keys(rt, 'move', 'rotation', [[0, [0, 0, 0]], [0.30, [-2.00, 0.55, 0]], [1.05, [-1.10, 0.28, 0]],
                                [1.42, [-1.60, 0.30, 0]], [1.80, [0.70, 0, 0]], [2.6, [0, 0, 0]]]);
  keys(rt, 'move', 'position', [[0, [0, 0, 0]], [0.30, [0.06, -0.09, 0.09]], [1.10, [0, -0.05, 0.10]],
                                [1.50, [0, -0.06, 0.14]], [1.84, [0, 0.05, -0.06]], [2.6, [0, 0, 0]]]);
  keys(rt, 'body', 'rotation', [[0, [0, 0, 0]], [0.40, [0.65, 0, 0]], [1.05, [-0.85, 0, 0]],
                                [1.45, [0.50, 0, 0]], [1.86, [0.40, 0, 0]], [2.6, [0, 0, 0]]]);
  keys(rt, 'hand_l', 'rotation', [[0, [0, 0, 0]], [0.34, [12, 0, 0]], [1.10, [6, 0, 0]], [1.9, [0, 0, 0]], [2.6, [0, 0, 0]]]);
  K(rt, 'casing', 'scale', 0, [0, 0, 0]); K(rt, 'round_in', 'scale', 0, [0, 0, 0]);
  rest(rt, 0, ['magazine', 'additional_magazine', 'trigger', 'cover']);

  /* ================================================================
   * 7. reload_empty —— 空仓换弹（once, 3.6s）★真机六拍★
   *      0.00-0.34 左手离托、枪身向左下让位（右手腾出来）
   *      0.20-0.40 按弹匣盖卡榫
   *      0.38-0.58 盖向前下方敞开 60°
   *      0.58-0.78 空漏夹掉出
   *      0.96-1.62 新漏夹自下往上插到位（纯平移）
   *      1.66-1.94 合盖
   *      2.04-2.72 拉一次拉机柄送弹入膛、松手闭锁
   *      2.72-3.60 回 rest
   * ================================================================ */
  var re = makeAnim('reload_empty', 3.6, 'once');
  keys(re, 'mag_cover', 'rotation', [[0, [0, 0, 0]], [0.38, [0, 0, 0]], [0.58, [60, 0, 0]],
                                     [1.66, [60, 0, 0]], [1.94, [0, 0, 0]], [3.6, [0, 0, 0]]]);
  keys(re, 'safety', 'position', [[0, [0, 0, 0]], [0.20, [0, -0.055, 0]], [0.40, [0, -0.055, 0]],
                                  [0.62, [0, 0, 0]], [3.6, [0, 0, 0]]]);
  /* 空漏夹：换弹起手时匣里那个（shoot_last 结尾留下的）整块掉出 */
  K(re, 'clip', 'scale', 0, [0, 0, 0]);
  K(re, 'clip_empty', 'scale', 0, [1, 1, 1]);
  keys(re, 'clip_empty', 'position', [[0, [0, 0, 0]], [0.58, [0, 0, 0]], [0.78, [0, -1.70, 0]], [1.02, [0, -3.30, 0]]]);
  keys(re, 'clip_empty', 'rotation', [[0, [0, 0, 0]], [0.58, [0, 0, 0]], [0.78, [24, 0, -16]], [1.02, [48, 0, -32]]]);
  K(re, 'clip_empty', 'scale', 1.06, [0, 0, 0]);
  /* 新漏夹：0.958 换肤（第 23 帧关、第 24 帧开 —— 必须错帧，否则导出时被并成一个键） */
  K(re, 'clip', 'scale', 0.9583, [1, 1, 1]);
  keys(re, 'clip', 'position', [[0.9583, [0, -2.60, 0]], [1.20, [0, -1.10, 0]], [1.50, [0, -0.06, 0]],
                                [1.58, [0, 0.07, 0]], [1.68, [0, 0, 0]], [3.6, [0, 0, 0]]]);
  keys(re, 'clip', 'rotation', [[0.9583, [0, 0, 0]], [1.68, [0, 0, 0]], [3.6, [0, 0, 0]]]);
  /* 枪机：送弹入膛 */
  keys(re, 'bolt', 'position', [[0, [0, 0, 0]], [2.04, [0, 0, 0]], [2.30, [0, 0, BOLT]], [2.46, [0, 0, BOLT * 0.86]],
                                [2.60, [0, 0, 0.18]], [2.68, [0, 0, 0]], [3.6, [0, 0, 0]]]);
  keys(re, 'move', 'rotation', [[0, [0, 0, 0]], [0.34, [-3.20, 1.10, 0]], [0.62, [-2.40, 0.80, 0]],
                                [1.30, [-1.30, 0.40, 0]], [1.90, [-0.60, 0.20, 0]],
                                [2.30, [-1.80, 0.35, 0]], [2.78, [0.80, 0, 0]], [3.6, [0, 0, 0]]]);
  keys(re, 'move', 'position', [[0, [0, 0, 0]], [0.34, [0.10, -0.16, 0.14]], [1.30, [0, -0.08, 0.12]],
                                [1.94, [0, -0.04, 0.06]], [2.40, [0, -0.08, 0.16]],
                                [2.84, [0, 0.06, -0.07]], [3.6, [0, 0, 0]]]);
  keys(re, 'body', 'rotation', [[0, [0, 0, 0]], [0.50, [0.90, 0, 0]], [1.30, [-0.95, 0, 0]],
                                [1.90, [0.60, 0, 0]], [2.40, [0.55, 0, 0]], [2.90, [-0.45, 0, 0]], [3.6, [0, 0, 0]]]);
  keys(re, 'hand_l', 'rotation', [[0, [0, 0, 0]], [0.34, [16, 0, 0]], [1.30, [8, 0, 0]], [2.2, [2, 0, 0]], [3.6, [0, 0, 0]]]);
  K(re, 'casing', 'scale', 0, [0, 0, 0]); K(re, 'round_in', 'scale', 0, [0, 0, 0]);
  rest(re, 0, ['magazine', 'additional_magazine', 'trigger', 'cover']);

  /* ================================================================
   * 8. single_load —— 单发补弹（once, 1.5s）
   *    真机也能这么干：把枪机拉到底，直接往弹膛里放一发，再放枪机上膛。
   *    （漏夹供弹枪零星补弹的标准手法；M1 手册同样这么写。）
   * ================================================================ */
  var sg = makeAnim('single_load', 1.5, 'once');
  keys(sg, 'bolt', 'position', [[0, [0, 0, 0]], [0.30, [0, 0, BOLT]], [0.56, [0, 0, BOLT]],
                                [0.78, [0, 0, BOLT * 0.80]], [0.98, [0, 0, 0.14]], [1.06, [0, 0, 0]], [1.5, [0, 0, 0]]]);
  /* 那一发：从机匣上方落下、滑进弹膛，枪机闭锁后藏起来 */
  K(sg, 'round_in', 'scale', 0, [0, 0, 0]); K(sg, 'round_in', 'scale', 0.3333, [1, 1, 1]);
  keys(sg, 'round_in', 'position', [[0.3333, [0.10, 1.15, 0.35]], [0.50, [0.02, 0.42, 0.10]],
                                    [0.62, [0, 0, 0]], [0.72, [0, 0.02, 0]], [0.86, [0, 0, 0]]]);
  keys(sg, 'round_in', 'rotation', [[0.3333, [-18, 0, 0]], [0.50, [-6, 0, 0]], [0.62, [0, 0, 0]], [0.86, [0, 0, 0]]]);
  K(sg, 'round_in', 'scale', 1.0833, [0, 0, 0]);
  keys(sg, 'move', 'rotation', [[0, [0, 0, 0]], [0.32, [-1.60, 0.40, 0]], [0.90, [-0.50, 0.10, 0]], [1.5, [0, 0, 0]]]);
  keys(sg, 'move', 'position', [[0, [0, 0, 0]], [0.32, [0.06, -0.05, 0.12]], [0.95, [0, 0, 0]], [1.5, [0, 0, 0]]]);
  keys(sg, 'body', 'rotation', [[0, [0, 0, 0]], [0.32, [0.60, 0, 0]], [1.0, [-0.30, 0, 0]], [1.5, [0, 0, 0]]]);
  keys(sg, 'hand_l', 'rotation', [[0, [0, 0, 0]], [0.40, [10, 0, 0]], [1.1, [3, 0, 0]], [1.5, [0, 0, 0]]]);
  K(sg, 'casing', 'scale', 0, [0, 0, 0]); K(sg, 'clip', 'scale', 0, [1, 1, 1]); K(sg, 'clip_empty', 'scale', 0, [0, 0, 0]);
  K(sg, 'mag_cover', 'rotation', 0, [0, 0, 0]);
  rest(sg, 0, ['magazine', 'additional_magazine', 'trigger', 'safety', 'cover']);

  /* ---------- dump 原始关键帧（由 tools/rsc_1917_anim.py 落盘 + 转 GeckoLib） ---------- */
  var dump = { name: 'rsc_1917', anims: [] };
  Animation.all.forEach(function (a) {
    var bones = {};
    Object.keys(a.animators || {}).forEach(function (uuid) {
      var an = a.animators[uuid];
      var gname = (an && an.group && an.group.name) || '';
      if (!gname) { for (var gi = 0; gi < Group.all.length; gi++) { if (Group.all[gi].uuid === uuid) { gname = Group.all[gi].name; break; } } }
      if (!gname) gname = uuid;
      var chans = {};
      ['rotation', 'position', 'scale'].forEach(function (ch) {
        var arr = an[ch];
        if (!arr || !arr.length) return;
        chans[ch] = arr.map(function (k) { return { t: +k.time.toFixed(4), v: [k.get('x'), k.get('y'), k.get('z')], i: k.interpolation }; });
      });
      if (Object.keys(chans).length) bones[gname] = chans;
    });
    dump.anims.push({ name: a.name, length: a.length, loop: a.loop, bones: bones });
  });
  out.animation_dump = dump;
  out.animations = Animation.all.map(function (a) {
    return { name: a.name, length: a.length, loop: a.loop,
             bones: Object.keys(a.animators || {}).length,
             keys: Object.keys(a.animators || {}).reduce(function (s, u) {
               var an = a.animators[u]; if (!an) return s;
               ['rotation', 'position', 'scale'].forEach(function (c) { if (an[c]) s += an[c].length; });
               return s;
             }, 0) };
  });
  if (typeof Preview !== 'undefined') Preview.all.forEach(function (v) { if (v.canvas) v.render(); });
  return out;
})()