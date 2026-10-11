'use strict';
/* ============================================================================
 * RSC M1917 —— 通过 blockbench-mcp 下发建模（几何 + 逐面 UV 图集 + 导出）
 *
 * 用法: node tools/rsc_1917_build.js [--reset] [--no-export] [--eval]
 *   几何定义在 tools/rsc_1917_geo.js；本脚本负责 UV 打包 / 贴图绘制 / MCP 下发 / 导出。
 *   --reset  先清空当前 Blockbench 项目里的元素与骨骼（幂等重跑用）
 *   --eval   用 risky_eval 在进程内批量建方块（500+ 元素时逐颗 place_cube 会撞桥超时，推荐）
 *
 * 产出（与短管喷同一套口径，便于 check_rsc_1917_art.py 直接吃）:
 *   build/rsc_1917_tex.png       512x512 逐面 UV 图集
 *   build/rsc_1917.geo.json      GeckoLib 模型（Blockbench 导出，可回读核对）
 *   build/rsc_1917_build.json    本次下发 + 自检的完整回报
 *
 * 注意：本脚本**只下发 + 导出**，不写 assets/；落位与规范化由 rsc_1917_install.js 负责
 * （与短管喷 / S686 同一分工，谁也别抢谁的活）。
 * ========================================================================== */
const fs = require('fs');
const path = require('path');
const { Bb } = require('./bbmcp_lib.js');
const { encodePNG } = require('./png_write.js');
const geoMod = require('./rsc_1917_geo.js');

const ROOT = path.resolve(__dirname, '..');
const BUILD = path.join(ROOT, 'build');
const TEX_NAME = 'rsc_1917';
const TEX_SIZE = 512;
/* 规范要求 11~13 px/u（kar98k 的 128² 是历史例外）；从 13 往下试，装不下再降 */
const UV_MIN = 11;
const UV_MAX = 13;

const GAP_FIX = 0.003;   /* 相邻方块轻微重叠，消灭亚像素缝（同短管喷） */
const FACES = ['north', 'east', 'south', 'west', 'up', 'down'];

/* ---------------- 1. 逐面清单 + UV 装箱 ---------------- */
function faceList(cubes) {
  const out = [];
  for (const c of cubes) {
    for (const f of FACES) {
      let w, h;
      if (f === 'north' || f === 'south') { w = c.size[0]; h = c.size[1]; }
      else if (f === 'east' || f === 'west') { w = c.size[2]; h = c.size[1]; }
      else { w = c.size[0]; h = c.size[2]; }
      out.push({ c, f, w, h, mat: c.mat });
    }
  }
  return out;
}

function pack(faces, D) {
  const items = faces.map((o, i) => ({ i, w: Math.max(1, Math.round(o.w * D)), h: Math.max(1, Math.round(o.h * D)) }))
    .sort((a, b) => (b.h - a.h) || (b.w - a.w));
  let x = 1, y = 1, rowH = 0;
  const rects = new Array(faces.length);
  for (const e of items) {
    if (x + e.w + 1 > TEX_SIZE) { x = 1; y += rowH + 1; rowH = 0; }
    if (y + e.h + 1 > TEX_SIZE) return null;
    rects[e.i] = [x, y, x + e.w, y + e.h];
    x += e.w + 1;
    rowH = Math.max(rowH, e.h);
  }
  return { rects, used: y + rowH };
}

/* ---------------- 2. 画 512x512 图集 ----------------
 * 面与面之间**不压边**：相邻方块同材质同朝向时颜色必须完全一致，否则拼出黑缝
 * （短管喷踩过的坑，这里照抄它的结论）。立体感交给 MC 自己的逐面光照。 */
function paint(faces, MAT, SHADE, W, H) {
  const px = new Uint8Array(W * H * 4);
  const hash = (a, b) => { const n = Math.sin(a * 12.9898 + b * 78.233) * 43758.5453; return n - Math.floor(n); };
  faces.forEach((o, i) => {
    const base = MAT[o.mat] || [128, 128, 128];
    const s = SHADE[o.f] || 1;
    const r = o.rect;
    for (let y = r[1]; y < r[3]; y++) {
      for (let x = r[0]; x < r[2]; x++) {
        const grain = 0.93 + 0.14 * hash(x + i * 7, y - i * 3);
        const f = s * grain;
        const p = (y * W + x) * 4;
        px[p] = Math.min(255, Math.round(base[0] * f));
        px[p + 1] = Math.min(255, Math.round(base[1] * f));
        px[p + 2] = Math.min(255, Math.round(base[2] * f));
        px[p + 3] = 255;
      }
    }
  });
  return px;
}

