'use strict';
const zlib = require('zlib');
const CRC_TABLE = (() => {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    t[n] = c;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}
function chunk(type, data) {
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0);
  out.write(type, 4, 'ascii');
  data.copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
}
const PNG_SIG = Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]);
function decodePNG(fileBuf) {
  if (!fileBuf.subarray(0, 8).equals(PNG_SIG)) throw new Error('bad PNG signature');
  let off = 8, ihdr = null, plte = null, trns = null;
  const idat = [];
  while (off + 8 <= fileBuf.length) {
    const len = fileBuf.readUInt32BE(off);
    const type = fileBuf.toString('ascii', off + 4, off + 8);
    const data = fileBuf.subarray(off + 8, off + 8 + len);
    if (type === 'IHDR') {
      ihdr = { width: data.readUInt32BE(0), height: data.readUInt32BE(4), bitDepth: data[8], colorType: data[9], compression: data[10], filter: data[11], interlace: data[12] };
    } else if (type === 'PLTE') plte = Buffer.from(data);
    else if (type === 'tRNS') trns = Buffer.from(data);
    else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    off += 12 + len;
  }
  if (!ihdr) throw new Error('IHDR missing');
  const width = ihdr.width, height = ihdr.height;
  if (ihdr.bitDepth !== 8) throw new Error('unsupported bitDepth ' + ihdr.bitDepth);
  const channels = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 }[ihdr.colorType];
  if (!channels) throw new Error('unsupported colorType ' + ihdr.colorType);
  if (ihdr.interlace !== 0) throw new Error('unsupported interlace ' + ihdr.interlace);
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const stride = width * channels;
  if (raw.length < (stride + 1) * height) throw new Error('IDAT too short');
  const out = Buffer.alloc(stride * height);
  let pos = 0;
  for (let y = 0; y < height; y++) {
    const ft = raw[pos++];
    const dst = out.subarray(y * stride, (y + 1) * stride);
    const prev = y > 0 ? out.subarray((y - 1) * stride, y * stride) : null;
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? dst[x - channels] : 0;
      const b = prev ? prev[x] : 0;
      const c = prev && x >= channels ? prev[x - channels] : 0;
      let v = raw[pos + x];
      if (ft === 1) v = (v + a) & 255;
      else if (ft === 2) v = (v + b) & 255;
      else if (ft === 3) v = (v + ((a + b) >> 1)) & 255;
      else if (ft === 4) {
        const p = (a + b - c) | 0;
        const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
        v = (v + (pa <= pb && pa <= pc ? a : pb <= pc ? b : c)) & 255;
      } else if (ft !== 0) throw new Error('bad filter type ' + ft);
      dst[x] = v;
    }
    pos += stride;
  }
  const rgba = Buffer.alloc(width * height * 4);
  const npx = width * height;
  if (ihdr.colorType === 6) out.copy(rgba);
  else if (ihdr.colorType === 2) for (let i = 0; i < npx; i++) { rgba[i*4] = out[i*3]; rgba[i*4+1] = out[i*3+1]; rgba[i*4+2] = out[i*3+2]; rgba[i*4+3] = 255; }
  else if (ihdr.colorType === 0) for (let i = 0; i < npx; i++) { const g = out[i]; rgba[i*4] = g; rgba[i*4+1] = g; rgba[i*4+2] = g; rgba[i*4+3] = 255; }
  else if (ihdr.colorType === 4) for (let i = 0; i < npx; i++) { const g = out[i*2]; rgba[i*4] = g; rgba[i*4+1] = g; rgba[i*4+2] = g; rgba[i*4+3] = out[i*2+1]; }
  else if (ihdr.colorType === 3) {
    if (!plte) throw new Error('PLTE missing');
    for (let i = 0; i < npx; i++) {
      const idx = out[i];
      rgba[i*4] = plte[idx*3]; rgba[i*4+1] = plte[idx*3+1]; rgba[i*4+2] = plte[idx*3+2];
      rgba[i*4+3] = trns && idx < trns.length ? trns[idx] : 255;
    }
  }
  return { width, height, rgba, ihdr };
}
function encodePNG(rgba, width, height) {
  const stride = width * 4;
  const fbufs = [0,1,2,3,4].map(() => Buffer.alloc(stride));
  const filtered = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y++) {
    const row = rgba.subarray(y * stride, (y + 1) * stride);
    const prev = y > 0 ? rgba.subarray((y - 1) * stride, y * stride) : null;
    let bestFt = 0, bestScore = Infinity;
    for (let ft = 0; ft < 5; ft++) {
      const fb = fbufs[ft];
      let score = 0;
      for (let x = 0; x < stride; x++) {
        const cur = row[x];
        const a = x >= 4 ? row[x - 4] : 0;
        const b = prev ? prev[x] : 0;
        const c = prev && x >= 4 ? prev[x - 4] : 0;
        let v;
        if (ft === 0) v = cur;
        else if (ft === 1) v = cur - a;
        else if (ft === 2) v = cur - b;
        else if (ft === 3) v = cur - ((a + b) >> 1);
        else {
          const p = (a + b - c) | 0;
          const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
          v = cur - (pa <= pb && pa <= pc ? a : pb <= pc ? b : c);
        }
        v &= 255;
        fb[x] = v;
        score += v < 128 ? v : 256 - v;
      }
      if (score < bestScore) { bestScore = score; bestFt = ft; }
    }
    filtered[y * (stride + 1)] = bestFt;
    fbufs[bestFt].copy(filtered, y * (stride + 1) + 1);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  const idat = zlib.deflateSync(filtered, { level: 9 });
  return Buffer.concat([PNG_SIG, chunk('IHDR', ihdr), chunk('IDAT', idat), chunk('IEND', Buffer.alloc(0))]);
}
module.exports = { decodePNG, encodePNG };
