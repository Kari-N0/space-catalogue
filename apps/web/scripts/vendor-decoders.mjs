#!/usr/bin/env node
// Vendors Babylon's KTX2/meshopt decoder assets into public/vendor/babylon/ so
// the inspect path never touches a CDN (plan Part B; self-containment rule).
// Re-run after bumping @babylonjs/ktx2decoder or meshoptimizer.
//
//   node scripts/vendor-decoders.mjs        (from apps/web)
//
// The classic-worker bundles are built locally with esbuild (vite's own dep):
//  - babylon.ktx2Decoder.js  -> global KTX2DECODER   (Babylon worker contract)
//  - meshopt_decoder.js      -> global MeshoptDecoder

import { build } from "esbuild";
import { cpSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const appDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(join(appDir, "package.json"));
const ktx2Dir = dirname(require.resolve("@babylonjs/ktx2decoder")); // hoisted by the npm workspace
const out = join(appDir, "public/vendor/babylon");
mkdirSync(out, { recursive: true });

const wasmDir = join(ktx2Dir, "wasm");
const WASMS = [
  "zstddec.wasm",
  "msc_basis_transcoder.wasm",
  "uastc_astc.wasm",
  "uastc_bc7.wasm",
  "uastc_rgba8_unorm_v2.wasm",
  "uastc_rgba8_srgb_v2.wasm",
  "uastc_r8_unorm.wasm",
  "uastc_rg8_unorm.wasm",
];
for (const f of WASMS) cpSync(join(wasmDir, f), join(out, f));

// msc_basis_transcoder.js companion (classic script shipped alongside the wasm)
cpSync(join(wasmDir, "msc_basis_transcoder.js"), join(out, "msc_basis_transcoder.js"));

await build({
  entryPoints: [join(ktx2Dir, "index.js")],
  bundle: true,
  minify: true,
  format: "iife",
  globalName: "KTX2DECODER",
  outfile: join(out, "babylon.ktx2Decoder.js"),
});

const meshoptEntry = join(out, ".meshopt-entry.mjs");
writeFileSync(meshoptEntry, 'import { MeshoptDecoder } from "meshoptimizer";\nglobalThis.MeshoptDecoder = MeshoptDecoder;\n');
await build({
  entryPoints: [meshoptEntry],
  bundle: true,
  minify: true,
  format: "iife",
  outfile: join(out, "meshopt_decoder.js"),
});
rmSync(meshoptEntry);

console.log(`vendored decoders -> ${out}`);
