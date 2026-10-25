'use strict';
const fs = require('fs');
const path = require('path');
const { decodePNG, encodePNG } = require(path.join(__dirname, 'pngcodec.cjs'));
function main(args) {
  const src = args[0] || 'src/main/resources/assets/apocalypse_zombies/textures/environment/earth.png';
  const a = decodePNG(fs.readFileSync(src));
  const enc = encodePNG(a.rgba, a.width, a.height);
  const tmp = path.join(__dirname, 'roundtrip_tmp.png');
  fs.writeFileSync(tmp, enc);
  const b = decodePNG(fs.readFileSync(tmp));
  if (a.width !== b.width || a.height !== b.height) throw new Error('dimension mismatch after roundtrip');
  const n = a.width * a.height * 4;
  let diff = -1;
  for (let i = 0; i < n; i++) { if (a.rgba[i] !== b.rgba[i]) { diff = i; break; } }
  console.log(JSON.stringify({ sample: src, ihdr: a.ihdr, encodedBytes: enc.length, pixelEqual: diff < 0, firstDiffIndex: diff }));
  if (diff >= 0) process.exit(1);
}
if (require.main === module) main(process.argv.slice(2));
module.exports = { main };
