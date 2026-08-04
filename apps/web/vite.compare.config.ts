// Dev-only Vite config for the splat quality-comparison tool
// (compare/index.html). Extends the production config — same plugins, same
// /content/ serving — and adds a middleware that exposes the local splat
// staging folder to the browser:
//   GET /api/splats        → JSON listing of *.sog (name, size, mtime)
//   GET /splats-d/<name>   → streams that file (basename-guarded)
// Run with `npm run compare` (port 5174, so it can sit next to `npm run
// dev`). Never used for builds; the production build/deploy path is
// vite.config.ts and does not include the compare entry.

import { defineConfig, mergeConfig, type Plugin } from "vite";
import { createReadStream, existsSync, readdirSync, statSync } from "node:fs";
import { basename, join } from "node:path";
import baseConfig from "./vite.config";

// Kari's splat staging folder (WSL view of D:\renders\lunar-base\assets\splats).
// Override per-run: SPLAT_DIR=/some/where npm run compare
const SPLAT_DIR = process.env.SPLAT_DIR ?? "/mnt/d/renders/lunar-base/assets/splats";

function splatDirServer(): Plugin {
  return {
    name: "compare-splat-dir",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? "").split("?")[0];

        if (url === "/api/splats") {
          let files: { name: string; size: number; mtime: number }[] = [];
          try {
            files = readdirSync(SPLAT_DIR)
              .filter((f) => f.toLowerCase().endsWith(".sog"))
              .flatMap((name) => {
                // one vanishing/locked file must not empty the whole listing
                try {
                  const st = statSync(join(SPLAT_DIR, name));
                  return [{ name, size: st.size, mtime: st.mtimeMs }];
                } catch {
                  return [];
                }
              });
          } catch (err) {
            console.error(`[compare] cannot list ${SPLAT_DIR}:`, err);
          }
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify({ dir: SPLAT_DIR, files }));
          return;
        }

        if (url.startsWith("/splats-d/")) {
          // basename() blocks path traversal; only .sog is ever served
          const name = basename(decodeURIComponent(url.slice("/splats-d/".length)));
          const file = join(SPLAT_DIR, name);
          if (!name.toLowerCase().endsWith(".sog") || !existsSync(file)) {
            res.statusCode = 404;
            res.end("not found");
            return;
          }
          res.setHeader("Content-Type", "application/octet-stream");
          res.setHeader("Content-Length", String(statSync(file).size));
          // an unhandled read-stream 'error' would throw and kill the dev
          // server (file replaced mid-read, D: unmounted) — fail the response
          createReadStream(file)
            .on("error", (err) => {
              console.error(`[compare] stream ${name} failed:`, err.message);
              res.destroy(err);
            })
            .pipe(res);
          return;
        }

        next();
      });
    },
  };
}

export default mergeConfig(
  baseConfig,
  defineConfig({
    plugins: [splatDirServer()],
    server: { port: 5174 },
    // own dep cache — sharing node_modules/.vite with the plain `npm run dev`
    // server invalidates ITS optimized Babylon chunks mid-flight (the concept
    // page then loads with no splats until that server restarts)
    cacheDir: "node_modules/.vite-compare",
  }),
);
