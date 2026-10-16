// _bb_edit_mode.js —— 切回编辑模式（动画模式下 clear 方块会触发 Blockbench 的
// motion-trail bug：'Cannot read properties of undefined (reading fix_rotation)'，
// 结果工程被清空、方块一个都建不进去）。
// Blockbench 的模式切换是 Modes.<id>.select()（Mode.set 不存在）。
try {
  if (typeof Modes !== 'undefined' && Modes.edit && Modes.edit.select) Modes.edit.select();
} catch (e) {}
let mode = 'unknown';
try { mode = (Mode && Mode.id) || mode; } catch (e) {}
if (mode === 'unknown') {
  try { mode = (Modes.selected && Modes.selected.id) || mode; } catch (e) {}
}
return {
  mode,
  cubes: (typeof Cube !== 'undefined' ? Cube.all.length : -1),
  groups: (typeof Group !== 'undefined' ? Group.all.length : -1),
  animations: (typeof Animation !== 'undefined' ? Animation.all.map((a) => a.name) : []),
};
