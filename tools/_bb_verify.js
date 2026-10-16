// _bb_verify.js —— 建造完核对：方块数 / 骨骼数 / 契约骨骼名 / 动画条数。
// 任何一项不符就 throw，让 MCP 回 ok:false，apply 立刻失败 ——
// 免得再出现"看着建完了、导出的 geo 却是 0 bones"这种情况（2026-10-16 踩过一次）。
// params: { cubes, groups, bones: [...], animations: [...] }
const P = params || {};
const names = Group.all.map((g) => g.name);
const anims = Animation.all.map((a) => a.name);
const problems = [];

if (typeof P.cubes === 'number' && Cube.all.length !== P.cubes) {
  problems.push(`方块数 ${Cube.all.length} != 期望 ${P.cubes}`);
}
if (typeof P.groups === 'number' && Group.all.length !== P.groups) {
  problems.push(`骨骼数 ${Group.all.length} != 期望 ${P.groups}`);
}
for (const b of (P.bones || [])) {
  if (!names.includes(b)) problems.push(`缺契约骨骼 ${b}`);
}
for (const a of (P.animations || [])) {
  if (!anims.includes(a)) problems.push(`缺契约动画 ${a}`);
}
// 贴图与动画属于后续步骤（import_texture / create_animation），
// 只有显式要求时才查 —— apply 阶段查这两项会必然失败。
if (P.require_texture && Texture.all.length < 1) problems.push('没有贴图');

const out = {
  cubes: Cube.all.length,
  groups: Group.all.length,
  textures: Texture.all.length,
  animations: anims.length,
  bones: names.join(','),
};
if (problems.length) throw new Error('建造校验不通过：' + problems.join(' | '));
return out;
