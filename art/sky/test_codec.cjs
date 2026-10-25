'use strict';
const fs = require('fs');
const path = require('path');
const { decodePNG, encodePNG } = require(path.join(__dirname, 'pngcodec.cjs'));
function rt(file) {
  const a = decodePNG(fs.readFileSync(file));
  const b = decodePNG(encodePNG(a.rgba, a.width, a.height));
  let diff = 0;
  for (let i = 0; i < a.rgba.length; i++) if (a.rgba[i] !== b.rgba[i]) diff++;
  return { file: path.basename(file), w: a.width, h: a.height, ct: a.ihdr.colorType, roundTrip: diff === 0 ? 'PASS' : 'FAIL diffs=' + diff };
}
const R = path.join(__dirname, '..', '..');
console.log(JSON.stringify([
  rt(path.join(R, 'src/main/resources/assets/apocalypse_zombies/textures/environment/earth.png')),
  rt(path.join(__dirname, 'moon_base.png')),
]));