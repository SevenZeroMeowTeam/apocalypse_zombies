'use strict';
const fs = require('fs');
const path = require('path');
const { decodePNG, encodePNG } = require(path.join(__dirname, 'pngcodec.cjs'));
function main(args) {
  const SRC = args[0] || path.join(__dirname, 'moon_base.png');
  const OUT = path.join(__dirname, '..', '..', 'src', 'main', 'resources', 'assets', 'minecraft', 'textures', 'environment', 'moon_phases.png');
  const CELL = 512, W = 2048, H = 1024, R = CELL / 2;
  const dec = decodePNG(fs.readFileSync(SRC));
  const sw = dec.width, sh = dec.height, src = dec.rgba;
  const np = sw * sh;
  const bx = [], by = [];
  for (let i = 0, p = 0; i < np; i++, p += 4) {
    const L = 0.2126 * src[p] + 0.7152 * src[p + 1] + 0.0722 * src[p + 2];
    if (L > 50) { bx.push(i % sw); by.push((i / sw) | 0); }
  }
  if (bx.length < 1000) throw new Error('moon not detected: only ' + bx.length + ' bright px of ' + np);
  const sx2 = bx.slice().sort((a, b) => a - b);
  const sy2 = by.slice().sort((a, b) => a - b);
  const q = (arr, f) => arr[Math.min(arr.length - 1, Math.max(0, Math.floor(f * arr.length)))];
  const medx = q(sx2, 0.5), medy = q(sy2, 0.5);
  const maxR = Math.floor(Math.hypot(Math.max(medx, sw - 1 - medx), Math.max(medy, sh - 1 - medy))) + 1;
  const binW = 2;
  const nBins = Math.ceil(maxR / binW) + 2;
  const bins = new Float64Array(nBins);
  const dists = new Float64Array(bx.length);
  for (let i = 0; i < bx.length; i++) {
    const d = Math.hypot(bx[i] - medx, by[i] - medy);
    dists[i] = d;
    bins[Math.min(nBins - 1, (d / binW) | 0)]++;
  }
  const densities = new Float64Array(nBins);
  for (let b = 0; b < nBins; b++) {
    const r0 = b * binW, r1 = r0 + binW;
    densities[b] = bins[b] / Math.max(1, Math.PI * (r1 * r1 - r0 * r0));
  }
  let lastSeen = 10;
  for (let b = 1; b < nBins; b++) {
    if (densities[b] >= 0.3) lastSeen = b;
    else if ((b - lastSeen) * binW > 60) break;
  }
  const Rsrc = (lastSeen + 1) * binW;
  if (Rsrc < 100) throw new Error('detected disc too small: Rsrc=' + Rsrc);
  const t = Math.max(0, Math.floor(bx.length * 0.002));
  const bboxPct = [sx2[t], sy2[t], sx2[sx2.length - 1 - t], sy2[sy2.length - 1 - t]];
  const pctDiag = ((sx2[sx2.length - 1 - t] - sx2[t]) + (sy2[sy2.length - 1 - t] - sy2[t])) / 2 / (2 * Rsrc);
  let beyondCount = 0;
  for (let i = 0; i < bx.length; i++) if (dists[i] > Rsrc + 10) beyondCount++;
  const cornerLuma = [2, sw - 3].flatMap((cx) => [2, sh - 3].map((cy) => src[(cy * sw + cx) * 4]));
  const diag = {
    src: sw + 'x' + sh, brightPx: bx.length, center: [medx, medy], Rsrc: Rsrc,
    discFills: +(Rsrc / (Math.min(sw, sh) / 2)).toFixed(3),
    bboxPctile: bboxPct, pctOverRadial: +pctDiag.toFixed(3),
    brightBeyondRplus10: beyondCount, cornerLuma: cornerLuma,
  };
  const bcx = medx, bcy = medy;
  const scale = CELL / (2 * Rsrc);
  const out = Buffer.alloc(W * H * 4);
  const expected = [1, 0.8536, 0.5, 0.1464, 0, 0.1464, 0.5, 0.8536];
  const stats = [];
  for (let k = 0; k < 8; k++) {
    const row = (k / 4) | 0, col = k % 4;
    const ox = col * CELL, oy = row * CELL;
    const cosA = Math.cos((k * Math.PI) / 4);
    let litAcc = 0, discAcc = 0;
    for (let py = 0; py < CELL; py++) {
      const dy = py + 0.5 - R;
      const s = Math.sqrt(Math.max(0, R * R - dy * dy));
      const tx = cosA * s;
      for (let px = 0; px < CELL; px++) {
        const dx = px + 0.5 - R;
        const r = Math.sqrt(dx * dx + dy * dy);
        const cov = R + 0.5 - r;
        if (cov <= 0) continue;
        discAcc += Math.min(1, cov);
        let pcov = 0;
        if (k === 0) pcov = 1;
        else if (k <= 3) pcov = tx - dx;
        else if (k >= 5) pcov = dx + tx;
        if (pcov <= 0) continue;
        if (pcov > 1) pcov = 1;
        const sxp = bcx + dx / scale, syp = bcy + dy / scale;
        const cx = sxp < 0 ? 0 : sxp > sw - 1.001 ? sw - 1.001 : sxp;
        const cy = syp < 0 ? 0 : syp > sh - 1.001 ? sh - 1.001 : syp;
        const xi = cx | 0, yi = cy | 0;
        const fx = cx - xi, fy = cy - yi;
        const i00 = (yi * sw + xi) * 4;
        const ro = sw * 4;
        const w00 = (1 - fx) * (1 - fy), w10 = fx * (1 - fy), w01 = (1 - fx) * fy, w11 = fx * fy;
        const sr = src[i00] * w00 + src[i00 + 4] * w10 + src[i00 + ro] * w01 + src[i00 + ro + 4] * w11;
        const sg = src[i00 + 1] * w00 + src[i00 + 5] * w10 + src[i00 + ro + 1] * w01 + src[i00 + ro + 5] * w11;
        const sb = src[i00 + 2] * w00 + src[i00 + 6] * w10 + src[i00 + ro + 2] * w01 + src[i00 + ro + 6] * w11;
        const L = 0.2126 * sr + 0.7152 * sg + 0.0722 * sb;
        const aLimb = r <= 246 ? 1 : Math.min(1, Math.max(0, (L - 8) / 36));
        const alpha = Math.round(255 * aLimb * Math.min(1, cov) * pcov);
        if (alpha <= 0) continue;
        const o = ((oy + py) * W + (ox + px)) * 4;
        out[o] = sr; out[o + 1] = sg; out[o + 2] = sb; out[o + 3] = alpha;
        litAcc += alpha / 255;
      }
    }
    const frac = discAcc > 0 ? litAcc / discAcc : 0;
    stats.push({ cell: k, litFracOfDisc: +frac.toFixed(3), expected: expected[k] });
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  const png = encodePNG(out, W, H);
  fs.writeFileSync(OUT, png);
  const check = decodePNG(fs.readFileSync(OUT));
  diag.out = { bytes: png.length, w: check.width, h: check.height, colorType: check.ihdr.colorType, bitDepth: check.ihdr.bitDepth };
  const ok = stats.every((s) => Math.abs(s.litFracOfDisc - s.expected) < 0.03);
  console.log(JSON.stringify({ diag: diag, stats: stats, fractionCheck: ok ? 'OK' : 'DEVIATION' }));
  if (!ok) process.exit(2);
}
if (require.main === module) main(process.argv.slice(2));
module.exports = { main };
