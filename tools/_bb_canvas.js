// _bb_canvas.js —— 把 Blockbench 预览画布临时改宽（截图通道是竖屏画布，枪会被缩得很小）。
// params: { width:1400, height:520, restore:false }
const P = params || {};
const preview = Preview.selected;
const el = preview.canvas;
const info0 = {
  attr: [el.width, el.height],
  style: [el.style.width, el.style.height],
  client: [el.clientWidth, el.clientHeight],
  aspect: preview.camera ? preview.camera.aspect : null,
};

let info1 = null;
if (!P.restore && P.width && P.height) {
  el.width = P.width;
  el.height = P.height;
  el.style.width = P.width + 'px';
  el.style.height = P.height + 'px';
  try { if (preview.onResize) preview.onResize(); } catch (e) {}
  try { if (preview.updateAspectRatio) preview.updateAspectRatio(); } catch (e) {}
  if (preview.camera) {
    preview.camera.aspect = P.width / P.height;
    preview.camera.updateProjectionMatrix();
  }
  preview.render();
  info1 = {
    attr: [el.width, el.height],
    style: [el.style.width, el.style.height],
    client: [el.clientWidth, el.clientHeight],
    aspect: preview.camera ? preview.camera.aspect : null,
  };
}
return { before: info0, after: info1 };
