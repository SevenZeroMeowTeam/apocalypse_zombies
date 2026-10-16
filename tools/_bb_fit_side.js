// _bb_fit_side.js —— 把预览相机摆到模型正侧，并用 camera.zoom 放大到刚好框住模型。
// 不要手改 left/right：Screencam 截图会按输出尺寸重算视锥，手改会被拉伸。
// params: { side:'right'|'left'|'front'|'back', margin:1.06, dist:60, aspect:2.6, zoom:null }
const P = params || {};
const side = P.side || 'right';
const margin = P.margin || 1.06;
const dist = P.dist || 60;

const preview = Preview.selected;
if (preview.setProjectionMode) preview.setProjectionMode(true);

const box = new THREE.Box3();
for (const c of Cube.all) if (c.mesh) box.expandByObject(c.mesh);
const size = box.getSize(new THREE.Vector3());
const center = box.getCenter(new THREE.Vector3());
const cam = preview.camera;

let dir;
if (side === 'right') dir = [1, 0, 0];
else if (side === 'left') dir = [-1, 0, 0];
else if (side === 'front') dir = [0, 0, -1];
else dir = [0, 0, 1];

cam.position.set(center.x + dir[0] * dist, center.y + dir[1] * dist, center.z + dir[2] * dist);
cam.up.set(0, 1, 0);
cam.lookAt(center.x, center.y, center.z);
if (preview.controls) {
  preview.controls.target.set(center.x, center.y, center.z);
  if (preview.controls.update) preview.controls.update();
  if (preview.controls.updateSceneScale) preview.controls.updateSceneScale(); // 让 Blockbench 先给一个合法基础视锥
}

// 基础视锥宽度（zoom=1 时相机覆盖多少世界单位）
const baseW = Math.abs(cam.right - cam.left) || 70;
const wantW = ((side === 'right' || side === 'left') ? size.z : size.x) * margin;
let zoom = P.zoom || (baseW / wantW);
zoom = Math.max(0.05, Math.min(60, zoom));
cam.zoom = zoom;
cam.updateProjectionMatrix();
preview.render();

return {
  side, mode: cam.isOrthographicCamera ? 'ortho' : 'persp',
  center: center.toArray().map((v) => +v.toFixed(3)),
  size: size.toArray().map((v) => +v.toFixed(3)),
  baseW: +baseW.toFixed(3), wantW: +wantW.toFixed(3), zoom: +zoom.toFixed(3),
  frustum: { l: +cam.left.toFixed(2), r: +cam.right.toFixed(2), t: +cam.top.toFixed(2), b: +cam.bottom.toFixed(2) },
};
