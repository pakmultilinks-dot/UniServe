/** Rasterize the existing UniServe SVG mark; never use reference screenshots as branding.
 * Requires sharp (or UNISERVE_SHARP_MODULE pointing to an isolated installation).
 * Run from any directory: node apps/mobile/make_icon.cjs
 */
const sharp = require(process.env.UNISERVE_SHARP_MODULE || "sharp");
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "../..");
const mark = fs.readFileSync(path.join(root, "apps/web/src/app/icon.svg"));
const bg = { r: 246, g: 239, b: 223, alpha: 1 };
async function icon(name, fraction, background) {
  const size = Math.round(1024 * fraction);
  const glyph = await sharp(mark).resize(size,size).png().toBuffer();
  await sharp({ create: { width:1024,height:1024,channels:4,background } })
    .composite([{input:glyph,gravity:"centre"}]).png()
    .toFile(path.join(__dirname,"assets",name));
}
(async () => {
  await icon("icon.png",0.88,bg);
  await icon("adaptive-icon.png",0.62,{r:0,g:0,b:0,alpha:0});
  await icon("splash-icon.png",0.55,{r:0,g:0,b:0,alpha:0});
  const logo = await sharp(mark).resize(512,512).flatten({background:bg}).jpeg({quality:95}).toBuffer();
  fs.writeFileSync(path.join(__dirname,"assets/lgu-logo.jpg"),logo);
  fs.writeFileSync(path.join(root,"apps/web/public/lgu-logo.jpg"),logo);
  console.log("Existing UniServe mark rendered for icon, splash and app/web logo assets.");
})().catch((error)=>{console.error(error);process.exitCode=1;});
