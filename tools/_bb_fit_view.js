// _bb_fit_view.js —— 把预览相机摆成正侧视并**直接设正交视锥**框住模型。
// 与 _bb_fit_side.js 的区别：那版用 camera.zoom，会被 Screencam/controls 重置；
// 这版直接写 left/right/top/bottom，并且要求画布本身已是宽屏（_bb_canvas.js）。
// params: { side:'right'|'left', margin:1.06, aspect:2.6923, dist:60 }
const P = params || {};
const side = P.side || 'left';
const margin = P.margin || 1.06;
const dist = P.dist || 60;

const preview = Preview.selected;
if (preview.setProjectionMode) preview.setProjectionMode(true);

const box = new THREE.Box3();
for (const c of Cube.all) if (c.mesh) box.expandByObject(c.mesh);
const size = box.getSize(new THREE.Vector3());
const center = box.getCenter(new THREE.Vector3());
const cam = preview.camera;
const canvas = preview.canvas;
const aspect = P.aspect || (canvas && canvas.height ? canvas.width / canvas.height : 2.6923);

let dir = [0, 0, 0];
if (side === 'left') dir = [-1, 0, 0];
else if (side === 'right') dir = [1, 0, 0];
else if (side === 'front') dir = [0, 0, -1];
else dir = [0, 0, 1];

let halfW = (size.z / 2) * margin;
let halfH = halfW / aspect;
if (halfH < (size.y / 2) * margin) { halfH = (size.y / 2) * margin; halfW = halfH * aspect; }

cam.left = -halfW; cam.right = halfW; cam.top = halfH; cam.bottom = -halfH;
cam.zoom = 1;
cam.position.set(center.x + dir[0] * dist, center.y + dir[1] * dist, center.z + dir[2] * dist);
cam.up.set(0, 1, 0);
cam.lookAt(center.x, center.y, center.z);
if (preview.controls) preview.controls.target.set(center.x, center.y, center.z);
cam.updateProjectionMatrix();
preview.render();

return {
  side, canvas: canvas ? [canvas.width, canvas.height] : null,
  aspect: +aspect.toFixed(3),
  center: center.toArray().map((v) => +v.toFixed(3)),
  size: size.toArray().map((v) => +v.toFixed(3)),
  frustum: { l: +cam.left.toFixed(3), r: +cam.right.toFixed(3), t: +cam.top.toFixed(3), b: +cam.bottom.toFixed(3) },
  camPos: cam.position.toArray().map((v) => +v.toFixed(2)),
};
