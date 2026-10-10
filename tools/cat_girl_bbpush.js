'use strict';
/* 猫耳娘：把「唯一真相源」art/cat_girl/cat_girl_spec.json 推成 Blockbench 工程。
 *
 * 用法:
 *   node tools/cat_girl_bbpush.js            # 建工程 + 灌骨骼/方块/贴图
 *   node tools/cat_girl_bbpush.js --save     # 额外把工程写回 art/cat_girl/cat_girl.bbmodel
 *
 * 为什么要有这个脚本：cat_girl_build.py 只产 spec + 贴图（真相源），
 * 之前把 spec 灌进 Blockbench 是临时手搓的 —— 这里固化成可复跑的一步。
 * 灌完用 tools/cat_girl_shots.js 抓视图给人眼核验。
 */
const fs = require('fs');
const path = require('path');
const { Bb } = require('./bbmcp_lib.js');

const ROOT = path.resolve(__dirname, '..');
const SPEC = path.join(ROOT, 'art/cat_girl/cat_girl_spec.json').replace(/\\/g, '/');
const TEX = path.join(ROOT, 'src/main/resources/assets/apocalypse_zombies/textures/entity/cat_girl.png').replace(/\\/g, '/');
const BB_OUT = path.join(ROOT, 'art/cat_girl/cat_girl.bbmodel').replace(/\\/g, '/');

const CODE = `(async () => {
  const fs = require('fs');
  const spec = JSON.parse(fs.readFileSync(${JSON.stringify(SPEC)}, 'utf8'));
  const texData = 'data:image/png;base64,' + fs.readFileSync(${JSON.stringify(TEX)}).toString('base64');

  const T = spec.texture_size;
  Project.texture_width = T;
  Project.texture_height = T;

  while (Texture.all.length) Texture.all[0].remove(false);
  const tex = new Texture({ name: 'cat_girl.png', source: texData });
  tex.add(false);
  tex.use_as_default = true;
  if (tex.width) { Project.texture_width = tex.width; Project.texture_height = tex.height; }

  while (Cube.all.length) Cube.all[0].remove(false);
  while (Group.all.length) Group.all[0].remove(false);

  const groups = {};
  for (const b of spec.bones) {
    const g = new Group({ name: b.name, origin: b.pivot }).init();
    if (b.parent && groups[b.parent]) g.addTo(groups[b.parent]);
    groups[b.name] = g;
  }

  let n = 0, noUV = 0;
  for (const c of spec.cubes) {
    const f = c.from, s = c.size;
    const cube = new Cube({
      name: c.name,
      from: f,
      to: [f[0] + s[0], f[1] + s[1], f[2] + s[2]],
      origin: c.pivot || f,
      rotation: c.rot || [0, 0, 0],
      autouv: 0,
      uv: c.uv || [0, 0],
    });
    cube.addTo(groups[c.bone]);
    for (const face of Object.values(cube.faces)) face.texture = 0;
    if (!c.uv) noUV++;
    n++;
  }

  Canvas.updateAll();
  Undo.history.empty();
  return {
    bones: Object.keys(groups).length,
    cubes: n,
    noUV,
    textures: Texture.all.map((t) => t.name + ' ' + t.width + 'x' + t.height),
    res: Project.texture_width + 'x' + Project.texture_height,
  };
})()`;

async function main() {
  const save = process.argv.includes('--save');
  const bb = await Bb.connect();

  const made = await bb.t('create_project', { name: 'cat_girl', format: 'geckolib_model' });
  console.log('create_project ->', typeof made === 'string' ? made.slice(0, 120) : JSON.stringify(made).slice(0, 160));

  const res = await bb.call('risky_eval', { code: CODE });
  console.log('build ->', res.text || JSON.stringify(res).slice(0, 400));

  if (save) {
    const code = `(() => {
      const fs = require('fs');
      const json = Codecs.project.compile(Project, { minified: false });
      fs.writeFileSync(${JSON.stringify(BB_OUT)}, json);
      return { bytes: json.length, out: ${JSON.stringify(BB_OUT)} };
    })()`;
    const s = await bb.call('risky_eval', { code });
    console.log('save ->', s.text || JSON.stringify(s).slice(0, 300));
  }
}

main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
