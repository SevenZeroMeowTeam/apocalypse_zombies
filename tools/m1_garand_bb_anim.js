/* HexaLunar Calamity - M1 加兰德 动画集（Blockbench, 经 MCP risky_eval 跑）
 *   (function(){var fs=require('fs');return (0,eval)(fs.readFileSync('F:/mcmod/tools/m1_garand_bb_anim.js','utf8'));})()
 *
 * 通道铁律：逐骨 rotation / position（隐藏件用本骨 scale 0），绝不整体缩放（美术规范.md §5）
 * 轴向铁律：枪口 = -Z | 上 = +Y | +X = 射手右侧 | 位置单位 = 模型单位(u) | 16u = 1 block
 * 符号（本模型实测，非推导）：move 的 rotX **为正 = 抬枪口**
 *   （静止枪口冠 Y=2.353 → rotX +8° 得 Y=4.153，-8° 得 0.543）；位置 +Z = 向后（枪口在 -Z）
 *
 * 动作集 = TaCZ 通用步枪那套（static_idle / draw / shoot / bolt / reload_tactical / reload_empty），
 * 但运动按**真 M1 加兰德**走，依据 US Army ARDEC《M1 Garand Operation and Maintenance Guide》
 * (2013-06-01, §3.2 Loading the Rifle / §3.4 Functioning)：
 *   手册原文顺序 = ①"pull the operating rod handle all the way to the rear"
 *                  ②"place the clip on top of the follower assembly … press the clip straight down
 *                     into the receiver until it latches"
 *                  ③"remove your hand and allow the bolt to travel forward freely
 *                     —  note that the operating rod is NOT held to the rear after fully inserting a loaded clip"
 *                  ④"it may be necessary to strike the back of the operating rod handle with the heel of the
 *                     right hand to fully close and lock the bolt"
 *   ⇒ 换弹（空仓）= 拉手柄到底 → 盖抬起 → 空漏夹弹飞("ping") → 新漏夹压入卡住 → 盖合上
 *                  → **枪机被漏夹自动释放、自由前冲** → 拍拉机柄补到位（不是人工拉放）
 *   ⇒ 换弹（战术）= 未空仓时枪机是闭锁的，井口被枪机挡死 ⇒ 同样必须先拉到底，只是更快
 *   ⇒ 拉栓      = 右侧导气杆手柄前后来回（纯平移）
 *   射        = 半自动，每发导气杆自动走一个**全行程**（要越过漏夹末弹底缘）
 *
 * 行程上限（几何约束，非喜好）：bolt 组的方块占 120…740mm（枪口起算），机匣尾端 799mm
 *   ⇒ 模型能给的行程 ≈ 1.10u(69mm)；真机需 ≥ .30-06 弹长 85mm(1.36u) 才能越过漏夹末弹底缘。
 *   要彻底真机化得改几何（bolt 组后段前移 ~20mm 或加长机匣），见 art/m1garand/README.md「待办」。
 *   抛壳      = 弹壳从 +X 抛壳窗翻飞出去（锚点 0.85, 2.88, -1.05）
 */
