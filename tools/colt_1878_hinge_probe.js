'use strict';
/* 折开轴探针：验证「枪管到底该绕哪一根轴、往哪个方向折」（纯几何量测，不依赖截图）。
 *
 * 留着它是因为 tools/colt_1878_anim.js 里折开通道的**轴和符号**就是靠它定下来的 ——
 * 以后谁再动那个通道，先跑一遍这个再改，别靠推理。
 *
 * 做法：把 barrel 的 rest rotation 设成绕 X / 绕 Z 的角度，重算，
 * 再读枪管 cube 的 **世界矩阵平移**（mesh.position 是静止的，变换在 matrixWorld 上），
 * 看枪口那一端（z 最负）的 y 是往下（负）还是往上（正）。
 * 实测结论：X −62 → 枪口朝下（真枪的折开）；Z −52 → 只是滚转，枪口位置几乎不动。
 *
 * 跑完自动还原 rest rotation = 0。
 * 用法: node tools/colt_1878_hinge_probe.js
 */
const { Bb } = require('./bbmcp_lib.js');

const CODE = (rot) => '(function(){'
  + 'var b=Group.all.find(function(x){return x.name==="barrel";});if(!b)return {err:"no barrel"};'
  + 'b.rotation=' + JSON.stringify(rot) + ';'
  + 'if(typeof Canvas!=="undefined"&&Canvas.updateAll)Canvas.updateAll();'
  + 'function wp(c){if(!c||!c.mesh)return null;c.mesh.updateWorldMatrix(true,false);'
  + '  var e=c.mesh.matrixWorld.elements;'
  + '  return [+e[12].toFixed(3),+e[13].toFixed(3),+e[14].toFixed(3)];}'
  + 'var out=[];["barrel_0","barrel_8","barrel_9","barrel_17"].forEach(function(n){'
  + '  var c=Cube.all.find(function(x){return x.name===n;});var p=wp(c);'
  + '  if(p)out.push({n:n,p:p});});'
  + 'var ys=out.map(function(o){return o.p[1];});'
  + 'return {rot:String(b.rotation.x)+","+String(b.rotation.y)+","+String(b.rotation.z),probe:out,'
  + '  yOfFront:out.length?out[0].p[1]:null,yMin:+Math.min.apply(null,ys).toFixed(3),yMax:+Math.max.apply(null,ys).toFixed(3)};'
  + '})()';

async function main() {
  const bb = await Bb.connect();
  for (const [tag, rot] of [['rest', [0, 0, 0]], ['X_-62', [-62, 0, 0]], ['X_+62', [62, 0, 0]], ['Z_-52', [0, 0, -52]]]) {
    const r = await bb.t('risky_eval', { code: CODE(rot) });
    console.log(tag.padEnd(6), r.text.replace(/\s+/g, ' ').slice(0, 460));
  }
  const back = await bb.t('risky_eval', { code: CODE([0, 0, 0]) });
  console.log('restore', back.text.replace(/\s+/g, ' ').slice(0, 200));
}
main().catch((e) => { console.error('FATAL', e.message); process.exit(1); });
