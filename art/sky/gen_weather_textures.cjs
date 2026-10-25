#!/usr/bin/env node
/**
 * gen_weather_textures.cjs - procedural weather overlays (no AI image gen).
 * Writes vanilla-namespace environment overrides:
 *   rain.png / snow.png  128x128 RGBA, vertically tileable (8px crossfade).
 * Deterministic (fixed seeds). Pure Node + zlib, hand-rolled PNG encoder.
 * Run: node art/sky/gen_weather_textures.cjs
 */
'use strict';
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const W = 128, H = 128, BAND = 8;
const STRIP_H = H + BAND; // render strip: rows 128..135 wrap-blend into rows 0..7

// ---- PNG encoder (RGBA8, filter 0 per row, zlib deflate) ----
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    t[n] = c >>> 0;
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
  out.write(type, 4, 'latin1');
  data.copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
}
function encodePNG(rgba, w, h) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8;  // bit depth
  ihdr[9] = 6;  // color type: RGBA
  const stride = w * 4;
  const raw = Buffer.alloc((stride + 1) * h);
  for (let y = 0; y < h; y++) {
    raw[y * (stride + 1)] = 0; // filter 0
    rgba.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride);
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

// ---- helpers ----
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function newStrip() {
  return {
    a: new Float32Array(W * STRIP_H),
    r: new Uint8Array(W * STRIP_H),
    g: new Uint8Array(W * STRIP_H),
    b: new Uint8Array(W * STRIP_H),
  };
}
function put(s, x, y, a, r, g, b, cap) {
  if (y < 0 || y >= STRIP_H || a <= 0) return;
  x = ((x % W) + W) % W;
  const i = y * W + x;
  s.a[i] = Math.min(cap, s.a[i] + a);
  s.r[i] = r; s.g[i] = g; s.b[i] = b;
}
function stripToRGBA(s) {
  const out = Buffer.alloc(W * H * 4);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = y * W + x;
      let a = s.a[i], r = s.r[i], g = s.g[i], b = s.b[i];
      if (y < BAND) { // vertical wrap: blend top band with strip rows 128..135
        const w = y / BAND;
        const i2 = (H + y) * W + x;
        const a2 = s.a[i2];
        if (a2 * (1 - w) > a * w) { r = s.r[i2]; g = s.g[i2]; b = s.b[i2]; }
        a = a * w + a2 * (1 - w);
      }
      const o = (y * W + x) * 4;
      out[o] = r; out[o + 1] = g; out[o + 2] = b;
      out[o + 3] = Math.round(Math.min(1, a) * 255);
    }
  }
  return out;
}

// ---- rain.png: thin vertical streaks ----
function genRain() {
  const rnd = mulberry32(0x51EC1);
  const s = newStrip();
  const CAP = 0.9, COUNT = 55;
  for (let k = 0; k < COUNT; k++) {
    const len = 20 + Math.floor(rnd() * 51);              // 20..70 px
    const width = rnd() < 0.72 ? 1 : 2;                   // 1 or 2 px
    const drift = (1 + rnd()) * (rnd() < 0.5 ? 1 : -1);   // +/-1..2 px total
    const base = 0.15 + rnd() * 0.35;                     // alpha 0.15..0.5
    const tint = 205 + Math.floor(rnd() * 36);            // cool white
    const r = tint, g = Math.min(255, tint + 6), b = 255;
    const x0 = rnd() * W, y0 = rnd() * STRIP_H;
    const head = 0.18 + rnd() * 0.12, tail = 0.18 + rnd() * 0.15;
    for (let j = 0; j < len; j++) {
      const t = len > 1 ? j / (len - 1) : 0;
      let env = 1;
      if (t < head) env = t / head;
      if (t > 1 - tail) env = Math.min(env, (1 - t) / tail);
      env = 0.2 + 0.8 * env; // tapered ends
      const y = Math.round(y0 + j);
      const xc = x0 + drift * t;
      const xi = Math.floor(xc - (width - 1) / 2);
      const fx = xc - (width - 1) / 2 - xi;
      put(s, xi, y, base * env * (1 - fx), r, g, b, CAP);
      put(s, xi + 1, y, base * env, r, g, b, CAP);
      if (width === 2) put(s, xi + 2, y, base * env * fx, r, g, b, CAP);
    }
  }
  return { rgba: stripToRGBA(s), info: 'streaks=' + COUNT };
}

// ---- snow.png: soft-focus flakes ----
function genSnow() {
  const rnd = mulberry32(4242);
  const s = newStrip();
  const CAP = 0.85;
  const want = 8 + Math.floor(rnd() * 7); // 8..14
  const cells = [];
  for (let i = 0; i < 16; i++) cells.push(i);
  for (let i = cells.length - 1; i > 0; i--) { // Fisher-Yates
    const j = Math.floor(rnd() * (i + 1));
    const t = cells[i]; cells[i] = cells[j]; cells[j] = t;
  }
  const placed = [];
  let used = 0;
  for (let k = 0; k < want; k++) {
    const cell = cells[k];
    const ox = (cell % 4) * 32, oy = Math.floor(cell / 4) * 32;
    let cx = 0, cy = 0, rad = 0, ok = false;
    for (let t = 0; t < 24 && !ok; t++) {
      cx = ox + 7 + rnd() * 18;
      cy = oy + 7 + rnd() * 18;
      rad = 3 + rnd() * 8; // diameter 6..22
      ok = placed.every(p => Math.hypot(p.x - cx, p.y - cy) >= (p.r + rad) * 0.8);
    }
    if (!ok) continue; // keep spacing, avoid clumps
    placed.push({ x: cx, y: cy, r: rad });
    used++;
    const xi = Math.round(cx), yi = Math.round(cy);
    const shade = 245 + Math.floor(rnd() * 11);
    const R = Math.ceil(rad);
    for (let dy = -R; dy <= R; dy++) {
      for (let dx = -R; dx <= R; dx++) {
        const d = Math.hypot(dx, dy);
        if (d > rad) continue;
        const a = 0.55 * Math.pow(1 - d / rad, 1.4); // center 0.55 -> edge 0
        put(s, xi + dx, yi + dy, a, shade, shade, 255, CAP);
      }
    }
  }
  return { rgba: stripToRGBA(s), info: 'flakes=' + used + '/' + want };
}

// ---- main ----
function main() {
  const outDir = path.resolve(__dirname, '..', '..', 'src', 'main', 'resources',
    'assets', 'minecraft', 'textures', 'environment');
  fs.mkdirSync(outDir, { recursive: true });
  for (const [name, gen] of [['rain.png', genRain], ['snow.png', genSnow]]) {
    const { rgba, info } = gen();
    const file = path.join(outDir, name);
    fs.writeFileSync(file, encodePNG(rgba, W, H));
    const chk = fs.readFileSync(file);
    const w = chk.readUInt32BE(16), h = chk.readUInt32BE(20);
    let cov = 0;
    for (let i = 3; i < rgba.length; i += 4) if (rgba[i] > 5) cov++;
    console.log(name + ': ' + w + 'x' + h + ' colortype=' + chk[25] +
      ' bitdepth=' + chk[24] + ' bytes=' + chk.length +
      ' visiblePx=' + (100 * cov / (W * H)).toFixed(1) + '% | ' + info);
  }
  console.log('outDir=' + outDir);
}
main();
