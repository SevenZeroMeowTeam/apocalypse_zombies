// _bb_reset.js —— 把工程复位到"空工程 + 编辑模式"，好让 apply 重新建。
// 背景：动画模式下删方块会触发 Blockbench 渲染层的 motion-trail bug
// ('Cannot read properties of undefined (reading fix_rotation)')，
// 于是 clear 半途失败、方块一个都没建上，工程变成空壳。
// 这里先取消动画选择、停掉预览（motion trail 就不再有对象可引用），再切模式、清骨骼。
const log = {};
try {
  Animation.all.forEach((a) => { a.selected = false; });
} catch (e) { log.animErr = String(e && e.message); }
try { if (typeof Animator !== 'undefined' && Animator.preview) Animator.preview(); } catch (e) {}
try { if (typeof Modes !== 'undefined' && Modes.edit && Modes.edit.select) Modes.edit.select(); }
catch (e) { log.modeErr = String(e && e.message); }
log.modeAfterSelect = (typeof Mode !== 'undefined' && Mode && Mode.id) || 'unknown';
try {
  const gs = Group.all.slice();
  gs.forEach((g) => g.remove());
  log.removedGroups = gs.length;
} catch (e) { log.groupErr = String(e && e.message); }
log.cubes = (typeof Cube !== 'undefined' ? Cube.all.length : -1);
log.groups = (typeof Group !== 'undefined' ? Group.all.length : -1);
log.modeFinal = (typeof Mode !== 'undefined' && Mode && Mode.id) || 'unknown';
return log;
