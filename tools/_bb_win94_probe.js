// 一次性探针：把当前 win94 工程的骨骼树、动画、纹理摘出来（不修改任何东西）。
const out = { project: Project ? Project.name : null, format: Format ? Format.id : null, groups: [], animations: [], textures: [], bones: [] };

function walk(nodes, depth) {
  for (const n of nodes) {
    const row = {
      d: depth, name: n.name, type: n.type,
      origin: n.origin ? n.origin.map((v) => +v.toFixed(2)) : null,
      rot: n.rotation ? n.rotation.map((v) => +v.toFixed(1)) : null,
      kids: (n.children || []).length,
      cubes: (n.children || []).filter((c) => c instanceof Cube).length,
    };
    if (n instanceof Cube) {
      row.from = n.from.map((v) => +v.toFixed(2));
      row.to = n.to.map((v) => +v.toFixed(2));
      out.groups.push(row);
    } else {
      out.groups.push(row);
      if (n.children) walk(n.children, depth + 1);
    }
  }
}
walk(Group.all, 0);

for (const a of Animation.all) {
  out.animations.push({
    name: a.name, loop: a.loop, length: a.length, snapping: a.snapping,
    bone_moves: a.animators.map((an) => ({
      bone: an.name,
      channels: Object.keys(an.keyframes || {}),
      kf_counts: Object.fromEntries(Object.entries(an.keyframes || {}).map(([ch, list]) => [ch, (list || []).length])),
      kf: Object.fromEntries(Object.entries(an.keyframes || {}).map(([ch, list]) => [ch,
        (list || []).map((k) => ({ t: k.time, d: k.data_points ? k.data_points.map((dp) => dp.x) : k.data }))])),
    })),
  });
}

for (const t of Texture.all) {
  out.textures.push({ name: t.name, w: t.width, h: t.height, uv_mode: t.uv_mode, particle: t.particle, source: String(t.source || '').slice(0, 80) });
}

for (const b of (typeof BoneAnimation !== 'undefined' ? [] : [])) out.bones.push(b);
out.uv_groups = (typeof UVEditor !== 'undefined' && UVEditor.isUVEditor) ? 'uv-mode' : 'n/a';

return out;