(function () {
  var DUMP = 'F:/mcmod/art/m1garand/_anim_raw.json';
  var out = { steps: [], warnings: [] };
  var G = {};
  Group.all.forEach(function (g) { G[g.name] = g; });

  /* ---------- 0. wipe previous animations ---------- */
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
    /* 导出按 24fps 吸附关键帧（Math.round，半点进位）。这里先吸附，否则两个相隔 <1/24s 的键
       会在导出时并到同一帧而被丢掉（换弹里"旧漏夹消失/新漏夹出现"的 scale 开关就吃过这个亏）。 */
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
  var HIDE = ['casing', 'clip_in'];   /* 静止时藏件：本骨 scale 0（逐骨，非整体缩放）*/

  /* ================================================================
   * 1. static_idle —— 持枪待机（loop, 2.0 s）
   * ================================================================ */
  var idle = makeAnim('static_idle', 2.0, 'loop');
  keys(idle, 'move', 'rotation', [[0, [0, 0, 0]], [0.5, [0.45, 0.25, 0]], [1.0, [0.12, 0.45, 0]],
                                  [1.5, [-0.30, 0.16, 0]], [2.0, [0, 0, 0]]]);
  keys(idle, 'move', 'position', [[0, [0, 0, 0]], [0.5, [0.02, -0.05, 0.03]], [1.0, [0, -0.08, 0]],
                                  [1.5, [-0.02, -0.03, -0.02]], [2.0, [0, 0, 0]]]);
  keys(idle, 'body', 'rotation', [[0, [0, 0, 0]], [1.0, [-0.22, 0, 0]], [2.0, [0, 0, 0]]]);
  rest(idle, 0, ['bolt', 'cover', 'magazine', 'trigger']);
  K(idle, 'casing', 'scale', 0, [0, 0, 0]); K(idle, 'clip_in', 'scale', 0, [0, 0, 0]);

  /* ================================================================
   * 2. draw —— 出枪到位（once, 0.9 s）
   * ================================================================ */
  var dr = makeAnim('draw', 1.0, 'once');   // 24fps 量化：末帧 0.9 会落到 0.9167，长度必须盖过它
  keys(dr, 'move', 'position', [[0, [0, -2.20, 0.90]], [0.35, [0, -0.35, 0.12]], [0.55, [0, 0.06, -0.04]], [0.9, [0, 0, 0]]]);
  keys(dr, 'move', 'rotation', [[0, [-14.0, 3.0, 4.0]], [0.35, [-3.0, 1.0, 1.0]], [0.55, [1.2, -0.4, 0]], [0.9, [0, 0, 0]]]);
  keys(dr, 'body', 'rotation', [[0, [2.4, 0, 0]], [0.5, [-0.6, 0, 0]], [0.9, [0, 0, 0]]]);
  keys(dr, 'bolt', 'position', [[0, [0, 0, 0.55]], [0.45, [0, 0, 0.60]], [0.62, [0, 0, 0]], [0.9, [0, 0, 0]]]);
  rest(dr, 0, ['cover', 'magazine', 'trigger']);
  K(dr, 'casing', 'scale', 0, [0, 0, 0]); K(dr, 'clip_in', 'scale', 0, [0, 0, 0]);

  /* ================================================================
   * 3. shoot —— 单发后坐（once, 0.6 s）半自动：导气杆自动循环一次
   * ================================================================ */
  var sh = makeAnim('shoot', 0.6, 'once');
  keys(sh, 'move', 'rotation', [[0, [0, 0, 0]], [0.05, [2.60, 0.30, 0]], [0.12, [1.90, -0.20, 0]],
                                [0.22, [0.70, 0.10, 0]], [0.35, [-0.25, 0, 0]], [0.5, [0, 0, 0]], [0.6, [0, 0, 0]]]);
  keys(sh, 'move', 'position', [[0, [0, 0, 0]], [0.05, [0, 0.28, 0.62]], [0.12, [0, 0.24, 0.44]],
                                [0.22, [0, 0.12, 0.20]], [0.35, [0, -0.04, -0.06]], [0.5, [0, 0, 0]], [0.6, [0, 0, 0]]]);
  keys(sh, 'body', 'rotation', [[0, [0, 0, 0]], [0.05, [-1.10, 0, 0]], [0.40, [0, 0, 0]], [0.6, [0, 0, 0]]]);
  /* 半自动循环：枪机走全行程 1.10u（旧版只有 0.55u = 半个行程，越不过漏夹末弹底缘）*/
  keys(sh, 'bolt', 'position', [[0, [0, 0, 0]], [0.05, [0, 0, 0.92]], [0.075, [0, 0, 1.10]],
                                [0.14, [0, 0, 0.22]], [0.20, [0, 0, 0]], [0.6, [0, 0, 0]]]);
  /* 抛壳：弹壳在 +X 抛壳窗内，翻着跟头向 +X 上飞出去，0.45s 后收回（scale 0）*/
  keys(sh, 'casing', 'position', [[0, [0, 0, 0]], [0.075, [0, 0.04, 0.02]], [0.12, [0.35, 0.55, 0.10]],
                                  [0.20, [0.95, 1.55, 0.50]], [0.35, [1.90, 2.60, 1.30]], [0.45, [2.60, 3.40, 1.90]]]);
  keys(sh, 'casing', 'rotation', [[0, [0, 0, 0]], [0.12, [-25, 0, -40]], [0.20, [-70, 0, -160]],
                                  [0.35, [-140, 0, -320]], [0.45, [-190, 0, -430]]]);
  K(sh, 'casing', 'scale', 0, [0, 0, 0]); K(sh, 'casing', 'scale', 0.075, [1, 1, 1]); K(sh, 'casing', 'scale', 0.45, [0, 0, 0]);
  K(sh, 'clip_in', 'scale', 0, [0, 0, 0]); K(sh, 'clip_in', 'scale', 0.06, [1, 1, 1]);
  rest(sh, 0, ['cover', 'magazine', 'trigger']);

  /* ================================================================
   * 4. bolt —— 拉栓（手动拉导气杆，once, 1.1 s）
   *    真机行程 ~6.6cm = 1.06u，取 1.10u（纯平移，沿 Z 后退）
   * ================================================================ */
  var bo = makeAnim('bolt', 1.1, 'once');
  keys(bo, 'bolt', 'position', [[0, [0, 0, 0]], [0.18, [0, 0, 0.30]], [0.42, [0, 0, 1.10]], [0.62, [0, 0, 1.10]],
                                [0.80, [0, 0, 0.06]], [0.90, [0, 0, 0]], [1.1, [0, 0, 0]]]);
  keys(bo, 'move', 'rotation', [[0, [0, 0, 0]], [0.40, [-1.40, 0.50, 0]], [0.85, [0.30, 0, 0]], [1.1, [0, 0, 0]]]);
  keys(bo, 'move', 'position', [[0, [0, 0, 0]], [0.40, [0.10, -0.06, 0.16]], [0.90, [0, 0, 0]], [1.1, [0, 0, 0]]]);
  keys(bo, 'body', 'rotation', [[0, [0, 0, 0]], [0.42, [0.80, 0, 0]], [0.90, [0, 0, 0]], [1.1, [0, 0, 0]]]);
  /* 抽壳：枪机后退到 0.42 时弹壳脱出抛壳窗 */
  K(bo, 'casing', 'scale', 0, [0, 0, 0]); K(bo, 'casing', 'scale', 0.42, [1, 1, 1]);
  keys(bo, 'casing', 'position', [[0.42, [0, 0, 0]], [0.50, [0.42, 0.60, 0.14]], [0.62, [1.10, 1.70, 0.55]],
                                  [0.80, [2.10, 2.90, 1.40]], [0.95, [2.90, 3.70, 2.10]]]);
  keys(bo, 'casing', 'rotation', [[0.42, [0, 0, 0]], [0.62, [-90, 0, -180]], [0.80, [-200, 0, -400]], [0.95, [-280, 0, -540]]]);
  K(bo, 'casing', 'scale', 0.95, [0, 0, 0]);
  rest(bo, 0, ['cover', 'magazine', 'trigger']);
  K(bo, 'clip_in', 'scale', 0, [0, 0, 0]); K(bo, 'clip_in', 'scale', 0.42, [1, 1, 1]);

  /* ================================================================
   * 5. reload_empty —— 空仓换弹（once, 1.1 s）★手册 §3.2 四步★
   *    0.00-0.22 拉导气杆手柄到底（0.11 顿一下=解锁）
   *    0.19-0.33 漏夹盖平行抬起（纯平移）
   *    0.31-0.62 空漏夹向上弹飞（"ping"）
   *    0.58-0.78 新漏夹压入，0.80 回弹卡住
   *    0.80-0.94 盖子合上
   *    0.80-1.02 **漏夹卡住自动释放枪机** → 枪机自由前冲（停在 0.08 未完全闭锁）
   *    1.08      手掌根拍拉机柄，补到位闭锁
   * ================================================================ */
  var re = makeAnim('reload_empty', 1.1, 'once');
  /* 枪机：起手拉到底 → 被挂住 → 漏夹卡住后自动前冲 → 拍到位。
     注意：本模型无法保持"空仓挂机"状态（idle 里枪机是闭合的），所以起手必须补这一次拉柄，
     否则枪机在 t=0 会瞬移 1.10u；手册 §3.2 第一步也正是这个动作。 */
  keys(re, 'bolt', 'position', [[0, [0, 0, 0]], [0.11, [0, 0, 0.10]], [0.22, [0, 0, 1.10]], [0.80, [0, 0, 1.10]],
                                [0.88, [0, 0, 0.82]], [0.94, [0, 0, 0.44]], [0.99, [0, 0, 0.16]],
                                [1.03, [0, 0, 0.08]], [1.08, [0, 0, 0]], [1.1, [0, 0, 0]]]);
  /* 漏夹盖：纯平移 +Y 抬起 0.55u */
  keys(re, 'cover', 'position', [[0, [0, 0, 0]], [0.19, [0, 0, 0]], [0.33, [0, 0.55, 0]],
                                 [0.80, [0, 0.55, 0]], [0.94, [0, 0, 0]], [1.1, [0, 0, 0]]]);
  /* 漏夹：旧的弹飞 → 全新的自上而下压入。
     用户明确要求：装填是"平移"（平移进出），不得带翻转 —— 因此 rotation 全为 0，
     位移 x 与 z 也全为 0（只走竖直 Y）：z 非 0 时观感是漏夹沿枪身横滑，
     2026-09-30 用户截图指出该件应只走绿色轴。出货件早已是纯竖直，这里把
     art 与生成器补齐（历史上只改了出货 JSON，生成器漏改，重导出会把毛病带回来）。 */
  K(re, 'clip_in', 'scale', 0, [1, 1, 1]);
  keys(re, 'clip_in', 'position', [[0, [0, 0, 0]], [0.31, [0, 0, 0]], [0.48, [0, 0.50, 0]],
                                   [0.72, [0, 2.40, 0]], [0.92, [0, 3.80, 0]]]);
  keys(re, 'clip_in', 'rotation', [[0, [0, 0, 0]], [0.92, [0, 0, 0]]]);
  K(re, 'clip_in', 'scale', 1.0, [0, 0, 0]);           /* 旧的消失（第 24 帧） */
  K(re, 'clip_in', 'scale', 25 / 24, [1, 1, 1]);       /* 新的从上方出现（第 25 帧，必须与上一键不同帧） */
  keys(re, 'clip_in', 'position', [[0.58, [0, 2.50, 0]], [0.74, [0, 1.05, 0]], [0.86, [0, 0, 0]],
                                   [0.90, [0, 0.05, 0]], [0.96, [0, 0, 0]], [1.1, [0, 0, 0]]]);
  keys(re, 'move', 'rotation', [[0, [0, 0, 0]], [0.22, [-2.30, 0.65, 0]], [0.65, [-1.15, 0.35, 0]],
                                [0.98, [0.85, 0, 0]], [1.06, [-0.28, 0, 0]], [1.1, [0, 0, 0]]]);
  keys(re, 'move', 'position', [[0, [0, 0, 0]], [0.22, [0.08, -0.12, 0.12]], [0.65, [0, -0.08, 0.08]],
                                [0.92, [0, 0.08, -0.07]], [1.02, [0, 0, 0]], [1.1, [0, 0, 0]]]);
  keys(re, 'body', 'rotation', [[0, [0, 0, 0]], [0.35, [0.75, 0, 0]], [0.85, [-0.95, 0, 0]],
                                [1.00, [0.50, 0, 0]], [1.1, [0, 0, 0]]]);
  rest(re, 0, ['magazine', 'trigger']);
  K(re, 'casing', 'scale', 0, [0, 0, 0]);

  /* ================================================================
   * 6. reload_tactical —— 未空仓换弹（once, 2.6 s）★手册 §3.2 同样顺序，只是更快★
   *    未空仓时枪机是闭锁的 ⇒ 井口被枪机挡死，必须先拉到底才能卸/装漏夹。
   *    （旧版是"先插漏夹、再人工拉栓闭锁"，两步真机都做不到，已改。）
   *    0.00-0.26 拉导气杆到底 → 0.24-0.38 盖抬起 → 0.38-0.62 旧漏夹弹飞
   *    → 0.70-0.98 新漏夹压入卡住 → 1.00-1.14 盖合上
   *    → 0.98-1.24 漏夹卡住自动释放枪机（自由前冲）→ 1.32 拍拉机柄补到位
   * ================================================================ */
  var rt = makeAnim('reload_tactical', 2.6, 'once');
  keys(rt, 'bolt', 'position', [[0, [0, 0, 0]], [0.08, [0, 0, 0.10]], [0.26, [0, 0, 1.10]], [0.98, [0, 0, 1.10]],
                                [1.06, [0, 0, 0.82]], [1.13, [0, 0, 0.46]], [1.19, [0, 0, 0.18]],
                                [1.24, [0, 0, 0.06]], [1.32, [0, 0, 0]], [2.6, [0, 0, 0]]]);
  keys(rt, 'cover', 'position', [[0, [0, 0, 0]], [0.24, [0, 0, 0]], [0.38, [0, 0.55, 0]],
                                 [1.00, [0, 0.55, 0]], [1.14, [0, 0, 0]], [2.6, [0, 0, 0]]]);
  K(rt, 'clip_in', 'scale', 0, [1, 1, 1]);
  keys(rt, 'clip_in', 'position', [[0, [0, 0, 0]], [0.38, [0, 0, 0]], [0.50, [0, 0.50, 0.26]],
                                   [0.62, [0, 2.40, 1.15]]]);
  keys(rt, 'clip_in', 'rotation', [[0, [0, 0, 0]], [0.62, [0, 0, 0]]]);
  K(rt, 'clip_in', 'scale', 0.66, [0, 0, 0]);
  K(rt, 'clip_in', 'scale', 0.70, [1, 1, 1]);
  keys(rt, 'clip_in', 'position', [[0.70, [0, 2.20, 0.26]], [0.86, [0, 0.90, 0.10]], [0.98, [0, 0, 0]],
                                   [1.03, [0, 0.05, 0]], [1.10, [0, 0, 0]], [2.6, [0, 0, 0]]]);
  keys(rt, 'clip_in', 'rotation', [[0.70, [0, 0, 0]], [1.10, [0, 0, 0]], [2.6, [0, 0, 0]]]);
  keys(rt, 'move', 'rotation', [[0, [0, 0, 0]], [0.28, [-2.00, 0.55, 0]], [1.05, [-1.10, 0.28, 0]],
                                [1.30, [0.70, 0, 0]], [2.6, [0, 0, 0]]]);
  keys(rt, 'move', 'position', [[0, [0, 0, 0]], [0.28, [0.06, -0.09, 0.09]], [1.10, [0, -0.05, 0.05]],
                                [1.34, [0, 0.05, -0.06]], [2.6, [0, 0, 0]]]);
  keys(rt, 'body', 'rotation', [[0, [0, 0, 0]], [0.40, [0.65, 0, 0]], [1.05, [-0.85, 0, 0]],
                                [1.36, [0.40, 0, 0]], [2.6, [0, 0, 0]]]);
  rest(rt, 0, ['magazine', 'trigger']);
  K(rt, 'casing', 'scale', 0, [0, 0, 0]);

  /* ---------- dump raw keyframes for the record ---------- */
  var dump = { name: 'm1_garand', anims: [] };
  Animation.all.forEach(function (a) {
    var bones = {};
    Object.keys(a.animators || {}).forEach(function (uuid) {
      var an = a.animators[uuid];
      /* animator.group 不一定可用（本工程实测为 undefined），退回按 uuid 在 Group.all 里找骨名 */
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
  /* 顺带写盘：供 tools/m1_anim_export.py 转成 GeckoLib animation.json（与 AWM 同套路）*/
  try { if (typeof window !== 'undefined') window.__m1_bb_dump = dump; } catch (e) {}
  try {
    var fs = require('fs');
    fs.writeFileSync(DUMP, JSON.stringify(dump, null, 1));
    out.steps.push('dumped ' + DUMP);
  } catch (e) { out.warnings.push('dump: ' + e.message); }
  /* 注：本脚本是被间接 eval 执行的（全局作用域），拿不到调用方的 require；
     所以 dump 同时挂在 window.__m1_bb_dump 上，由 MCP 包装器落盘（见 README「生成链路」）。 */
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
