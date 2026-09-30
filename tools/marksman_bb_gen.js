/* 骸骨射手 MarksmanSkeleton —— Blockbench 几何 + 贴图生成器（在 Blockbench 里跑，末尾 return out）
 *
 * 规格：art/marksman/DESIGN.md。铁律：16u = 1 Block、1u = 1px、面朝 -Z、+X 为模型右侧、
 * 脚底 Y = 0、颅顶 Y = 32、骨头 rest 旋转全零、禁止任何 scale 通道、贴图 128×128 逐面 UV。
 *
 * 与项目既有 mob 生成器保持一致的两点（tools/_scratch_geo_schema.py 实测）：
 *   1. 体块一律轴对齐，本体块不带 rotation —— 骨弓的弧用 5 段分片拼（曲面用图元，不用自转）；
 *   2. 逐面 UV 是 {north:{uv,uv_size},...}，所以这里按面打包、按面画。
 *
 * 执行方式（不要直接贴给 risky_eval，注释会炸）：
 *   python tools/marksman_bb_gen.py
 */
(function () {

  var out = { step: [] };

  /* ------------------------------------------------------------------ 0. 清场（可反复跑） */
  try {
    Project.elements.slice().forEach(function (e) { if (e.remove) { e.remove(); } });
  } catch (e0) {}
  try {
    Project.groups.slice().forEach(function (g) { if (g.remove) { g.remove(); } });
  } catch (e1) {}
  Project.elements.length = 0;
  Project.groups.length = 0;

  /* ------------------------------------------------------------------ 0b. 贴图：128×128 空画布
     注意：不要用 Texture.fromPath —— 它是异步的，画布会停在 Blockbench 默认的 16×16，
     于是整张图被画在 16×16 上（m1_garand_bb_gen.js / mosin_nagant_bb_gen.js 就是这么踩过来的）。*/
  try {
    Project.textures.slice().forEach(function (t) { if (t.remove) t.remove(); });
  } catch (e2) {}
  Project.textures.length = 0;
  var TEX = new Texture({ name: 'marksman_skeleton', width: 128, height: 128, internal: true });
  TEX.add(false);
  TEX = Project.textures[Project.textures.length - 1];
  try {
    if (TEX.canvas.width !== 128 || TEX.canvas.height !== 128) {
      TEX.canvas.width = 128;
      TEX.canvas.height = 128;
    }
  } catch (e2b) {}
  TEX.width = 128;
  TEX.height = 128;
  Project.texture_width = 128;
  Project.texture_height = 128;
  Project.box_uv = false;
  Project.name = 'marksman_skeleton';
  try { Project.geometry_name = 'marksman_skeleton'; } catch (e3) {}
  try { Project.visible_box = [2.5, 3.0, 1.05]; } catch (e4) {}
  out.tex = {
    name: TEX.name,
    w: TEX.width,
    h: TEX.height,
    canvas: TEX.canvas ? TEX.canvas.width + 'x' + TEX.canvas.height : 'no-canvas'
  };

  /* ------------------------------------------------------------------ 1. 调色板 */
  var P = {
    bone: '#d8d2bd', boneDark: '#a89f86', boneShade: '#c4bda6', boneDeep: '#8d846d',
    socket: '#22221c', eye: '#d6c46a',
    cloth: '#4a4438', clothDark: '#3a352c', clothEdge: '#2b271f',
    leather: '#5b4632', leatherDark: '#463423', stitch: '#8a7355',
    bow: '#cfc7ae', bowGrip: '#6b5a44', string: '#8d8878',
    under: '#6d6455', fletch: '#b5533f'
  };

  /* ------------------------------------------------------------------ 2. 骨架 */
  var G = {};
  function grp(name, origin, parent) {
    var g = new Group({ name: name, origin: origin }).init();
    if (parent) {
      g.addTo(G[parent]);
    }
    G[name] = g;
    return g;
  }
  function mirP(p) { return [-p[0], p[1], p[2]]; }

  grp('root', [0, 0, 0], null);
  grp('move', [0, 0, 0], 'root');
  grp('hip', [0, 13.5, 0], 'move');
  grp('spine', [0, 17.0, 0], 'move');
  grp('chest', [0, 20.0, 0], 'spine');

  grp('leg_r', [2.1, 13.5, 0], 'hip');
  grp('shin_r', [2.1, 7.5, 0], 'leg_r');
  grp('foot_r', [2.1, 1.5, 0], 'shin_r');
  grp('leg_l', mirP([2.1, 13.5, 0]), 'hip');
  grp('shin_l', mirP([2.1, 7.5, 0]), 'leg_l');
  grp('foot_l', mirP([2.1, 1.5, 0]), 'shin_l');

  grp('neck', [0, 24.5, 0], 'chest');
  grp('head', [0, 24.0, 0], 'neck');
  grp('jaw', [0, 27.0, -2.0], 'head');

  grp('cape_a', [0, 23.0, 2.6], 'chest');
  grp('cape_b', [0, 17.0, 3.2], 'cape_a');
  grp('cape_c', [0, 11.0, 3.6], 'cape_b');
  grp('quiver', [3.0, 23.0, 3.0], 'chest');

  grp('shoulder_r', [4.6, 23.5, 0], 'chest');
  grp('arm_r', [4.6, 23.5, 0], 'shoulder_r');
  grp('forearm_r', [4.6, 18.0, 0], 'arm_r');
  grp('hand_r', [4.6, 12.5, 0], 'forearm_r');
  grp('shoulder_l', mirP([4.6, 23.5, 0]), 'chest');
  grp('arm_l', mirP([4.6, 23.5, 0]), 'shoulder_l');
  grp('forearm_l', mirP([4.6, 18.0, 0]), 'arm_l');
  grp('hand_l', mirP([4.6, 12.5, 0]), 'forearm_l');
  grp('bow', mirP([6.3, 11.0, -3.0]), 'hand_l');
  out.bones = Project.groups.length;
  out.groups_tree = Project.groups.map(function (g) {
    return g.name + '<' + (g.parent && g.parent.name ? g.parent.name : 'root') + '>';
  });

  /* ------------------------------------------------------------------ 3. 体块表（u） */
  var REC = [];
  function box(bone, name, f, t, mat, hi) {
    REC.push({
      bone: bone, name: name, f: f, t: t, mat: mat, hi: hi || [],
      org: [(f[0] + t[0]) / 2, (f[1] + t[1]) / 2, (f[2] + t[2]) / 2]
    });
  }
  function mirB(f, t) { return [[-t[0], f[1], f[2]], [-f[0], t[1], t[2]]]; }
  function boxPair(boneR, boneL, name, f, t, mat, hi) {
    box(boneR, name + '_r', f, t, mat, hi);
    var m = mirB(f, t);
    box(boneL, name + '_l', m[0], m[1], mat, hi);
  }

  /* 腿：大腿 / 小腿 / 骨足（前伸） */
  boxPair('leg_r', 'leg_l', 'thigh', [0.6, 7.5, -1.5], [3.6, 13.5, 1.5], 'bone');
  boxPair('shin_r', 'shin_l', 'shin', [0.8, 1.5, -1.2], [3.4, 7.5, 1.2], 'bone');
  boxPair('foot_r', 'foot_l', 'foot', [0.8, 0.0, -3.0], [3.4, 1.5, 1.2], 'bone');

  /* 躯干：骨盆 / 腰椎 / 胸腔 / 两层肋 */
  box('hip', 'pelvis', [-3.5, 13.5, -2.0], [3.5, 17.0, 2.0], 'bone');
  box('spine', 'lumbar', [-3.5, 17.0, -1.8], [3.5, 20.0, 1.8], 'bone');
  box('chest', 'ribcage', [-4.5, 20.0, -2.2], [4.5, 25.0, 2.2], 'rib');
  boxPair('chest', 'chest', 'rib_layer', [4.2, 20.5, -2.0], [4.7, 24.5, 2.0], 'rib');

  /* 头颅 / 下颚 */
  box('neck', 'neck', [-1.0, 24.5, -1.0], [1.0, 26.5, 1.0], 'under');
  box('head', 'skull', [-4.0, 24.0, -4.0], [4.0, 32.0, 4.0], 'bone', ['north', 'up']);
  box('jaw', 'jaw', [-3.2, 24.5, -4.6], [3.2, 27.0, -2.0], 'bone', ['north']);

  /* 斗篷三段（1u 厚薄板，逐段收窄） */
  box('cape_a', 'cape_a', [-4.6, 17.5, 2.2], [4.6, 23.5, 3.2], 'cloth');
  box('cape_b', 'cape_b', [-4.0, 11.5, 2.8], [4.0, 17.7, 3.8], 'cloth');
  box('cape_c', 'cape_c', [-3.2, 5.5, 3.2], [3.2, 11.7, 4.2], 'cloth');

  /* 箭袋 + 三支箭 */
  box('quiver', 'quiver_box', [1.4, 16.0, 3.0], [4.6, 23.0, 6.0], 'leather');
  box('quiver', 'arrow_1', [1.9, 23.0, 3.4], [2.4, 27.2, 3.9], 'bone');
  box('quiver', 'arrow_2', [3.1, 23.2, 4.2], [3.6, 27.4, 4.7], 'bone');
  box('quiver', 'arrow_3', [2.5, 23.1, 5.0], [3.0, 27.3, 5.5], 'bone');

  /* 双臂（上臂 / 前臂 / 手） */
  boxPair('arm_r', 'arm_l', 'upper_arm', [4.6, 18.0, -1.25], [7.1, 23.5, 1.25], 'bone');
  boxPair('forearm_r', 'forearm_l', 'forearm', [4.7, 12.5, -1.1], [7.0, 18.0, 1.1], 'bone');
  boxPair('hand_r', 'hand_l', 'hand', [4.8, 10.0, -1.2], [6.9, 12.5, 1.2], 'bone');

  /* 骨弓：握把 + 4 段分片弓臂（曲面用图元）+ 弦；弧面朝 -Z（射向），弦在 +Z 侧靠近身体 */
  box('bow', 'bow_grip', [-6.9, 7.5, -3.9], [-5.7, 14.5, -2.7], 'bowGrip');
  box('bow', 'bow_arm_1', [-6.8, 14.5, -4.0], [-5.8, 17.0, -3.2], 'bow');
  box('bow', 'bow_arm_2', [-6.7, 17.0, -3.8], [-5.9, 19.0, -2.6], 'bow');
  box('bow', 'bow_arm_3', [-6.8, 3.0, -4.0], [-5.8, 5.5, -3.2], 'bow');
  box('bow', 'bow_arm_4', [-6.7, 5.5, -3.8], [-5.9, 7.5, -2.6], 'bow');
  box('bow', 'bow_string', [-6.5, 5.0, -2.5], [-6.1, 17.0, -2.1], 'string');

  /* ------------------------------------------------------------------ 4. 实例化 */
  REC.forEach(function (r) {
    var c = new Cube({ name: r.name, from: r.f, to: r.t, origin: r.org, autouv: 0 });
    c.init();
    c.addTo(G[r.bone]);
    r.cube = c;
    r.size = [r.t[0] - r.f[0], r.t[1] - r.f[1], r.t[2] - r.f[2]];
  });
  out.cubes = REC.length;
  out.registered_elements = Project.elements.length;

  /* ------------------------------------------------------------------ 5. 逐面 UV：货架打包，密度自适应 */
  var DIM = { north: [0, 1], south: [0, 1], east: [2, 1], west: [2, 1], up: [0, 2], down: [0, 2] };
  var FACES = ['north', 'south', 'east', 'west', 'up', 'down'];
  var jobs = [];
  REC.forEach(function (r) {
    FACES.forEach(function (fn) {
      var d = DIM[fn];
      jobs.push({ rec: r, face: fn, w: r.size[d[0]], h: r.size[d[1]], hi: r.hi.indexOf(fn) >= 0 });
    });
  });

  function tryPack(D) {
    var items = jobs.map(function (j) {
      var d = j.hi ? Math.max(D, 3.0) : D;
      return { j: j, w: Math.max(1, Math.ceil(j.w * d)), h: Math.max(1, Math.ceil(j.h * d)) };
    });
    items.sort(function (a, b) { return (b.h - a.h) || (b.w - a.w); });
    var X = 0, Y = 0, rowH = 0, placed = [];
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      if (X + it.w > 128) { X = 0; Y += rowH + 1; rowH = 0; }
      if (Y + it.h > 128) { return null; }
      it.x = X; it.y = Y;
      X += it.w + 1;
      if (it.h > rowH) { rowH = it.h; }
      placed.push(it);
    }
    return { items: placed, used: Y + rowH };
  }

  var D = 0, PACK = null;
  for (var d = 2.0; d >= 0.75; d -= 0.05) {
    var p = tryPack(+d.toFixed(2));
    if (p) { D = +d.toFixed(2); PACK = p; break; }
  }
  if (!PACK) {
    return { error: 'atlas does not fit in 128x128 even at 0.75 px/u' };
  }
  PACK.items.forEach(function (it) {
    var f = it.j.rec.cube.faces[it.j.face];
    f.uv = [it.x, it.y, it.x + it.w, it.y + it.h];
    f.texture = TEX.uuid;
    it.j.rec.uv = it.j.rec.uv || {};
    it.j.rec.uv[it.j.face] = [it.x, it.y, it.w, it.h];
  });
  out.density = D;
  out.atlas_used_px = PACK.used;

  /* ------------------------------------------------------------------ 6. 画 128×128 贴图 */
  var ctx = TEX.ctx || TEX.canvas.getContext('2d');
  ctx.clearRect(0, 0, 128, 128);
  function fill(x, y, w, h, c) { ctx.fillStyle = c; ctx.fillRect(x, y, w, h); }
  function dot(x, y, c) { fill(x, y, 1, 1, c); }
  function h1(a, b) { var n = Math.sin(a * 12.9898 + b * 78.233) * 43758.5453; return n - Math.floor(n); }

  var BASE = {
    bone: P.bone, rib: P.boneShade, under: P.under, cloth: P.cloth,
    leather: P.leather, bow: P.bow, bowGrip: P.bowGrip, string: P.string
  };

  PACK.items.forEach(function (it) {
    var r = it.j.rec, fn = it.j.face, x = it.x, y = it.y, w = it.w, h = it.h;
    var base = BASE[r.mat] || P.bone;
    fill(x, y, w, h, base);

    /* 通用：骨材质撒骨纹斑点 + 上下缘压暗，读起来才像骨头而不是塑料 */
    if (r.mat === 'bone') {
      var n = Math.floor(w * h * 0.10);
      for (var i = 0; i < n; i++) {
        var hx = x + Math.floor(h1(x + i, y + fn.length) * w);
        var hy = y + Math.floor(h1(y + i * 2.7, x) * h);
        dot(hx, hy, h1(i, x + y) > 0.5 ? P.boneDark : P.boneShade);
      }
      fill(x, y, w, 1, P.boneShade);
      fill(x, y + h - 1, w, 1, P.boneDark);
    }
    if (r.mat === 'rib') {
      for (var k = 0; k < h; k += 3) { fill(x, y + k, w, 1, P.boneDark); }
      fill(x, y, 1, h, P.boneDeep);
      fill(x + w - 1, y, 1, h, P.boneDeep);
    }
    if (r.mat === 'cloth') {
      for (var c2 = 0; c2 < h; c2 += 2) { fill(x, y + c2, w, 1, P.clothDark); }
      for (var e = 0; e < w; e += 5) { fill(x + e, y, 1, h, P.clothEdge); }
    }
    if (r.mat === 'leather') {
      for (var s = 0; s < h; s += 3) { dot(x + 1, y + s, P.stitch); dot(x + w - 2, y + s, P.stitch); }
      fill(x, y, w, 1, P.leatherDark);
      fill(x, y + h - 1, w, 1, P.leatherDark);
    }
    if (r.mat === 'bowGrip') {
      for (var g = 0; g < h; g += 2) { fill(x, y + g, w, 1, P.leatherDark); }
    }
    if (r.mat === 'string') {
      fill(x, y, w, h, P.string);
      fill(x, y, w, 1, P.bow);
    }

    /* 面部：眼窝 + 鼻腔 + 齿列 + 裂缝（只有 front 面才画，别糊到后脑勺） */
    if (r.name === 'skull' && fn === 'north') {
      var ew = Math.max(3, Math.round(w * 0.22)), eh = Math.max(3, Math.round(h * 0.26));
      var e1x = x + Math.round(w * 0.16), e2x = x + Math.round(w * 0.62), ey = y + Math.round(h * 0.20);
      fill(e1x, ey, ew, eh, P.socket);
      fill(e2x, ey, ew, eh, P.socket);
      dot(e1x + 1, ey + eh - 2, P.eye); dot(e2x + ew - 2, ey + eh - 2, P.eye);
      var nx = x + Math.round(w * 0.5) - 1;
      fill(nx, ey + eh + 1, 2, Math.max(2, Math.round(h * 0.16)), P.socket);
      var ty = y + h - Math.max(3, Math.round(h * 0.22));
      for (var t = x + 1; t < x + w - 1; t += 2) { fill(t, ty, 1, y + h - ty, P.socket); }
      fill(x + Math.round(w * 0.35), y + 1, 1, Math.round(h * 0.18), P.boneDark);
      fill(x + Math.round(w * 0.72), y + Math.round(h * 0.55), 1, Math.round(h * 0.3), P.boneDark);
    }
    if (r.name === 'skull' && fn === 'up') {
      for (var u = 0; u < w; u += 4) { fill(x + u, y + 1, 1, h - 2, P.boneDark); }
      for (var u2 = 0; u2 < h; u2 += 5) { fill(x + 1, y + u2, w - 2, 1, P.boneDark); }
    }
    if (r.name === 'jaw' && fn === 'north') {
      for (var jt = x; jt < x + w; jt += 2) { fill(jt, y + 1, 1, Math.max(2, Math.round(h * 0.45)), P.socket); }
    }
    /* 胸腔正面：肋骨缝隙（横向暗带），背面留平 */
    if (r.name === 'ribcage' && (fn === 'north' || fn === 'south')) {
      for (var rb = 0; rb < h; rb += 4) { fill(x + 1, y + rb, w - 2, 2, P.boneDark); }
    }
    /* 箭袋口：三支箭的羽尾颜色，从背后一眼看出是箭袋 */
    if (r.name === 'quiver_box' && fn === 'up') {
      fill(x + 1, y + 1, Math.max(1, Math.round(w * 0.3)), 2, P.fletch);
      fill(x + Math.round(w * 0.55), y + 1, 2, 2, P.fletch);
    }
  });

  try { TEX.source = TEX.canvas.toDataURL('image/png', 1); } catch (e5) { out.texErr = String(e5); }
  try { if (TEX.updateSource) { TEX.updateSource(TEX.source); } } catch (e5b) { out.texUpdErr = String(e5b); }
  try { if (TEX.updateVersion) { TEX.updateVersion(); } } catch (e5c) {}
  try { out.png = TEX.canvas.toDataURL('image/png', 1); } catch (e6) { out.pngErr = String(e6); }

  /* ------------------------------------------------------------------ 7. 自检 + dump */
  var bb = [[1e9, 1e9, 1e9], [-1e9, -1e9, -1e9]];
  REC.forEach(function (r) {
    for (var a = 0; a < 3; a++) {
      bb[0][a] = Math.min(bb[0][a], r.f[a]);
      bb[1][a] = Math.max(bb[1][a], r.t[a]);
    }
  });
  var overlaps = 0, oob = 0;
  var rects = PACK.items.map(function (it) { return [it.x, it.y, it.w, it.h]; });
  rects.forEach(function (a, i) {
    if (a[0] < 0 || a[1] < 0 || a[0] + a[2] > 128 || a[1] + a[3] > 128) { oob++; }
    for (var j = i + 1; j < rects.length; j++) {
      var b = rects[j];
      if (a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3]) { overlaps++; }
    }
  });

  out.bbox = { min: bb[0].map(function (v) { return +v.toFixed(2); }), max: bb[1].map(function (v) { return +v.toFixed(2); }) };
  out.check = {
    faces_packed: PACK.items.length,
    elements_registered: Project.elements.length === REC.length,
    canvas_128: out.tex.canvas === '128x128',
    uv_overlaps: overlaps,
    uv_out_of_bounds: oob,
    bone_rest_rot_all_zero: Project.groups.every(function (g) {
      return !g.rotation || (g.rotation[0] === 0 && g.rotation[1] === 0 && g.rotation[2] === 0);
    }),
    foot_at_zero: Math.abs(bb[0][1]) < 1e-6,
    top_at_32: Math.abs(bb[1][1] - 32.0) < 1e-6,
    cube_rotations: REC.filter(function (r) { return r.cube.rotation && (r.cube.rotation[0] || r.cube.rotation[1] || r.cube.rotation[2]); }).length
  };

  out.model = {
    name: 'marksman_skeleton',
    texture: { w: 128, h: 128 },
    density: D,
    visible_bounds: { width: 2.5, height: 3.0, offset: [0, 1.05, 0] },
    bones: Project.groups.map(function (g) {
      return {
        name: g.name,
        pivot: [+g.origin[0], +g.origin[1], +g.origin[2]],
        parent: (g.parent && g.parent.name) ? g.parent.name : null
      };
    }),
    cubes: REC.map(function (r) {
      return { name: r.name, bone: r.bone, from: r.f, to: r.t, pivot: r.org, mat: r.mat, uv: r.uv };
    })
  };

  if (typeof Preview !== 'undefined' && Preview.all) {
    Preview.all.forEach(function (v) { if (v.canvas && v.canvas.render) { v.canvas.render(); } });
  }
  return out;
})()
