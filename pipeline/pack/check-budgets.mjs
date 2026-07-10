#!/usr/bin/env node
// Budget checker (PLAN.md §6) — fails the build when an output exceeds budget.
//
//   node pipeline/pack/check-budgets.mjs [--dist apps/web/dist]
//
// Checks:
//   1. Initial route: gzipped index.html + every non-lazy JS/CSS chunk it
//      references (script/link tags) must fit initial_route_gz_bytes.
//   2. Engine chunk: any lazy chunk matching /babylon/i must fit
//      engine_chunk_gz_bytes.
//   3. Shipped assets: *.sog and *.glb under dist, tiered by filename suffix
//      (-m = mobile, -d = desktop; untiered files must fit the mobile budget).
//
// Budgets live in budgets.json next to this script. Never raise a budget to
// make a task pass (CLAUDE.md hard rule).

import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const here = dirname(fileURLToPath(import.meta.url));
const budgets = JSON.parse(readFileSync(join(here, "budgets.json"), "utf8"));

const distFlag = process.argv.indexOf("--dist");
const dist = resolve(
  distFlag !== -1 ? process.argv[distFlag + 1] : join(here, "../../apps/web/dist"),
);

const gz = (path) => gzipSync(readFileSync(path), { level: 9 }).length;
const kb = (bytes) => `${(bytes / 1024).toFixed(1)} KB`;

function* walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(path);
    else yield path;
  }
}

let failed = false;
const report = (ok, label, actual, budget) => {
  const mark = ok ? "ok  " : "FAIL";
  console.log(`${mark}  ${label}: ${kb(actual)} (budget ${kb(budget)})`);
  if (!ok) failed = true;
};

// --- 1. initial route -------------------------------------------------------
const indexPath = join(dist, "index.html");
let stat;
try {
  stat = statSync(indexPath);
} catch {
  console.error(`error: ${indexPath} not found — run the build first`);
  process.exit(2);
}
if (!stat.isFile()) {
  console.error(`error: ${indexPath} is not a file`);
  process.exit(2);
}

const html = readFileSync(indexPath, "utf8");
const refs = [
  ...html.matchAll(/<script[^>]+src="([^"]+)"/g),
  ...html.matchAll(/<link[^>]+rel="(?:stylesheet|modulepreload)"[^>]+href="([^"]+)"/g),
  ...html.matchAll(/<link[^>]+href="([^"]+)"[^>]+rel="(?:stylesheet|modulepreload)"/g),
].map((m) => m[1]);

let initialGz = gz(indexPath);
for (const ref of new Set(refs)) {
  if (/^(https?:)?\/\//.test(ref)) continue; // external — nothing should be, but don't crash
  initialGz += gz(join(dist, ref.replace(/^[./]*/, "")));
}
report(
  initialGz <= budgets.initial_route_gz_bytes,
  "initial route (html+css+js, gz)",
  initialGz,
  budgets.initial_route_gz_bytes,
);

// --- 2. engine chunk + 3. shipped assets ------------------------------------
for (const path of walk(dist)) {
  const rel = relative(dist, path);
  const name = rel.toLowerCase();

  if (/babylon/.test(name) && name.endsWith(".js")) {
    report(gz(path) <= budgets.engine_chunk_gz_bytes, `engine chunk ${rel} (gz)`, gz(path), budgets.engine_chunk_gz_bytes);
    continue;
  }

  const tiered = (ext, mobileBudget, desktopBudget) => {
    if (!name.endsWith(ext)) return;
    const desktop = /-d\.[a-z]+$/.test(name);
    const budget = desktop ? desktopBudget : mobileBudget;
    const size = statSync(path).size;
    report(size <= budget, `${rel} (${desktop ? "desktop" : "mobile"} tier)`, size, budget);
  };
  tiered(".sog", budgets.assets.sog_mobile_bytes, budgets.assets.sog_desktop_bytes);
  tiered(".glb", budgets.assets.glb_mobile_bytes, budgets.assets.glb_desktop_bytes);
}

process.exit(failed ? 1 : 0);
