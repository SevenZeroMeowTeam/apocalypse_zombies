'use strict';
const fs = require('fs');
const { decodePNG, encodePNG } = require('./pngcodec.cjs');

function lum(d, i) { return 0.299*d[i] + 0.587*d[i+1] + 0.114*d[i+2]; }

// ---------- sun: force alpha=255 (additive blending, black=invisible), stats ----------
{
  const img = decodePNG(fs.readFileSync('../../dsh-image-gen/image-0bd61532.png'));
  const { width: W, height: H, rgba } = img;
  for (let i = 3; i < rgba.length; i += 4) rgba[i] = 255;
  fs.writeFileSync('../../src/main/resources/assets/minecraft/textures/environment/sun.png', encodePNG(rgba, W, H));
  // stats: center luminance, corner luminance, disc radius estimate along axes
  const c = ((H/2|0)*W + (W/2|0)) * 4;
  const corner = lum(rgba, 0) ;
  let rSum = 0;
  for (let r = 0; r < W/2; r++) {
    const x = (W/2|0) + r;
    if (lum(rgba, ((H/2|0)*W + x)*4) > 24) rSum = r;
  }
  console.log('sun: ' + W + 'x' + H + ' centerLum=' + lum(rgba, c).toFixed(0) + ' cornerLum=' + corner.toFixed(0) + ' brightRadiusX=' + rSum);
}

// ---------- clouds: photo -> alpha density map -> offset+crossfade tileable ----------
{
  const img = decodePNG(fs.readFileSync('../../dsh-image-gen/image-a516f86e.png'));
  const { width: W, height: H } = img;
  const d = img.rgba;
  // luminance histogram for adaptive thresholds
  const hist = new Array(256).fill(0);
  for (let i = 0; i < W*H; i++) hist[Math.min(255, lum(d, i*4) | 0)]++;
  let acc = 0, t0 = 100, t1 = 190;
  const p30 = W*H*0.52, p75 = W*H*0.84;
  for (let v = 0; v < 256; v++) { acc += hist[v]; if (acc >= p30) { t0 = v; break; } }
  acc = 0;
  for (let v = 0; v < 256; v++) { acc += hist[v]; if (acc >= p75) { t1 = v; break; } }
  if (t1 - t0 < 24) t1 = t0 + 24;
  // density map
  const out = Buffer.alloc(W*H*4);
  for (let i = 0; i < W*H; i++) {
    const L = lum(d, i*4);
    let a = (L - t0) / (t1 - t0);
    a = a < 0 ? 0 : a > 1 ? 1 : a;
    a = a*a*(3-2*a);                      // smoothstep
    out[i*4+3] = Math.round(a*255);
    const shade = 205 + 47 * a;           // denser cloud = brighter white
    out[i*4] = out[i*4+1] = out[i*4+2] = Math.round(shade);
  }
  // torus shift by (W/2, H/2): outer boundary then joins naturally-adjacent content
  const sh = Buffer.alloc(W*H*4);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const s = ((x + (W>>1)) % W) + ((y + (H>>1)) % H) * W;
    sh[(y*W+x)*4] = out[s*4]; sh[(y*W+x)*4+1] = out[s*4+1]; sh[(y*W+x)*4+2] = out[s*4+2]; sh[(y*W+x)*4+3] = out[s*4+3];
  }
  // crossfade band across the (now central) old seams
  const m = 96;
  const res = Buffer.from(sh);
  // horizontal band centered at x = W/2
  for (let y = 0; y < H; y++) for (let k = 0; k < m; k++) {
    const x = ((W>>1) - (m>>1) + k + W) % W;
    const t = (k + 0.5) / m;
    const p = (x + (W>>1)) % W;           // other side of the original seam
    for (let c = 0; c < 4; c++) res[(y*W+x)*4+c] = Math.round(sh[(y*W+x)*4+c]*(1-t) + sh[(y*W+p)*4+c]*t);
  }
  // vertical band centered at y = H/2
  for (let x = 0; x < W; x++) for (let k = 0; k < m; k++) {
    const y = ((H>>1) - (m>>1) + k + H) % H;
    const t = (k + 0.5) / m;
    const p = (y + (H>>1)) % H;
    for (let c = 0; c < 4; c++) res[(y*W+x)*4+c] = Math.round(res[(y*W+x)*4+c]*(1-t) + res[(p*W+x)*4+c]*t);
  }
  fs.writeFileSync('../../src/main/resources/assets/minecraft/textures/environment/clouds.png', encodePNG(res, W, H));
  let vis = 0; for (let i = 3; i < W*H*4; i += 4) if (res[i] > 8) vis++;
  console.log('clouds: ' + W + 'x' + H + ' t0=' + t0 + ' t1=' + t1 + ' visible=' + (100*vis/(W*H)).toFixed(1) + '%');
}
console.log('done');