'use strict';
/* 折开方式的探针：确认「机匣+枪托绕铰链向上翻、而枪管在世界坐标里不动」所需的轴与符号。
 *
 * 为什么留着它：折开现在是**两个骨反向转**实现的（body 绕铰链上翻 + barrel 反向补偿），
 * 两者必须绕**同一个 pivot** 才抵得干净 —— body 的 pivot 就是铰链（见 tools/colt_1878_geo.js）。
 * 以后谁再动这两个通道，先跑一遍这个：rest 那一行与补偿那一行的 muzzle/回收值应当**逐位相同**。
 *
 * 用法: node tools/colt_1878_fold_probe.js
 */
const { Bb } = require('./bbmcp_lib.js');

const CODE = (bodyRot, barrelRot) => '(function(){'
  + 'var B=Group.all.find(function(x){return x.name==="body";});'
  + 'var R=Group.all.find(function(x){return x.name==="barrel";});'
  + 'if(!B||!R)return {err:"no bones"};'
  + 'B.rotation=' + JSON.stringify(bodyRot) + ';R.rotation=' + JSON.stringify(barrelRot) + ';'
  + 'if(typeof Canvas!=="undefined"&&Canvas.updateAll)Canvas.updateAll();'
  + 'function wp(c){if(!c||!c.mesh)return null;c.mesh.updateWorldMatrix(true,false);'
  + '  var e=c.mesh.matrixWorld.elements;return [+e[12].toFixed(3),+e[13].toFixed(3),+e[14].toFixed(3)];}'
  + 'function first(p){return wp(Cube.all.find(function(x){return x.name.indexOf(p)===0;}));}'
  + 'return {bodyPivot:B.origin?[B.origin[0],B.origin[1],B.origin[2]]:null,'
  + '  barrelPivot:R.origin?[R.origin[0],R.origin[1],R.origin[2]]:null,'
  + '  recv:first("body_"), muzzle:first("barrel_"), shell:first("shell_upper_")};'
  + '})()';

const f = (a) => (a ? `[${a.map((v) => String(v).padStart(8)).join(',')}]` : '          -          ');

async function main() {
  const bb = await Bb.connect();
  const cases = [
    ['rest（合膛）', [0, 0, 0], [0, 0, 0]],
    ['body -62 无补偿', [-62, 0, 0], [0, 0, 0]],
    ['body +62 无补偿', [62, 0, 0], [0, 0, 0]],
    ['body -62 / barrel +62', [-62, 0, 0], [62, 0, 0]],
    ['body +62 / barrel -62', [62, 0, 0], [-62, 0, 0]],
  ];
  for (const [tag, b, r] of cases) {
    const res = await bb.t('risky_eval', { code: CODE(b, r) });
    const j = JSON.parse(res.text);
    if (j.err) { console.log('ERR', j.err); break; }
    console.log(tag.padEnd(24), '机匣' + f(j.recv), '枪管' + f(j.muzzle), '壳' + f(j.shell));
  }
  const back = await bb.t('risky_eval', { code: CODE([0, 0, 0], [0, 0, 0]) });
  const j = JSON.parse(back.text);
  console.log('pivot  body =', JSON.stringify(j.bodyPivot), ' barrel =', JSON.stringify(j.barrelPivot));
}
main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