/* ---------------- 主流程 ---------------- */
async function main() {
  const argv = process.argv.slice(2);
  const reset = argv.includes('--reset');
  const noExport = argv.includes('--no-export');
  const evalMode = argv.includes('--eval');
  fs.mkdirSync(BUILD, { recursive: true });

  const { cubes, bones, fails } = geoMod;
  if (fails.length) throw new Error('几何自检未过：\n  ' + fails.join('\n  '));
  const report = { cubes: cubes.length, bones: bones.length, steps: [], name: TEX_NAME };
  console.log(`[geo] ${bones.length} bones, ${cubes.length} cubes`);

  const faces = faceList(cubes);
  let D = 0, pk = null;
  for (let d = UV_MAX; d >= UV_MIN; d--) { const p = pack(faces, d); if (p) { D = d; pk = p; break; } }
  if (!pk) throw new Error(`UV 图集在 ${UV_MIN} px/u 都放不下（面太多或方块太大）`);
  faces.forEach((o, i) => { o.rect = pk.rects[i]; });
  report.uv = { density: D, atlas_height: pk.used, faces: faces.length };
  console.log(`[uv] ${faces.length} faces @ ${D} px/u, atlas rows -> ${pk.used}/${TEX_SIZE}`);

  const rgba = paint(faces, geoMod.MAT, geoMod.SHADE, TEX_SIZE, TEX_SIZE);
  const texPath = path.join(BUILD, `${TEX_NAME}_tex.png`);
  fs.writeFileSync(texPath, encodePNG(TEX_SIZE, TEX_SIZE, rgba));
  console.log(`[tex] ${texPath} (${fs.statSync(texPath).size} bytes)`);

  const bb = await Bb.connect();
  const tools = await bb.listTools();
  for (const need of ['create_texture', 'add_group', 'place_cube', 'geckolib_export_model']) {
    if (!tools.includes(need)) throw new Error(`MCP 缺少工具 ${need}（当前项目/模式不对？先在 Blockbench 里建一个 geckolib_model 项目）`);
  }

  if (reset) {
    const cl = await bb.t('risky_eval', {
      code: '(function(){var n=0;Project.elements.slice().forEach(function(e){if(e.remove){e.remove();n++;}});'
        + 'Project.groups.slice().forEach(function(g){if(g.remove){g.remove();n++;}});'
        + 'Project.textures.slice().forEach(function(t){if(t.remove){t.remove();n++;}});'
        + 'Project.elements.length=0;Project.groups.length=0;Project.textures.length=0;Outliner.root.length=0;'
        + 'return {removed:n};})()',
    });
    report.steps.push('reset: ' + cl.text.slice(0, 200));
    console.log('[reset]', cl.text.slice(0, 200));
  }

  /* GeckoLib 项目默认按 16x16 解释 UV，会让 512 图集在游戏里整体错位 */
  const uvBase = await bb.t('risky_eval', {
    code: '(function(){Project.texture_width=' + TEX_SIZE + ';Project.texture_height=' + TEX_SIZE + ';'
      + 'try{if(typeof Canvas!=="undefined"&&Canvas.updateAllFaces)Canvas.updateAllFaces();}catch(e){}'
      + 'return {tw:Project.texture_width,th:Project.texture_height};})()',
  });
  report.steps.push('uv base: ' + uvBase.text.slice(0, 300));
  console.log('[uvbase]', uvBase.text.slice(0, 300));

  let r = await bb.t('create_texture', { name: TEX_NAME, width: TEX_SIZE, height: TEX_SIZE, data: texPath });
  report.steps.push('create_texture: ' + r.text.slice(0, 300));
  console.log('[mcp] create_texture ->', r.text.slice(0, 160));

  for (const b of bones) {
    await bb.t('add_group', { name: b.name, origin: b.pivot, parent: b.parent || 'root' });
  }
  report.steps.push(`add_group x${bones.length}`);
  console.log(`[mcp] add_group x${bones.length}`);

  /* 每颗方块的字段（逐颗下发与批量下发两条路共用） */
  const items = cubes.map((c, k) => {
    const uv = {};
    for (const f of FACES) {
      const o = faces.find((q) => q.c === c && q.f === f);
      uv[f] = o.rect;
    }
    return {
      bone: c.bone,
      name: `${c.bone}_${k}`,
      from: [c.origin[0] - GAP_FIX, c.origin[1] - GAP_FIX, c.origin[2] - GAP_FIX].map((v) => +v.toFixed(5)),
      to: [c.origin[0] + c.size[0] + GAP_FIX, c.origin[1] + c.size[1] + GAP_FIX,
        c.origin[2] + c.size[2] + GAP_FIX].map((v) => +v.toFixed(5)),
      origin: (c.pivot || c.origin).map((v) => +v.toFixed(5)),
      rotation: (c.rot || [0, 0, 0]).map((v) => +v.toFixed(4)),
      uv,
    };
  });

  if (evalMode) {
    /* --eval：一次 risky_eval 在进程内批量建方块（插件同款 API）。
     * 为什么要有这条路：逐颗 place_cube 到 500+ 元素时 Blockbench 视口掉到 1 FPS，
     * 桥的每次调用都会撞 75 s 超时 —— 1.1.88 构建连挂两次（480/577 处 FATAL），
     * 而这一步本该是「一次性灌几何」，没有理由走 577 次往返。 */
    const BATCH = 120;
    for (let i = 0; i < items.length; i += BATCH) {
      const slice = items.slice(i, i + BATCH);
      const code = `(function(){
  var FACES = ${JSON.stringify(FACES)};
  var data = ${JSON.stringify(slice)};
  var tex = (Texture.all || []).find(function (t) { return t.name === ${JSON.stringify(TEX_NAME)}; });
  if (!tex) throw new Error('texture missing: ${TEX_NAME}');
  var n = 0, skipped = 0;
  Undo.initEdit({ elements: [], outliner: true });
  for (var i = 0; i < data.length; i++) {
    var d = data[i];
    var g = (Group.all || []).find(function (x) { return x.name === d.bone; });
    if (!g) throw new Error('group missing: ' + d.bone);
    var c = new Cube({ name: d.name, from: d.from, to: d.to, origin: d.origin, rotation: d.rotation, autouv: 0 });
    c.box_uv = false;
    c.init().addTo(g);
    if (c.parent !== g) throw new Error('parent rejected: ' + d.name);
    c.applyTexture(tex, FACES);
    for (var j = 0; j < FACES.length; j++) c.faces[FACES[j]].uv = d.uv[FACES[j]];
    n++;
  }
  Undo.finishEdit('bulk place cubes');
  Canvas.updateAll();
  return JSON.stringify({ placed: n, cubes: (Cube.all || []).length, skipped: skipped });
})()`;
      const rr = await bb.t('risky_eval', { code });
      report.steps.push('bulk_eval: ' + rr.text.slice(0, 200));
      console.log(`[mcp] bulk_eval ${Math.min(i + BATCH, items.length)}/${items.length} -> ${rr.text.slice(0, 120)}`);
    }
  } else {
    const BATCH = 40;
    let placed = 0;
    for (let i = 0; i < items.length; i += BATCH) {
      const slice = items.slice(i, i + BATCH);
      /* cube 级的 rotation/pivot 必须一起下发：枪托每段的 droop 就是靠它，漏了就退化成台阶 */
      const elements = slice.map((c) => ({ name: c.name, from: c.from, to: c.to, origin: c.origin, rotation: c.rotation }));
      const faceArgs = slice.map((c) => FACES.map((f) => ({ face: f, uv: c.uv[f] })));
      const calls = slice.map((c, k) => bb.t('place_cube', {
        group: c.bone,
        texture: TEX_NAME,
        elements: [elements[k]],
        faces: faceArgs[k],
      }).then((rr) => { report.steps.push(`place_cube: ${rr.text.slice(0, 100)}`); }));
      for (let j = 0; j < calls.length; j += 8) await Promise.all(calls.slice(j, j + 8));
      placed += slice.length;
      console.log(`[mcp] place_cube ${placed}/${items.length}`);
    }
  }

  await bb.t('geckolib_set_project_settings', { modid: 'apocalypse_zombies', model_type: 'Item', model_identifier: TEX_NAME });
  const v = await bb.t('geckolib_validate_model', { include_animations: false });
  report.validate = v.text.slice(0, 4000);
  console.log('[validate]', v.text.slice(0, 800));

  if (!noExport) {
    const geoPath = path.join(BUILD, `${TEX_NAME}.geo.json`);
    const e = await bb.t('geckolib_export_model', { path: geoPath, mode: 'compile', max_content_length: 0 });
    report.export = e.text.slice(0, 1000);
    console.log('[export]', e.text.slice(0, 400));
    if (fs.existsSync(geoPath)) {
      const j = JSON.parse(fs.readFileSync(geoPath, 'utf8'));
      const bs = j['minecraft:geometry']?.[0]?.bones || [];
      report.exported = {
        bytes: fs.statSync(geoPath).size,
        bones: bs.length,
        cubes: bs.reduce((n, b) => n + (b.cubes || []).length, 0),
        bone_names: bs.map((b) => b.name),
      };
      console.log(`[exported] ${report.exported.cubes} cubes in ${report.exported.bones} bones -> ${geoPath}`);
    }
  }

  const outPath = path.join(BUILD, `${TEX_NAME}_build.json`);
  fs.writeFileSync(outPath, JSON.stringify(report, null, 1));
  console.log('\n完整回报 ->', outPath);
}

main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
