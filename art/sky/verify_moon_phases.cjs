'use strict';
const fs = require('fs');
const path = require('path');
const { decodePNG } = require(path.join(__dirname, 'pngcodec.cjs'));
function main() {
  const p = path.join(__dirname, '..', '..', 'src', 'main', 'resources', 'assets', 'minecraft', 'textures', 'environment', 'moon_phases.png');
  const dec = decodePNG(fs.readFileSync(p));
  const width = dec.width, height = dec.height, rgba = dec.rgba;
  if (width !== 2048 || height !== 1024) throw new Error('bad dims ' + width + 'x' + height);
  const CELL = 512;
  const rows = [];
  for (let k = 0; k < 8; k++) {
    const ox = (k % 4) * CELL, oy = ((k / 4) | 0) * CELL;
    let mass = 0, cx = 0, cy = 0, maxA = 0, L = 0, Rt = 0;
    for (let py = 0; py < CELL; py++) {
      const rowBase = (oy + py) * width + ox;
      for (let px = 0; px < CELL; px++) {
        const a = rgba[(rowBase + px) * 4 + 3];
        if (!a) continue;
        mass += a; cx += a * (px + 0.5); cy += a * (py + 0.5);
        if (maxA < a) maxA = a;
        if (px < 256) L += a; else Rt += a;
      }
    }
    rows.push({
      cell: k,
      litSideLR: Rt < 1 ? 'L>>R' : (L < 1 ? 'R>>L' : +(L / Rt).toFixed(2)),
      centroidX: mass ? +(cx / mass).toFixed(1) : null,
      centroidY: mass ? +(cy / mass).toFixed(1) : null,
      maxAlpha: maxA,
      coverPct: +((mass / (255 * CELL * CELL)) * 100).toFixed(1),
    });
  }
  console.log(JSON.stringify(rows));
}
if (require.main === module) main();
module.exports = { main };
