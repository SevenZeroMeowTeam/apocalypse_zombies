/* ============================================================================
 * bride_zombie_skin.js —— 「美女僵尸 / bride_zombie」64×64 皮肤生成器
 *
 * 用法（Blockbench 桌面版 + MCP 插件；**没开工程也能跑**——贴图只活在 canvas 上直接落盘）：
 *   eval(require('fs').readFileSync('F:/mcmod/tools/bride_zombie_skin.js','utf8'))
 * 脚本会：创建（或复用它已有的）名为 bride_zombie 的 64×64 贴图 → 按原版人形 UV
 * 布局逐像素画 → 用 fs 直接把 PNG 写进资源目录。全程不依赖任何外部图片。
 *
 * 布局用的是 1.8+ 的「无称人形」标准 UV（与 skin 格式一致）：
 *   head 8×8×8 @ (0,0)      hat 覆盖层 @ (32,0)
 *   body 8×12×4 @ (16,16)   right_arm 4×12×4 @ (40,16)
 *   right_leg 4×12×4 @(0,16) left_arm @ (32,48)  left_leg @ (16,48)
 *   胸部补块 2×3×1 ×2 @ (0,32)/(12,32) —— BrideModel.createBodyLayer() 额外挂的两瓣，
 *   刻意用 v=32 那条标准布局里的空带，不覆盖任何原版区域。
 *
 * 画的东西：苍白泛绿的尸肤、暗红瞳、缝线嘴、及腰黑长发（含覆盖层做发量）、
 * 深色束腰 + 破损象牙长裙、裙摆破口露出的赤足、各处血渍。
 * 随机噪声全部走固定种子，同一颗种子画出来永远是同一张图。
 * ==========================================================================*/
