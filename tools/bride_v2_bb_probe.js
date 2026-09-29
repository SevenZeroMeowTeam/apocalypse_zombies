(function () {
  var fs = require('fs');
  var out = { stamp: 'probe-1' };
  try { out.version = Blockbench.version; } catch (e) { out.e1 = String(e); }
  try { out.visibility = document.visibilityState; out.focus = document.hasFocus(); } catch (e) { }
  out.requireType = typeof require;
  try {
    out.formatsAll = (Formats.all || []).map(function (f) { return f.id; });
  } catch (e) { out.e2 = String(e); }
  try {
    out.formatsKeys = Object.keys(Formats).slice(0, 30);
  } catch (e) { out.e3 = String(e); }
  try {
    out.codecs = (Codecs || []).map(function (c) { return c.id; }).filter(Boolean).slice(0, 40);
  } catch (e) { out.e4 = String(e); }
  try {
    out.projectOpen = !!Project;
    out.projectName = Project ? Project.name : null;
    out.projectFormat = Project && Project.format ? Project.format.id : null;
    out.elements = Project ? (Project.elements ? Project.elements.length : -1) : null;
  } catch (e) { out.e5 = String(e); }
  try {
    out.bedrockCodec = !!(Codecs.bedrock && Codecs.bedrock.parse && Codecs.bedrock.compile);
  } catch (e) { out.e6 = String(e); }
  fs.writeFileSync('F:/mcmod/art/bride/_bb_probe.json', JSON.stringify(out, null, 1));
  return out;
})()