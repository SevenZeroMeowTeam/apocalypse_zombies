'use strict';
/* 最小 PNG 解码器（只做资源自检用：8 位 RGB/RGBA、非隔行）。
 * 用途：核对 geo.json 里每个 cube 面的 UV 矩形是否落在真正涂绘过的像素上 ——
 * 贴在资源目录的那张图一旦被截断/过期，大量面会采到全透明区，游戏里渲染成纯黑
 * （M1 加兰德踩过：旧图只画到 V=237 而模型 UV 用到 V=322，1516/2076 个面全黑）。 */
const zlib = require('zlib');

function decodePNG(buf) {
  if (buf.readUInt32BE(0) !== 0x89504E47) throw new Error('不是 PNG');
  let off = 8, width = 0, height = 0, depth = 0, colorType = 0, interlace = 0;
  const idat = [];
  while (off < buf.length) {
    const len = buf.readUInt32BE(off);
    const type = buf.toString('ascii', off + 4, off + 8);
    const data = buf.subarray(off + 8, off + 8 + len);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0); height = data.readUInt32BE(4);
      depth = data[8]; colorType = data[9]; interlace = data[12];
    } else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    off += 12 + len;
  }
  if (depth !== 8) throw new Error(`bit depth ${depth} 不支持（自检只处理 8 位）`);
  if (interlace !== 0) throw new Error('不支持隔行 PNG');
  const channels = colorType === 6 ? 4 : colorType === 2 ? 3 : colorType === 0 ? 1 : 0;
  if (!channels) throw new Error(`color type ${colorType} 不支持`);

  const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = width * channels;
  const out = Buffer.alloc(stride * height);
  let prev = Buffer.alloc(stride);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    const line = raw.subarray(y * (stride + 1) + 1, y * (stride + 1) + 1 + stride);
    const cur = Buffer.alloc(stride);
    for (let i = 0; i < stride; i++) {
      const a = i >= channels ? cur[i - channels] : 0;
      const b = prev[i];
      const c = i >= channels ? prev[i - channels] : 0;
      let v = line[i];
      switch (filter) {
        case 0: break;
        case 1: v = v + a; break;
        case 2: v = v + b; break;
        case 3: v = v + ((a + b) >> 1); break;
        case 4: {
          const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
          v = v + (pa <= pb && pa <= pc ? a : pb <= pc ? b : c);
          break;
        }
        default: throw new Error(`未知 PNG filter ${filter}`);
      }
      cur[i] = v & 0xFF;
    }
    cur.copy(out, y * stride);
    prev = cur;
  }
  return { width, height, channels, data: out };
}

/** 取某像素的 alpha（RGB 图无 alpha 通道时视为 255）。 */
function alphaAt(img, x, y) {
  if (x < 0 || y < 0 || x >= img.width || y >= img.height) return 0;
  if (img.channels === 4) return img.data[(y * img.width + x) * 4 + 3];
  return 255;
}

module.exports = { decodePNG, alphaAt };
