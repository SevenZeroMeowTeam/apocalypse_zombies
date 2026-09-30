/* 把**已发布的** horde_overlord.geo.json + animation.json 灌回 Blockbench，用来肉眼复核。
 *
 * 为什么要这一步：生成器的 374 条自校验只能证明"数值自洽"，证明不了"看起来对"。
 * 把发布用的那两个 JSON 反向灌进 Blockbench，看到的是真正会进游戏的那份数据。
 *
 * 执行方式（MCP risky_eval）：
 *   (function(){globalThis.__gen_fs__=require('fs');
 *     return (0,eval)(globalThis.__gen_fs__.readFileSync('F:/mcmod/tools/boss_bb_load.js','utf8'));})()
 *
 * 前置：先用 create_project 建一个 geckolib_model 格式的空工程（本脚本会往里灌）。
 * 注意：会清掉工程里的全部动画，再用 JSON 里的那 12 段重建。
 */
(function () {
  var fs = globalThis.__gen_fs__ || require('fs');
  var BASE = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/';
  var GEO = BASE + 'geo/horde_overlord.geo.json';
  var ANIM = BASE + 'animations/horde_overlord.animation.json';
  var TEX = BASE + 'textures/entity/horde_overlord.png';

  var out = {codec: Format.codec, format: Format.id};

  /* ---- 0. 清空：脚本要能反复跑（重跑不清会叠出两套骨/体块）。
   * 注意：Blockbench 里**连续** create_project 会让 Project 变成半初始化的对象
   * （`getMultiFileRuleset is not a function`），必须用下面这行原生入口建工程：
   *   risky_eval: newProject('geckolib_model')
   * 所以清空这段平时都是空转，留着只是为了单工程内二次灌数据。
   */
  try {
    Cube.all.slice().forEach(function (c) { c.remove(); });
  } catch (e) {
    out.clearCubeErr = String(e);
  }
  try {
    Group.all.slice().forEach(function (g) { g.remove(); });
  } catch (e) {
    out.clearGroupErr = String(e);
  }

  /* ---- 1. 几何：交给 Blockbench 自己的 bedrock 编解码器读，不手工拼 bone/cube ---- */
  var data = JSON.parse(fs.readFileSync(GEO, 'utf8'));
  var codec = Codecs[Format.codec] || Codecs.bedrock;
  out.codecUsed = Object.keys(Codecs).filter(function (k) { return Codecs[k] === codec; })[0] || '?';

  try {
    var model = codec.load(data, GEO, false);
    out.loadReturned = !!model;
    if (model) {
      codec.parse(model, GEO, false);
    }
  } catch (e) {
    out.parseErr = String(e);
  }
  out.groupsAfterParse = Group.all.length;
  out.cubesAfterParse = Cube.all.length;

  /* ---- 2. 贴图：GeckoLib 格式是 single_texture，第一张就是模型贴图 ---- */
  try {
    var tex = new Texture();
    if (tex.fromPath) {
      tex.fromPath(TEX, false);
    }
    tex.name = 'horde_overlord';
    tex.add(false);
    out.texture = {name: tex.name, w: tex.width, h: tex.height, uv: tex.uv_width};
  } catch (e) {
    out.textureError = String(e);
  }

  /* ---- 2b. 把贴图绑到每一面 ----
   * 必须显式绑：Blockbench 是在 **解析几何时** 给每面分配 texture 索引的，
   * 这份 geo 里没有 `"texture": 0` 字段，解析时工程里又还没有贴图，于是每面都成了
   * `texture = null` —— 视口里就会用"随机彩色"当占位色，看着像贴图坏了。
   * 先加贴图后解析、或先解析后加贴图，结果都一样：要手动 `face.texture = 0`。
   */
  var bound = 0;
  try {
    Cube.all.forEach(function (c) {
      Object.keys(c.faces).forEach(function (k) {
        if (c.faces[k].texture === null || c.faces[k].texture === undefined) {
          c.faces[k].texture = 0;
          bound++;
        }
      });
    });
  } catch (e) {
    out.bindErr = String(e);
  }
  out.facesBound = bound;
  /* 重绘交给渲染循环；这里的手动重绘在部分工程状态下会踩到多文件规则集
     （`Project.getMultiFileRuleset is not a function`），所以整块包起来 —— 它只是刷新显示，
     不影响数据正确性。 */
  try {
    Canvas.updateAllFaces();
    Canvas.updateAllUVs();
  } catch (e) {
    out.canvasErr = String(e);
  }

  /* ---- 3. 动画：按发布 JSON 逐通道重建关键帧 ---- */
  var adata = JSON.parse(fs.readFileSync(ANIM, 'utf8'));
  var G = {};
  Group.all.forEach(function (g) {
    G[g.name] = g;
  });

  try {
    Project.animations.slice().forEach(function (a) {
      if (a.remove) a.remove();
    });
  } catch (e) {}

  var created = [], missing = [], channels = {}, keys = 0, scaleSeen = 0;
  Object.keys(adata.animations).forEach(function (name) {
    var src = adata.animations[name];
    var a = new Animation({
      name: name, loop: !!src.loop, length: src.animation_length,
      animation_length: src.animation_length, bones: {}, animators: {}
    });
    a.add();
    if (a.setLength) a.setLength(src.animation_length);

    Object.keys(src.bones).forEach(function (bn) {
      var g = G[bn];
      if (!g) {
        missing.push(name + ':' + bn);
        return;
      }
      var an = a.getBoneAnimator(g);
      if (!an) {
        missing.push(name + ':' + bn + ' (no animator)');
        return;
      }
      ['rotation', 'position', 'scale'].forEach(function (ch) {
        var chans = src.bones[bn][ch];
        if (!chans) {
          return;
        }
        if (ch === 'scale') {
          scaleSeen += Object.keys(chans).length;
        }
        Object.keys(chans).forEach(function (t) {
          var v = chans[t];
          var k = new Keyframe({
            channel: ch, time: parseFloat(t), interpolation: 'linear',
            data_points: [{x: v[0], y: v[1], z: v[2]}]
          }, null, an);
          an.pushKeyframe(k);
          keys++;
          channels[ch] = (channels[ch] || 0) + 1;
        });
      });
    });
    created.push(name + ' (' + a.length + 's' + (src.loop ? ', loop' : '') + ')');
  });

  /* ---- 4. 汇总：这几项对不上就说明"进游戏的模型"和生成器不是一份东西 ---- */
  out.groups = Group.all.length;
  out.cubes = Cube.all.length;
  out.roots = Group.all.filter(function (g) { return !g.parent; }).map(function (g) { return g.name; });
  out.animations = created;
  out.animKeys = keys;
  out.channels = channels;
  out.scaleChannels = scaleSeen;
  out.missingBones = missing;
  out.texWidth = Project.texture_width;
  out.texHeight = Project.texture_height;
  out.visibleBounds = [Project.visible_box ? Project.visible_box[0] : null,
                       Project.visible_box ? Project.visible_box[1] : null];
  return out;
})()
