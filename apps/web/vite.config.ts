import { defineConfig, type Plugin } from "vite";
import { resolve, join, normalize, sep } from "node:path";
import { cpSync, existsSync, readFileSync, statSync } from "node:fs";

// content/concepts/*.json is the single source of truth (repo root, outside
// the app). Serve it in dev and copy it into dist on build — no duplication.
function conceptContent(): Plugin {
  const contentDir = resolve(__dirname, "../../content");
  let outDir = "dist";
  return {
    name: "concept-content",
    configResolved(config) {
      outDir = config.build.outDir;
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? "").split("?")[0];
        if (!url.startsWith("/content/")) return next();
        const file = join(contentDir, normalize(url.slice("/content/".length)));
        if (!file.startsWith(contentDir + sep) || !existsSync(file) || !statSync(file).isFile()) return next();
        res.setHeader("Content-Type", file.endsWith(".json") ? "application/json" : "text/plain");
        res.end(readFileSync(file));
      });
    },
    closeBundle() {
      cpSync(contentDir, resolve(__dirname, outDir, "content"), { recursive: true });
    },
  };
}

// BASE_PATH lets CI build for a sub-path host (GitHub Pages project sites
// serve at /<repo>/); local dev and root-path hosts use "/".
export default defineConfig({
  plugins: [conceptContent()],
  base: process.env.BASE_PATH ?? "/",
  build: {
    // budget check (pipeline/pack/check-budgets.mjs) measures gzipped output;
    // keep vite's own gzip reporter on for eyeballing during dev builds
    reportCompressedSize: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        // unlinked M1 dev harness; not referenced from index.html
        devViewer: resolve(__dirname, "dev/viewer.html"),
        // unlinked structure mockups for Kari's pick (plan Part C)
        mockupA: resolve(__dirname, "mockups/a.html"),
        mockupB: resolve(__dirname, "mockups/b.html"),
        mockupC: resolve(__dirname, "mockups/c.html"),
        mockupC2: resolve(__dirname, "mockups/c2.html"),
        // the production concept-page template (JSON-driven; /concept/?id=<x>)
        conceptPage: resolve(__dirname, "concept/index.html"),
      },
      output: {
        // Babylon v9 materials pull shaders via per-file dynamic import();
        // without consolidation they explode into dozens of micro-chunks the
        // budget checker can't attribute. Two language chunks, both /babylon/i.
        manualChunks(id) {
          if (id.includes("@babylonjs/core/ShadersWGSL/")) return "babylon-shaders-wgsl";
          if (id.includes("@babylonjs/core/Shaders/")) return "babylon-shaders-glsl";
          return undefined;
        },
        // check-budgets.mjs finds the engine chunks by /babylon/i on the file
        // name — force the prefix onto every chunk that carries engine bytes.
        // (Any chunk with engine code contains @babylonjs/fflate module ids;
        // Babylon-free viewer helpers like tiering/types must NOT get the
        // prefix — they load eagerly with page entries.)
        chunkFileNames(chunk) {
          const engineSide = chunk.moduleIds.some(
            (m) => m.includes("@babylonjs") || m.includes("node_modules/fflate/"),
          );
          return engineSide && !/babylon/i.test(chunk.name)
            ? "assets/babylon-[name]-[hash].js"
            : "assets/[name]-[hash].js";
        },
      },
    },
  },
});
