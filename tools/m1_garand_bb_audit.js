/* M1 Garand —— 数值自检（Blockbench 内跑，输出 JSON）
 * 对应 美术规范.md 七·自检项：锚点 / pivot 邻近度 / 抛壳点在 +X / 骨骼旋转为零 / 方块与骨骼预算
 */
(function () {
  var out = { fails: [], warns: [], info: {} };
  var LIM = 4.0;                       // 规范 六.2：pivot 到自身几何最近距离 ≤ 4u

  function bounds(list) {
    var b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
    list.forEach(function (c) {
      var v = [];
      try { v = c.getGlobalVertexPositions ? c.getGlobalVertexPositions() : []; } catch (e) { v = []; }
      if (!v.length) { v = [[c.from[0], c.from[1], c.from[2]], [c.to[0], c.to[1], c.to[2]]]; }
      v.forEach(function (p) {
        for (var k = 0; k < 3; k++) {
          if (p[k] < b[k]) b[k] = p[k];
          if (p[k] > b[k + 3]) b[k + 3] = p[k];
        }
      });
    });
    return b;
  }
  function dist2Box(pt, b) {
    if (!isFinite(b[0])) return null;
    var d = 0;
    for (var k = 0; k < 3; k++) {
      var lo = b[k], hi = b[k + 3], v = pt[k];
      var e = (v < lo) ? (lo - v) : ((v > hi) ? (v - hi) : 0);
      d += e * e;
    }
    return Math.sqrt(d);
  }

  /* 1. 骨骼旋转必须为零（规范 一·铁律） */
  Group.all.forEach(function (g) {
    var r = g.rotation || [0, 0, 0];
    if (Math.abs(r[0]) + Math.abs(r[1]) + Math.abs(r[2]) > 1e-6) {
      out.fails.push('骨骼 ' + g.name + ' 带旋转 ' + JSON.stringify(r) + '（规范：一根都不许有）');
    }
  });

  /* 2. 每根骨的方块数 + pivot 邻近度 */
  var per = {};
  Group.all.forEach(function (g) {
    var cubes = g.children.filter(function (c) { return c instanceof Cube; });
    var b = bounds(cubes);
    var d = dist2Box(g.origin, b);
    per[g.name] = { cubes: cubes.length, pivot: g.origin.slice(),
                    dist: (d === null ? null : +d.toFixed(3)),
                    bbox: isFinite(b[0]) ? b.map(function (x) { return +x.toFixed(2); }) : null };
    if (d !== null && d > LIM) {
      out.fails.push('骨骼 ' + g.name + ' pivot 离自身几何 ' + d.toFixed(2) + 'u > ' + LIM + 'u');
    }
  });
  out.info.groups = per;

  /* 3. 全局包围盒 → 全长 / 锚点 */
  var all = bounds(Project.elements);
  out.info.bbox = all.map(function (x) { return +x.toFixed(2); });
  out.info.length_u = +(all[5] - all[2]).toFixed(2);
  out.info.height_u = +(all[4] - all[1]).toFixed(2);
  out.info.width_u  = +(all[3] - all[0]).toFixed(2);
  out.info.length_blocks = +((all[5] - all[2]) / 16).toFixed(3);
  if (all[2] < -13.65) out.fails.push('有几何越过枪口平面 -13.60，最前端 Z=' + all[2].toFixed(2));
  if (TEXCHK()) out.fails.push('贴图画布不是 512x512，导出 PNG 会是空图');
  function TEXCHK() {
    try { return Project.textures[0].canvas.width !== 512 || Project.textures[0].canvas.height !== 512; }
    catch (e) { return true; }
  }
  if (out.info.length_u < 15 || out.info.length_u > 20) {
    out.warns.push('全长 ' + out.info.length_u + 'u，真机 1103mm=17.6u，超出 ±2u');
  }

  /* 4. 锚点：枪口 / 瞄准线 / 抛壳点 */
  var muzzle = bounds(Project.elements.filter(function (c) { return c.name.indexOf('bbl_') === 0; }));
  out.info.muzzle = { y: +((muzzle[1] + muzzle[4]) / 2).toFixed(2), z: +muzzle[2].toFixed(2) };
  if (Math.abs(muzzle[2] + 13.60) > 0.10) out.fails.push('枪口 Z 应为 -13.60，实测 ' + muzzle[2].toFixed(2));

  var front = Group.all.find(function (g) { return g.name === 'barrel'; });
  var blade = Project.elements.find(function (c) { return c.name === 'fs_blade'; });
  if (blade) {
    var tb = bounds([blade]);
    out.info.front_sight_top = +tb[4].toFixed(2);
    if (Math.abs(tb[4] - 2.80) > 0.05) out.fails.push('前准星顶 ' + tb[4].toFixed(2) + ' ≠ 瞄准线 2.80');
  } else out.fails.push('找不到前准星 fs_blade');
  var ap = Project.elements.find(function (c) { return c.name === 'rs_ap'; });
  if (ap) {
    var ab = bounds([ap]);
    var cy = (ab[1] + ab[4]) / 2;
    out.info.rear_aperture_y = +cy.toFixed(2);
    out.info.rear_aperture_id = +(ab[4] - ab[1]).toFixed(2);
    if (Math.abs(cy - 2.80) > 0.05) out.fails.push('照门孔心 ' + cy.toFixed(2) + ' ≠ 瞄准线 2.80');
  } else out.fails.push('找不到照门 rs_ap');

  /* 5. 抛壳几何必须在 +X 抛壳窗内（规范 六.1 / 七·E） */
  var cas = Group.all.find(function (g) { return g.name === 'casing'; });
  if (cas) {
    var cb = bounds(cas.children.filter(function (c) { return c instanceof Cube; }));
    out.info.casing_bbox = cb.map(function (x) { return +x.toFixed(2); });
    if (cb[0] <= 0) out.fails.push('抛壳几何必须在 +X 侧，实测最小 X=' + cb[0].toFixed(2));
  } else out.fails.push('找不到 casing 骨');

  /* 5b. 装配合位：零件必须长在该在的地方（用户报的"扳机不在护圈内"就属这一类） */
  function inside(name, lo, hi, label) {
    var b = per[name] && per[name].bbox;
    if (!b) { out.fails.push('找不到骨骼 ' + name); return; }
    for (var k = 0; k < 3; k++) {
      var ax = 'XYZ'.charAt(k);
      if (b[k] < lo[k] - 1e-6) out.fails.push(label + '：' + ax + ' 最小 ' + b[k].toFixed(2) + ' < 下限 ' + lo[k]);
      if (b[k + 3] > hi[k] + 1e-6) out.fails.push(label + '：' + ax + ' 最大 ' + b[k + 3].toFixed(2) + ' > 上限 ' + hi[k]);
    }
  }
  /* 扳机必须落在护圈开口内：护圈前立柱 Z(806)–Z(826)，底横梁 Y(−91)–Y(−83) */
  inside('trigger', [-0.08, 0.74, -0.75], [0.08, 1.86, 0.20], '扳机越出护圈内腔');
  var tb = per['trigger'] && per['trigger'].bbox;
  if (tb && tb[1] >= 0.85) out.fails.push('扳机没伸进护圈开口（最低 Y=' + tb[1].toFixed(2) + ' ≥ 0.85）');
  /* 全局最低点 = 托底板下缘（真机 −176.5mm = −0.52u），低于它就是零件挂空 */
  if (all[1] < -0.54) out.fails.push('有几何挂在枪身下方，全局最低 Y=' + all[1].toFixed(2) + ' < -0.54');
  /* 机匣段（Z ≤ −0.30，枪口到托颈）不许有零件低于护圈底：挂空零件会在这条上现形。
     托颈之后托底本来就下沉到 −0.52（真机 −176.5mm），不在此列。 */
  Project.elements.forEach(function (cb) {
    if (cb.from && cb.from[2] <= -0.30 && cb.from[1] < -0.10)
      out.fails.push('机匣段有零件挂空：' + cb.name + ' 最低 Y=' + cb.from[1].toFixed(2));
  });
  /* 漏夹必须在弹夹井内（井 601–700mm = Z −3.98…−2.40，漏夹 85mm）；漏夹盖压在机匣顶面（+16mm）
     井位真机标定：前壁 = 闭锁面 610mm（枪管 24"），后壁贴后照门座/拉机柄前沿 700mm。 */
  inside('clip_in', [-0.20, 1.85, -3.99], [0.20, 2.58, -2.40], '漏夹越出弹夹井');
  inside('cover', [-0.32, 2.52, -4.03], [0.32, 2.72, -2.34], '漏夹盖没压在机匣顶面');
  /* 弹壳静止位（= 抛出点）必须在抛壳窗内（窗 700–795mm = Z −2.40…−0.88） */
  inside('casing', [0.19, 2.50, -2.42], [0.41, 2.80, -0.86], '弹壳不在抛壳窗内');
  /* 导气杆必须整根在右侧（逐个方块查，不能查骨包围盒：bolt 骨里还有居中的枪机体） */
  var opc = Project.elements.filter(function (c) { return /^oprod/.test(c.name); });
  if (opc.length) {
    var oc = bounds(opc);
    out.info.oprod_x = [+oc[0].toFixed(2), +oc[3].toFixed(2)];
    if (oc[0] < 0.26) out.fails.push('导气杆压过枪身中线，最小 X=' + oc[0].toFixed(2));
  }
  /* 托必须与机匣接合，不许留缝 */
  var sb = per['stock'] && per['stock'].bbox, bb2 = per['body'] && per['body'].bbox;
  if (sb && bb2 && sb[2] > bb2[5] + 0.02) out.fails.push('托与机匣留缝 ' + (sb[2] - bb2[5]).toFixed(2) + 'u');

  /* 6. 预算（规范 二·方块预算 ≤600 / ≤40 骨） */
  out.info.cubes = Project.elements.length;
  out.info.groups_n = Project.groups.length;
  if (Project.elements.length > 600) out.fails.push('方块 ' + Project.elements.length + ' 超预算 600');
  if (Project.groups.length > 40) out.fails.push('骨骼 ' + Project.groups.length + ' 超预算 40');

  /* 7. 漏夹 / 漏夹盖 / 枪机 的 pivot（硬编码清单要同步 Java） */
  ['root','move','bolt','cover','clip_in','casing','magazine','trigger','barrel','stock'].forEach(function (n) {
    var g = Group.all.find(function (x) { return x.name === n; });
    if (g) out.info['pivot_' + n] = g.origin.map(function (x) { return +x.toFixed(2); });
  });

  /* 8. 贴图导出（外层写盘：本作用域没有 require） */
  try {
    globalThis.__m1_png = Project.textures[0].canvas.toDataURL('image/png', 1);
    out.info.png_bytes = Math.round(globalThis.__m1_png.length * 0.75);
  } catch (e) { out.warns.push('png:' + e.message); }

  out.ok = out.fails.length === 0;
  return out;
})()
