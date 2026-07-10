import { defineConfig } from "vite";

// BASE_PATH lets CI build for a sub-path host (GitHub Pages project sites
// serve at /<repo>/); local dev and root-path hosts use "/".
export default defineConfig({
  base: process.env.BASE_PATH ?? "/",
  build: {
    // budget check (pipeline/pack/check-budgets.mjs) measures gzipped output;
    // keep vite's own gzip reporter on for eyeballing during dev builds
    reportCompressedSize: true,
  },
});