(function () {
  var OUT = 'F:/mcmod/src/main/resources/assets/apocalypse_zombies/textures/entity/bride_zombie.png';
  var NAME = 'bride_zombie';

  var tex = Texture.all.find(function (t) { return t.name === NAME; });
  if (!tex) {
    tex = new Texture({ name: NAME, width: 64, height: 64 });
    // 无工程模式下 Texture.add() 会在 Blockbench 内部炸（读 undefined.includes，见 bundle.js Mi.add）：
    // 贴图挂进工程只影响在 Blockbench 里看不看得见，落盘走的是这张 canvas，所以这步允许失败。
    try { tex.add(false); } catch (e) { /* 没有工程开着：canvas-only 模式，照画照写 */ }
  }
  // Blockbench 的 Texture 构造参数不一定落到 canvas 上，尺寸显式掰正（改 canvas 尺寸会重置上下文）
  tex.canvas.width = 64;
  tex.canvas.height = 64;
  tex.width = 64;
  tex.height = 64;
  if (tex.uv_width !== undefined) { tex.uv_width = 64; tex.uv_height = 64; }
  var cv = tex.canvas || (tex.ctx && tex.ctx.canvas);
  var ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, 64, 64);

  // ---------------------------------------------------------------- 调色板
  var P = {
    s: [201, 212, 178], S: [222, 231, 202], d: [172, 184, 150], k: [139, 151, 120],
    r: [120, 133, 101], R: [95, 107, 80],
    h: [26, 24, 34],  H: [49, 45, 63],     g: [14, 13, 20],
    D: [224, 219, 204], d2: [190, 183, 167], L: [152, 144, 126],
    w: [58, 44, 54],  W: [80, 62, 74],
    B: [122, 26, 30], b: [78, 18, 22],
    e: [24, 20, 24],  i: [196, 24, 42],    I: [246, 74, 86],
    m: [46, 32, 40],  T: [226, 221, 206]
  };

  function px(x, y, c, a) {
    ctx.fillStyle = 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + (a === undefined ? 255 : a) + ')';
    ctx.fillRect(x, y, 1, 1);
  }
  function fill(x, y, w, h, c) {
    ctx.fillStyle = 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',255)';
    ctx.fillRect(x, y, w, h);
  }
  function clear(x, y, w, h) { ctx.clearRect(x, y, w, h); }

  /** 按字符网格 stamp：'.' = 跳过（保留底色），其余查调色板。 */
  function stamp(x0, y0, rows) {
    for (var y = 0; y < rows.length; y++) {
      var row = rows[y];
      for (var x = 0; x < row.length; x++) {
        var ch = row.charAt(x);
        if (ch === '.' || ch === ' ') continue;
        var c = P[ch];
        if (c) px(x0 + x, y0 + y, c);
      }
    }
  }

  // 固定种子 PRNG（mulberry32）
  var seed = 0x9A17C0;
  function rnd() {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  function clamp255(v) { return v < 0 ? 0 : (v > 255 ? 255 : v | 0); }

  /** 逐像素亮度扰动：脏污/磨损。只在已上色的不透明像素上动，alpha 保持 255。 */
  function grime(x, y, w, h, prob, amount) {
    var img = ctx.getImageData(x, y, w, h), p = img.data;
    for (var i = 0; i < w * h; i++) {
      var o = i * 4;
      if (p[o + 3] === 0) continue;
      if (rnd() < prob) {
        var k = amount * (rnd() < 0.5 ? 1 : -1);
        p[o] = clamp255(p[o] + k); p[o + 1] = clamp255(p[o + 1] + k); p[o + 2] = clamp255(p[o + 2] + k);
      }
    }
    ctx.putImageData(img, x, y);
  }

  /** 血渍：从 (x,y) 随机游走出 n 个像素。 */
  function splatter(x, y, n, dark) {
    var cx = x, cy = y;
    for (var i = 0; i < n; i++) {
      px(cx, cy, dark ? P.b : P.B);
      cx += (rnd() < 0.5 ? -1 : 1) * (rnd() < 0.3 ? 0 : 1);
      cy += rnd() < 0.55 ? 0 : (rnd() < 0.5 ? -1 : 1);
      if (cx < x - 2) cx = x - 2; if (cx > x + 2) cx = x + 2;
      if (cy < y - 2) cy = y - 2; if (cy > y + 3) cy = y + 3;
    }
  }

  // ================================================================ 头
  fill(0, 0, 32, 16, P.s);      // 头 + 底/顶面先铺肤色
  fill(0, 0, 8, 8, P.h);        // top -> 头发
  fill(16, 0, 8, 8, P.d);       // bottom（脖子底面，几乎看不到）
  // 两侧：整片头发，最下面 2 行留出下颌
  fill(0, 8, 8, 6, P.h);
  fill(0, 14, 8, 2, P.s);
  fill(16, 8, 8, 6, P.h);
  fill(16, 14, 8, 2, P.s);
  px(3, 9, P.H); px(4, 11, P.H); px(1, 12, P.g);   // 左鬓发丝
  px(18, 9, P.H); px(21, 12, P.H); px(22, 13, P.g);
  // 后脑：全头发 + 发丝
  fill(24, 8, 8, 8, P.h);
  px(26, 9, P.H); px(29, 10, P.H); px(31, 13, P.H); px(25, 14, P.g);
  // 脸（正面 8×8 @ (8,8)）
  fill(8, 8, 8, 8, P.s);
  stamp(8, 8, [
    'hhhhhhhh',   // y=8  发际
    'hHhhhhHh',   // y=9  刘海
    'hhhsshhh',   // y=10 刘海缺口露出额头
    'sssssssd',   // y=11
    'seeeseed',   // y=12 眼窝（内凹）
    'sriSriSd',   // y=13 红瞳
    'sssmmssd',   // y=14 缝线嘴
    'ksTmmTsd'    // y=15 下巴 / 牙 / 腐斑
  ]);
  px(7 + 1, 13, P.i);                        // 瞳高光（左）
  splatter(9, 15, 3, false);                 // 嘴角血
  px(14, 10, P.k); px(13, 11, P.k);          // 腐斑

  // ================================================================ 头部覆盖层（hat）：长发的量感
  clear(32, 0, 32, 16);
  fill(40, 0, 8, 8, P.h);        // overlay top
  fill(32, 8, 8, 8, P.h);        // overlay 左侧
  fill(48, 8, 8, 8, P.h);        // overlay 右侧
  fill(56, 8, 8, 8, P.h);        // overlay 后脑（长发披到背）
  px(58, 10, P.H); px(61, 12, P.H); px(57, 14, P.g);
  px(34, 9, P.H); px(52, 11, P.H);
  // overlay 正面只留刘海，其余透明，别挡住脸
  fill(40, 8, 8, 2, P.h);
  px(41, 10, P.h); px(44, 10, P.H); px(47, 10, P.h);
  px(43, 11, P.h); px(46, 11, P.h);

  // ================================================================ 躯干 8×12×4 @ (16,16)
  fill(16, 16, 24, 16, P.D);               // 整块先铺裙布
  fill(16, 16, 8, 4, P.s);                 // body top：肩颈
  fill(28, 16, 8, 4, P.L);                 // body bottom：裙内阴影
  // 正面 (20,20)
  stamp(20, 20, [
    'DDDsDDDD',   // 领口
    'DDBsBDDD',   // 领口血点
    'DDDDsDDD',   // 胸衣
    'hDDDDDDh',   // 垂到胸前的两缕发
    'wwwwwwww',   // 束腰上缘
    'wWWwwWww',   // 束腰绑带
    'wwWwwWww',
    'wwwwwwww',   // 束腰下缘
    'DDdDDdDD',   // 裙褶
    'DdDDdDDd',
    'bDDLDDLD',   // 血渍 + 褶皱
    'LdDLDdLD'    // 破损裙摆
  ]);
  splatter(21, 27, 4, true);
  // 背面 (32,20)：长发垂到背 + 束腰交叉绑带
  stamp(32, 20, [
    'hhDDDDhh',
    'hHDDDDhh',
    'hhDDDDhg',
    'hDDDDDDh',
    'wwwwwwww',
    'cwWWWwcc',
    'ccWwWWcc',
    'wwwwwwww',
    'DDdDDdDD',
    'DddDDddD',
    'bDDDDbDD',
    'LLDLDDLD'
  ]);
  // 两侧 (16,20) / (28,20)：裙侧 + 束腰 + 血痕
  stamp(16, 20, ['DDDD', 'DDdD', 'DDDD', 'DhDh', 'wwww', 'wWww', 'wwwW', 'wwww', 'DDdD', 'DdDD', 'bDDD', 'LLDL']);
  stamp(28, 20, ['DDDD', 'DdDD', 'DDdD', 'hDhD', 'wwww', 'wwWw', 'Wwww', 'wwww', 'DdDD', 'DDdD', 'DDbD', 'LDLL']);
  px(17, 22, P.b); px(30, 25, P.B);

  // ================================================================ 右臂 4×12×4 @ (40,16)
  fill(40, 16, 16, 16, P.s);
  fill(44, 16, 4, 4, P.D);   // arm top：泡泡袖肩
  fill(48, 16, 4, 4, P.s);   // arm bottom：掌心
  stamp(40, 20, ['DDDD', 'DDdD', 'DdDD', 'DDBD', 'ssss', 'ssds', 'sBss', 'dssd', 'ssss', 'ssss', 'ssdS', 'sSd.']);
  stamp(44, 20, ['DDDD', 'dDDD', 'DDdD', 'DDDD', 'ssss', 'ssds', 'ssBs', 'sdss', 'ssss', 'ssss', 'ssSS', 'dS.i']);
  stamp(48, 20, ['DDDD', 'DDDd', 'DDDD', 'DDDD', 'ssss', 'ssss', 'sdsd', 'ssss', 'ssss', 'ssdS', 'sSSd', 's.i.']);
  stamp(52, 20, ['DDDD', 'DDDD', 'dDDD', 'DDdD', 'ssss', 'sdss', 'ssss', 'ssds', 'ssss', 'ssss', 'SSdd', 'sd.s']);

  // ================================================================ 左臂 4×12×4 @ (32,48)
  fill(32, 48, 16, 16, P.s);
  fill(36, 48, 4, 4, P.D);
  fill(40, 48, 4, 4, P.s);
  stamp(32, 52, ['DDDD', 'DDdD', 'DdDD', 'DDBD', 'ssss', 'ssds', 'sBss', 'dssd', 'ssss', 'ssss', 'ssdS', 'sSd.']);
  stamp(36, 52, ['DDDD', 'dDDD', 'DDdD', 'DDDD', 'ssss', 'ssds', 'ssBs', 'sdss', 'ssss', 'ssss', 'ssSS', 'dS.i']);
  stamp(40, 52, ['DDDD', 'DDDd', 'DDDD', 'DDDD', 'ssss', 'ssss', 'sdsd', 'ssss', 'ssss', 'ssdS', 'sSSd', 's.i.']);
  stamp(44, 52, ['DDDD', 'DDDD', 'dDDD', 'DDdD', 'ssss', 'sdss', 'ssss', 'ssds', 'ssss', 'ssss', 'SSdd', 'sd.s']);

  // ================================================================ 右腿 4×12×4 @ (0,16)
  fill(0, 16, 16, 16, P.D);
  fill(4, 16, 4, 4, P.D);    // leg top
  fill(8, 16, 4, 4, P.s);    // leg bottom：脚底
  stamp(0, 20, ['DDDD', 'DdDD', 'DDdD', 'DDDD', 'DdDD', 'DDdD', 'DDDD', 'DdDD', 'DDDd', 'dsDD', 'sdDD', 'ssds']);
  stamp(4, 20, ['DDDD', 'dDDD', 'DDdD', 'DDDD', 'DdDD', 'DDdD', 'DDBD', 'DDDD', 'dDDd', 'dsdD', 'ssds', 'sdsd']);
  stamp(8, 20, ['DDDD', 'DDdD', 'DdDD', 'DDDD', 'DDdD', 'DdDD', 'DDDD', 'DDdD', 'dDDD', 'DdsD', 'ssds', 'sdsD']);
  stamp(12, 20, ['DDDD', 'DDDD', 'dDDD', 'DDdD', 'DDDD', 'DDDD', 'DDdD', 'DDDD', 'DDdD', 'DsdD', 'sdsd', 'ssds']);

  // ================================================================ 左腿 4×12×4 @ (16,48)
  fill(16, 48, 16, 16, P.D);
  fill(20, 48, 4, 4, P.D);
  fill(24, 48, 4, 4, P.s);
  stamp(16, 52, ['DDDD', 'DdDD', 'DDdD', 'DDDD', 'DdDD', 'DDdD', 'DDDD', 'DdDD', 'DDDd', 'dsDD', 'sdDD', 'ssds']);
  stamp(20, 52, ['DDDD', 'dDDD', 'DDdD', 'DDDD', 'DdDD', 'DDdD', 'DDBD', 'DDDD', 'dDDd', 'dsdD', 'ssds', 'sdsd']);
  stamp(24, 52, ['DDDD', 'DDdD', 'DdDD', 'DDDD', 'DDdD', 'DdDD', 'DDDD', 'DDdD', 'dDDD', 'DdsD', 'ssds', 'sdsD']);
  stamp(28, 52, ['DDDD', 'DDDD', 'dDDD', 'DDdD', 'DDDD', 'DDDD', 'DDdD', 'DDDD', 'DDdD', 'DsdD', 'sdsd', 'ssds']);

  // ================================================================ 胸部补块 UV @ (0,32) / (12,32)
  // 盒子 2宽×3高×1深 ⇒ 展开 6宽×4高：
  //   第 1 行 (y+0)：[空 1] [top 2×1] [bottom 2×1] [空 1]
  //   第 2..4 行 (y+1..y+3)：[-x 面 1×3] [front 2×3] [+x 面 1×3] [back 2×3]
  // front 的 2×3 = 躯干正面 y=1..3 那三行：内侧那列最上一格是领口肤色，外侧那列最下一格
  // 是垂到胸前的发丝（对齐躯干正面 y=23 的 'h'），内侧列最下一格压暗当作两瓣之间的沟。
  function bust(u, mirrored) {
    var inner = mirrored ? u + 1 : u + 2, outer = mirrored ? u + 2 : u + 1;
    fill(u + 1, 32, 4, 1, P.D);        // 第 1 行：top 2×1 + bottom 2×1（两端各留 1px 空）
    fill(u, 33, 1, 3, P.D);            // -x 侧面
    fill(u + 3, 33, 1, 3, P.D);        // +x 侧面
    fill(u + 1, 33, 2, 3, P.D);        // front 打底
    fill(u + 4, 33, 2, 3, P.D);        // back（贴着躯干看不见，但不留透明洞）
    px(inner, 33, P.s);                // 领口肤色：只占最上一格，胸口其余仍是裙布
    px(inner, 35, P.d);                // 中缝侧的暗部，做出两瓣之间那道沟
    px(outer, 35, P.h);                // 垂到胸前的发丝
  }
  bust(0, false);    // 右胸（躯干 -x 侧）
  bust(12, true);    // 左胸（躯干 +x 侧；UV 独立，不靠 mirror，画法镜像）

  // ================================================================ 收尾：脏污 + 血渍
  grime(8, 8, 8, 8, 0.10, 14);      // 脸
  grime(0, 0, 32, 16, 0.08, 10);    // 头
  grime(16, 16, 24, 16, 0.11, 12);  // 躯干
  grime(40, 16, 16, 16, 0.09, 11);  // 右臂
  grime(32, 48, 16, 16, 0.09, 11);  // 左臂
  grime(0, 16, 16, 16, 0.10, 11);   // 右腿
  grime(16, 48, 16, 16, 0.10, 11);  // 左腿
  grime(0, 32, 18, 4, 0.12, 12);    // 胸部补块（(0,32) 右胸 6×4 + (12,32) 左胸 6×4）
  splatter(2, 34, 4, false);        // 胸前血渍（落在右胸正面）
  splatter(23, 30, 6, false);       // 裙摆血渍
  splatter(35, 29, 5, true);
  splatter(5, 30, 5, false);        // 裙腿交界血渍
  splatter(19, 30, 4, true);
  px(24, 21, P.b); px(25, 22, P.B); // 领口血珠

  if (tex.updateVersion) tex.updateVersion();

  // ================================================================ 写盘
  var fs = require('fs'), B = require('buffer').Buffer;
  // 直接取 canvas 的 PNG：不依赖 Blockbench 的 Texture.getDataURL()，无工程时照样落盘
  var dataUrl = cv.toDataURL('image/png');
  fs.writeFileSync(OUT, B.from(dataUrl.split(',')[1], 'base64'));
  var st = fs.statSync(OUT);
  return 'OK wrote ' + OUT + ' (' + st.size + ' bytes) tex=' + tex.width + 'x' + tex.height;
})();