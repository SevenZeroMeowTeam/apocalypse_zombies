(function () {
  var S = String.fromCharCode(47);
  var F = 'file:' + S + S + '/F:/mcmod/';
  var OUT = 'F:/mcmod/art/bride/bride_v2.bbmodel';
  var GEO_PATH = 'F:/mcmod/art/bride/bride_zombie.geo.json';
  var R = { stamp: 'bb2', ok: false, errors: [] };

  function walk(group, out) {
    var kids = (group && group.children) || [];
    for (var i = 0; i < kids.length; i++) {
      var k = kids[i];
      if (k && k.type === 'cube') { out.push(k); }
      else if (k && k.children) { walk(k, out); }
    }
    return out;
  }

  function uvStats(cubes) {
    var stat = { faces: 0, oob: 0, overlap: 0, area: 0, keys: {}, distinct: 0, rects: [] };
    var i, f, ci;
    for (ci = 0; ci < cubes.length; ci++) {
      var faces = cubes[ci].faces || {};
      for (f in faces) {
        if (!faces.hasOwnProperty(f)) { continue; }
        var fc = faces[f];
        stat.faces++;
        if (!fc || !fc.uv || fc.uv.length < 4) { stat.rects.push([ci, f, null]); continue; }
        var x1 = Math.round(Math.min(fc.uv[0], fc.uv[2])), x2 = Math.round(Math.max(fc.uv[0], fc.uv[2]));
        var y1 = Math.round(Math.min(fc.uv[1], fc.uv[3])), y2 = Math.round(Math.max(fc.uv[1], fc.uv[3]));
        stat.rects.push([ci, f, [x1, y1, x2, y2]]);
        stat.area += (x2 - x1) * (y2 - y1);
        if (x1 < 0 || y1 < 0 || x2 > 512 || y2 > 512) { stat.oob++; }
        var key = x1 + ',' + y1 + ',' + x2 + ',' + y2;
        stat.keys[key] = (stat.keys[key] || 0) + 1;
      }
    }
    for (var k2 in stat.keys) { stat.distinct++; }
    var grid = new Uint8Array(512 * 512);
    for (i = 0; i < stat.rects.length; i++) {
      var rr = stat.rects[i][2];
      if (!rr) { continue; }
      var key3 = rr[0] + ',' + rr[1] + ',' + rr[2] + ',' + rr[3];
      if (stat.keys[key3] > 1) { continue; }
      for (var y = Math.max(0, rr[1]); y < Math.min(512, rr[3]); y++) {
        for (var x = Math.max(0, rr[0]); x < Math.min(512, rr[2]); x++) {
          var id = y * 512 + x;
          if (grid[id]) { stat.overlap++; }
          grid[id] = 1;
        }
      }
    }
    return stat;
  }

  function loadTexture() {
    return new Promise(function (res) {
      var img = new Image();
      img.onload = function () {
        var c = document.createElement('canvas');
        c.width = img.width; c.height = img.height;
        c.getContext('2d').drawImage(img, 0, 0);
        res({ w: img.width, h: img.height, data: c.toDataURL('image/png', 1) });
      };
      img.onerror = function () { res(null); };
      img.src = F + 'art/bride/bride_zombie.png';
    });
  }

  function vecOf(x) { return x && x.post ? x.post.vector : (x && x.pre ? x.pre.vector : x); }

  return Promise.all([
    fetch(F + 'art/bride/bride_zombie.geo.json').then(function (r) { return r.text(); }),
    fetch(F + 'art/bride/bride_zombie.animation.json').then(function (r) { return r.text(); })
  ])
    .then(function (both) {
      var geoText = both[0], animText = both[1];
      globalThis.__brideGeoSaved = geoText;
      var doc = JSON.parse(geoText);
      var g = doc['minecraft:geometry'][0];
      R.geo_chars = geoText.length;
      R.geo_identifier = g.description.identifier;
      R.geo_texture = [g.description.texture_width, g.description.texture_height];
      R.geo_bones = g.bones.length;
      var rawCubes = 0, rawFaces = 0, rawBad = [], seen = {}, rotBones = [];
      var keys = {}, shared = 0, oob = 0, bi, ci, fk;
      for (bi = 0; bi < g.bones.length; bi++) {
        var b = g.bones[bi];
        if (b.rotation || b.scale) { rotBones.push(b.name); }
        if (seen[b.name]) { rawBad.push('dup-bone:' + b.name); }
        seen[b.name] = 1;
        var cs = b.cubes || [];
        for (ci = 0; ci < cs.length; ci++) {
          rawCubes++;
          var uvm = cs[ci].uv || {};
          for (fk in uvm) {
            if (!uvm.hasOwnProperty(fk)) { continue; }
            rawFaces++;
            var kk = uvm[fk].uv[0] + ',' + uvm[fk].uv[1] + ',' + uvm[fk].uv_size[0] + ',' + uvm[fk].uv_size[1];
            keys[kk] = (keys[kk] || 0) + 1;
            if (uvm[fk].uv[0] < 0 || uvm[fk].uv[1] < 0 || uvm[fk].uv[0] + uvm[fk].uv_size[0] > 512
              || uvm[fk].uv[1] + uvm[fk].uv_size[1] > 512) { oob++; }
          }
        }
      }
      for (var k3 in keys) { if (keys[k3] > 1) { shared++; } }
      R.raw_cubes = rawCubes; R.raw_faces = rawFaces; R.raw_uv_oob = oob;
      R.raw_shared_patch_rects = shared; R.raw_bad = rawBad.slice(0, 5);
      R.raw_rest_rotation_bones = rotBones;

      var ad = JSON.parse(animText);
      R.anim_format = ad.format_version;
      R.anim_clips = Object.keys(ad.animations);
      var scale = [], bad = [], lens = {};
      for (var cn in ad.animations) {
        if (!ad.animations.hasOwnProperty(cn)) { continue; }
        var cl = ad.animations[cn];
        lens[cn] = [cl.animation_length, !!cl.loop];
        for (var bn in cl.bones) {
          if (!cl.bones.hasOwnProperty(bn)) { continue; }
          var ch = cl.bones[bn];
          if (ch.scale) { scale.push(cn + '.' + bn); }
          if (!ch.rotation) { continue; }
          var names = Object.keys(ch.rotation), t0 = null, tE = null;
          for (var ni = 0; ni < names.length; ni++) {
            var tv = parseFloat(names[ni]);
            if (Math.abs(tv) < 0.0001) { t0 = ch.rotation[names[ni]]; }
            if (Math.abs(tv - cl.animation_length) < 0.0001) { tE = ch.rotation[names[ni]]; }
          }
          if (!t0) { bad.push(cn + '.' + bn + ':no-t0'); } else {
            var v0 = vecOf(t0);
            if (Math.abs(v0[0]) > 0.001 || Math.abs(v0[1]) > 0.001 || Math.abs(v0[2]) > 0.001) {
              bad.push(cn + '.' + bn + ':t0=' + JSON.stringify(v0));
            }
          }
          if (!tE) { bad.push(cn + '.' + bn + ':no-end'); } else if (cl.loop) {
            var vS = vecOf(t0 || tE), vE = vecOf(tE);
            if (Math.abs(vE[0] - vS[0]) > 0.001 || Math.abs(vE[1] - vS[1]) > 0.001 || Math.abs(vE[2] - vS[2]) > 0.001) {
              bad.push(cn + '.' + bn + ':seam');
            }
          }
        }
      }
      R.anim_len = lens;
      R.anim_scale_channels = scale;
      R.anim_bad = bad.slice(0, 8);

      return new Promise(function (r1) {
        try { if (typeof Project !== 'undefined' && Project) { Project.is_dirty = false; } } catch (e) { }
        try { if (typeof Dialog !== 'undefined' && Dialog.open) { Dialog.open.close(); } } catch (e) { }
        newProject(Formats.bedrock, { name: 'bride_zombie_phase2' });
        setTimeout(function () { r1(null); }, 600);
      }).then(function () {
        R.project_after_new = (typeof Project !== 'undefined' && Project)
          ? (Project.format ? Project.format.id : 'no-format') : 'null-project';
        try {
          Project.texture_width = 512;
          Project.texture_height = 512;
        } catch (e) { R.errors.push('texsize:' + String(e)); }
        try {
          Project.box_uv = false;
          R.project_box_uv_before_load = Project.box_uv;
        } catch (e) { R.errors.push('boxuv:' + String(e)); }
        try {
          Codecs.bedrock.load(JSON.parse(geoText), { path: GEO_PATH, no_file: true });
          R.bedrock_parse_ok = true;
        } catch (e) { R.errors.push('load:' + String(e)); }
        return new Promise(function (r2) { setTimeout(function () { r2(null); }, 500); });
      }).then(function () {
      R.bb_format = (typeof Project !== 'undefined' && Project && Project.format) ? Project.format.id : null;
      R.bb_geometry_name = (typeof Project !== 'undefined' && Project) ? (Project.geometry_name || null) : null;
      R.bb_texture_size = (typeof Project !== 'undefined' && Project) ? [Project.texture_width, Project.texture_height] : null;
      R.bb_outliner_roots = (typeof Outliner !== 'undefined' && Outliner.root) ? Outliner.root.length : -1;
      var groups = (Group && Group.all) ? Group.all : [];
      R.bb_groups = groups.length;
      var names2 = [];
      for (var gi = 0; gi < groups.length; gi++) { names2.push(groups[gi].name); }
      R.bb_bone_names = names2.sort();

      var cubes = walk({ children: (Outliner && Outliner.root) ? Outliner.root : [] }, []);
      if (!cubes.length) { for (var gj = 0; gj < groups.length; gj++) { walk(groups[gj], cubes); } }
      var uniq = {}, list = [];
      for (var qi = 0; qi < cubes.length; qi++) {
        if (!uniq[cubes[qi].uuid]) { uniq[cubes[qi].uuid] = 1; list.push(cubes[qi]); }
      }
      cubes = list;
      R.bb_cubes = cubes.length;
      R.bb_box_uv = cubes.length ? !!cubes[0].box_uv : null;
      var st = uvStats(cubes);
      R.bb_faces = st.faces;
      R.bb_uv_distinct_rects = st.distinct;
      R.bb_uv_area_texels = st.area;
      R.bb_face_uv_oob = st.oob;
      R.bb_face_uv_overlap_texels = st.overlap;
      var sample = null;
      for (var si = 0; si < st.rects.length; si++) {
        if (st.rects[si][2]) { sample = [st.rects[si][0] + ':' + st.rects[si][1], st.rects[si][2]]; break; }
      }
      R.bb_first_face_uv = sample;

      return loadTexture().then(function (t) {
        if (!t) { R.errors.push('texture-load-failed'); return null; }
        R.png_size = [t.w, t.h];
        var tex = new Texture({ name: 'bride_zombie', uv_width: t.w, uv_height: t.h });
        try { tex.fromDataURL(t.data); } catch (e) { R.errors.push('fromDataURL:' + String(e)); }
        try { tex.add(); } catch (e) { R.errors.push('texture-add:' + String(e)); }
        R.tex_uuid = tex.uuid;
        R.tex_size = [tex.uv_width, tex.uv_height];
        var assigned = 0;
        for (var i2 = 0; i2 < cubes.length; i2++) {
          var fc2 = cubes[i2].faces || {};
          for (var f2 in fc2) {
            if (!fc2.hasOwnProperty(f2)) { continue; }
            try { fc2[f2].texture = tex.uuid; assigned++; } catch (e2) { R.errors.push('faceTex:' + String(e2)); }
          }
        }
        R.faces_textured = assigned;
        var st2 = uvStats(cubes);
        R.bb_face_uv_oob_after = st2.oob;
        R.bb_uv_area_after = st2.area;
        return null;
      });
      })
    })
    .then(function () {
      var model = Codecs.project.compile({ raw: false });
      R.bbmodel_chars = model.length;
      try {
        Blockbench.writeFile(OUT, { content: model });
        R.bbmodel_saved = true;
        try { Project.is_dirty = false; } catch (e) { }
      }
      catch (e) { R.bbmodel_saved = false; R.errors.push('write:' + String(e)); }
      try {
        var reText = Codecs.bedrock.compile({ raw: false });
        R.reexported_geo_chars = reText.length;
        var re = JSON.parse(reText)['minecraft:geometry'][0];
        var orig = JSON.parse(globalThis.__brideGeoSaved)['minecraft:geometry'][0];
        var nb = {}, ob = {}, nbc = 0, obc = 0, i4;
        for (i4 = 0; i4 < re.bones.length; i4++) { nb[re.bones[i4].name] = (re.bones[i4].cubes || []).length; nbc += (re.bones[i4].cubes || []).length; }
        for (i4 = 0; i4 < orig.bones.length; i4++) { ob[orig.bones[i4].name] = (orig.bones[i4].cubes || []).length; obc += (orig.bones[i4].cubes || []).length; }
        var diff = [], k5;
        for (k5 in ob) { if (nb[k5] === undefined || nb[k5] !== ob[k5]) { diff.push(k5 + ':' + ob[k5] + '->' + (nb[k5] === undefined ? 'x' : nb[k5])); } }
        for (k5 in nb) { if (ob[k5] === undefined) { diff.push('extra:' + k5); } }
        R.roundtrip_bones_match = diff.length === 0;
        R.roundtrip_cube_counts = [obc, nbc];
        R.roundtrip_diff = diff.slice(0, 6);
        function bustOf(d) {
          for (var i5 = 0; i5 < d.bones.length; i5++) {
            if (d.bones[i5].name === 'bust_r' && (d.bones[i5].cubes || []).length) {
              var c0 = d.bones[i5].cubes[0];
              var uvN = c0.uv ? (c0.uv.north ? c0.uv.north.uv : c0.uv) : null;
              return { origin: c0.origin, size: c0.size, north: uvN };
            }
          }
          return null;
        }
        R.roundtrip_bust_orig = bustOf(orig);
        R.roundtrip_bust_re = bustOf(re);
      } catch (e) { R.errors.push('recompile:' + String(e)); }
      R.ok = R.errors.length === 0 && R.bb_cubes > 0 && R.bb_face_uv_oob === 0;
      return R;
    })
    .catch(function (e) {
      R.errors.push('fatal:' + String(e));
      R.fatal = e && e.stack ? String(e.stack).slice(0, 300) : null;
      return R;
    });
})()