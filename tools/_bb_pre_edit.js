// _bb_pre_edit.js —— 重建前的预处理：取消动画选择、停掉动画预览、切回编辑模式。
//
// 为什么必须有这一步：Blockbench 停在 **animate 模式**时，删方块会触发渲染层的
// motion-trail bug（'Cannot read properties of undefined (reading fix_rotation)'），
// clear 半途失败 —— 方块全被删掉但一个都建不上，工程直接变成空壳、导出的 geo 只剩
// 181 B / 0 bones。2026-10-16 踩过一次，丢掉了整份模型（靠生成器重建才恢复）。
const log = {};
try { Animation.all.forEach((a) => { a.selected = false; }); } catch (e) { log.animErr = String(e && e.message); }
try { if (typeof Animator !== 'undefined' && Animator.preview) Animator.preview(); } catch (e) {}
try { if (typeof Modes !== 'undefined' && Modes.edit && Modes.edit.select) Modes.edit.select(); }
catch (e) { log.modeErr = String(e && e.message); }
log.mode = (typeof Mode !== 'undefined' && Mode && Mode.id) || 'unknown';
log.cubes = (typeof Cube !== 'undefined' ? Cube.all.length : -1);
log.groups = (typeof Group !== 'undefined' ? Group.all.length : -1);
return log;
