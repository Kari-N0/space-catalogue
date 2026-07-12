#!/usr/bin/env node
// Vendors the brand fonts (BRAND.md §2: self-hosted OFL woff2, never the
// Google Fonts CDN) from @fontsource packages into src/styles/fonts/ so Vite
// hashes them and rewrites URLs under BASE_PATH. Re-run on font bumps.
//
//   node scripts/vendor-fonts.mjs        (from apps/web)

import { cpSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const appDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(join(appDir, "package.json"));
const out = join(appDir, "src/styles/fonts");
mkdirSync(out, { recursive: true });

const pkgDir = (name) => dirname(require.resolve(`${name}/package.json`));

const WANTED = [
  ["@fontsource/inter", "inter-latin-300-normal.woff2"],
  ["@fontsource/inter", "inter-latin-400-normal.woff2"],
  ["@fontsource/inter", "inter-latin-500-normal.woff2"],
  ["@fontsource/inter", "inter-latin-600-normal.woff2"],
  ["@fontsource/space-grotesk", "space-grotesk-latin-500-normal.woff2"],
];
for (const [pkg, file] of WANTED) cpSync(join(pkgDir(pkg), "files", file), join(out, file));
console.log(`vendored ${WANTED.length} font files -> ${out}`);
