// _bb_ensure_project.js —— 确保有打开的工程（B 计划：工程被关掉时自动新建一个 GeckoLib 工程）。
// 2026-10-16：Blockbench 里工程被关掉后，后续所有 MCP 命令都回
// "No project is open. Create one first with new_project."，apply 直接全线失败。
const info = { had: false, created: false };
try { info.had = !!(typeof Project !== 'undefined' && Project && Project.name); } catch (e) {}

if (!info.had) {
  newProject('geckolib_model');
  if (typeof Project !== 'undefined' && Project) {
    Project.name = 'win94';
    Project.texture_width = 512;
    Project.texture_height = 512;
    try { Project.model_identifier = 'win94'; } catch (e) {}
    try { Project.geckolib_model_type = 'animated_entity'; } catch (e) {}
  }
  info.created = true;
}
info.name = (typeof Project !== 'undefined' && Project && Project.name) || null;
info.format = (typeof Project !== 'undefined' && Project && Project.format && Project.format.id) || null;
info.cubes = (typeof Cube !== 'undefined') ? Cube.all.length : -1;
info.groups = (typeof Group !== 'undefined') ? Group.all.length : -1;
try {
  if (typeof Modes !== 'undefined' && Modes.edit && Modes.edit.select) Modes.edit.select();
} catch (e) {}
return info;
