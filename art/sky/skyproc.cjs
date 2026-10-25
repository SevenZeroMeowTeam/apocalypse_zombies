'use strict';
const fs = require('fs');
const path = require('path');
const { decodePNG, encodePNG } = require(path.join(__dirname, 'pngcodec.cjs'));
function centerCropSquare(img) {
  const w = img.width, h = img.height, rgba = img.rgba;
  if (w === h) return img;
  const s = Math.min(w, h), ox = (w - s) >> 1, oy = (h - s) >> 1;
  const out = Buffer.alloc(s * s * 4);
  for (let y = 0; y < s; y++) rgba.copy(out, y * s * 4, ((oy + y) * w + ox) * 4, ((oy + y) * w + ox + s) * 4);
  return { width: s, height: s, rgba: out };
}
function resizeBilinear(img, tw, th) {
  const sw = img.width, sh = img.height, rgba = img.rgba;
  if (sw === tw && sh === th) return img;
  const out = Buffer.alloc(tw * th * 4);
  for (let y = 0; y < th; y++) {
    const fy = ((y + 0.5) * sh) / th - 0.5;
    let y0 = Math.floor(fy), wy = fy - y0;
    if (y0 < 0) { y0 = 0; wy = 0; }
    if (y0 > sh - 2) { y0 = sh - 1; wy = 0; }
    const y1 = Math.min(sh - 1, y0 + 1);
    for (let x = 0; x < tw; x++) {
      const fx = ((x + 0.5) * sw) / tw - 0.5;
      let x0 = Math.floor(fx), wx = fx - x0;
      if (x0 < 0) { x0 = 0; wx = 0; }
      if (x0 > sw - 2) { x0 = sw - 1; wx = 0; }
      const x1 = Math.min(sw - 1, x0 + 1);
      const i00 = (y0 * sw + x0) * 4, i10 = (y0 * sw + x1) * 4, i01 = (y1 * sw + x0) * 4, i11 = (y1 * sw + x1) * 4;
      const o = (y * tw + x) * 4;
      for (let c = 0; c < 4; c++) {
        const v = rgba[i00 + c] * (1 - wx) * (1 - wy) + rgba[i10 + c] * wx * (1 - wy) + rgba[i01 + c] * (1 - wx) * wy + rgba[i11 + c] * wx * wy;
        out[o + c] = Math.round(Math.min(255, Math.max(0, v)));
      }
    }
  }
  return { width: tw, height: th, rgba: out };
}
function lum(r, g, b) { return Math.round(0.2126 * r + 0.7152 * g + 0.0722 * b); }
function sunAlpha(img) {
  const n = img.width * img.height, src = img.rgba, out = Buffer.alloc(n * 4);
  for (let i = 0; i < n; i++) {
    const r = src[i * 4], g = src[i * 4 + 1], b = src[i * 4 + 2];
    out[i * 4] = Math.max(0, Math.round((r - 10) * 255 / 245));
    out[i * 4 + 1] = Math.max(0, Math.round((g - 10) * 255 / 245));
    out[i * 4 + 2] = Math.max(0, Math.round((b - 10) * 255 / 245));
    out[i * 4 + 3] = lum(r, g, b);
  }
  return { width: img.width, height: img.height, rgba: out };
}
function cloudAlpha(img) {
  const n = img.width * img.height, src = img.rgba, out = Buffer.alloc(n * 4);
  for (let i = 0; i < n; i++) {
    out[i * 4] = out[i * 4 + 1] = out[i * 4 + 2] = 255;
    out[i * 4 + 3] = lum(src[i * 4], src[i * 4 + 1], src[i * 4 + 2]);
  }
  return { width: img.width, height: img.height, rgba: out };
}
function stretchAlpha(img) {
  const n = img.width * img.height, rgba = img.rgba;
  const hist = new Uint32Array(256);
  for (let i = 3; i < rgba.length; i += 4) hist[rgba[i]]++;
  let cum = 0, aLo = 0, aHi = 255;
  for (let v = 0; v < 256; v++) {
    cum += hist[v];
    if (aLo === 0 && cum >= n * 0.02) aLo = v;
    if (cum >= n * 0.98) { aHi = v; break; }
  }
  const scale = 255 / Math.max(1, aHi - aLo);
  const out = Buffer.alloc(n * 4);
  for (let i = 0; i < n; i++) {
    out[i * 4] = rgba[i * 4]; out[i * 4 + 1] = rgba[i * 4 + 1]; out[i * 4 + 2] = rgba[i * 4 + 2];
    out[i * 4 + 3] = Math.max(0, Math.min(255, Math.round((rgba[i * 4 + 3] - aLo) * scale)));
  }
  return { width: img.width, height: img.height, rgba: out };
}
function wrap4(img, F) {
  const W = img.width, H = img.height, rgba = img.rgba;
  const out = Buffer.alloc(W * H * 4);
  const sx = W >> 1, sy = H >> 1;
  const sm = t => { t = Math.max(0, Math.min(1, t)); return t * t * (3 - 2 * t); };
  for (let y = 0; y < H; y++) {
    const sY = sm(Math.min(y, H - 1 - y) / F);
    for (let x = 0; x < W; x++) {
      const sX = sm(Math.min(x, W - 1 - x) / F);
      const m = 1 - sX * sY;
      const o = (y * W + x) * 4;
      if (m <= 0) { out[o] = rgba[o]; out[o + 1] = rgba[o + 1]; out[o + 2] = rgba[o + 2]; out[o + 3] = rgba[o + 3]; continue; }
      const q = (((y + sy) % H) * W + ((x + sx) % W)) * 4;
      for (let c = 0; c < 4; c++) out[o + c] = Math.round(rgba[o + c] * (1 - m) + rgba[q + c] * m);
    }
  }
  return { width: W, height: H, rgba: out };
}
function proc(inFile, outFile, size, mode, doWrap) {
  let img = decodePNG(fs.readFileSync(path.join(__dirname, inFile)));
  img = centerCropSquare(img);
  img = resizeBilinear(img, size, size);
  img = mode === 'sun' ? sunAlpha(img) : cloudAlpha(img);
  if (mode === 'clouds') img = stretchAlpha(img);
  if (doWrap) img = wrap4(img, 64);
  const buf = encodePNG(img.rgba, img.width, img.height);
  fs.writeFileSync(path.join(__dirname, outFile), buf);
  const chk = decodePNG(fs.readFileSync(path.join(__dirname, outFile)));
  let amin = 255, amax = 0;
  for (let i = 3; i < chk.rgba.length; i += 4) { if (chk.rgba[i] < amin) amin = chk.rgba[i]; if (chk.rgba[i] > amax) amax = chk.rgba[i]; }
  return { out: outFile, w: chk.width, h: chk.height, bytes: buf.length, dimsOK: chk.width === size && chk.height === size, alphaMin: amin, alphaMax: amax };
}
console.log(JSON.stringify([
  proc('sun_base.png', 'sun_final.png', 512, 'sun', false),
  proc('clouds_base.png', 'clouds_final.png', 1024, 'clouds', true),
]));