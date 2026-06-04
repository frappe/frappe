/**
 * Vite build for Frappe Desk islands (frappe-ui-based Vue pages).
 *
 * This is the SECOND, parallel asset pipeline. Legacy Desk bundles keep
 * building through esbuild (esbuild/esbuild.js, esbuild ^0.28) untouched.
 * Island entries — `*.bundle.{js,ts}` living under `frappe/public/js/islands/`,
 * a directory the esbuild pipeline ignores — build here, the way frappe-ui is
 * designed to be consumed: latest @vue/compiler-sfc, native `import.meta.env`,
 * and the `~icons/lucide/*` virtual-module form. Islands keep the familiar
 * `.bundle.js` name so `frappe.require` / `bundled_asset` resolve them with no
 * runtime changes; the `islands/` directory is the only thing that routes them
 * to Vite instead of esbuild.
 *
 * Why a programmatic loop (not `vite build -c <config>`):
 *   Frappe's `frappe.require` injects a CLASSIC <script> (assets.js sets
 *   `script.type = "text/javascript"`), so each island bundle must be an IIFE,
 *   exactly like the esbuild bundles. Rollup forbids the iife format for a
 *   code-splitting (multi-entry) build, so we build each island on its own as a
 *   self-contained iife via Vite's JS API and read the output filenames back
 *   from the returned RollupOutput (no manifest needed).
 *
 * Both pipelines write hashed output into `sites/assets/<app>/dist` and share
 * one `assets.json` (merge + Redis invalidation live in ./island-assets.js).
 *
 * Isolation: islands mount in a Shadow DOM (see frappe.ui.mount_vue_island), so
 * there is NO CSS-war — frappe-ui ships its normal full Tailwind + preflight and
 * the shadow boundary contains it both ways. The only Desk adaptation is the
 * PostCSS `postcss-root-to-host` plugin, which rewrites `:root` design tokens to
 * `:host` so they apply inside the shadow tree.
 *
 * Usage (see package.json):
 *   node esbuild/build-islands.mjs --mode production
 *   node esbuild/build-islands.mjs --mode development --watch
 */
import { build } from "vite";
import vue from "@vitejs/plugin-vue";
import { lucideIconsPlugin } from "frappe-ui/vite/lucideIconsPlugin";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const require = createRequire(import.meta.url);
const fg = require("fast-glob");
const autoprefixer = require("autoprefixer");
const tailwindcss = require("tailwindcss");
const rootToHost = require("./postcss-root-to-host.js");
const {
  write_island_assets,
  notify_island_build,
  notify_island_error,
  sites_path,
} = require("./island-assets.js");

// Let @vue/compiler-sfc resolve cross-package types in `defineProps<T>()`.
//
// frappe-ui components compiled from source use the type-macro form, e.g.
// TextEditor's `defineProps<NodeViewProps>()` importing the type from
// `@tiptap/vue-3`. compiler-sfc can only resolve such imported types through
// the TypeScript compiler API, and the consumer (here, this island build) must
// hand it TypeScript via `registerTS` — @vitejs/plugin-vue 5.2.x does not.
//
// It must be TS >= 5: the types live behind modern `exports` maps that only
// `moduleResolution: bundler` (TS 5) can follow. The repo's hoisted typescript
// is 4.x (pulled by esbuild-plugin-vue3), so frappe declares its own
// `typescript@^5` devDep, which `require("typescript")` resolves here.
//
// Without this, importing the `frappe-ui` barrel fails to compile (one heavy
// component's type kills the whole graph), forcing islands into deep
// `frappe-ui/src/components/*` imports. With it, islands use the idiomatic
// `import { Button } from "frappe-ui"` and unused components tree-shake away.
const { registerTS } = require("vue/compiler-sfc");
registerTS(() => require("typescript"));

const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  ".."
);
const APP = "frappe";
const DIST_DIR = path.join(sites_path, "assets", APP, "dist");
const TAILWIND_CONFIG = path.join(
  REPO_ROOT,
  "tailwind.config.desk-islands.mjs"
);

const MODE = arg("--mode") || "production";
const WATCH = process.argv.includes("--watch");
// Mirrors esbuild's `--live-reload`: full Desk reload instead of a soft
// hot_update swap. Off by default (soft reload), same as esbuild.
const LIVE_RELOAD = process.argv.includes("--live-reload");

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

async function main() {
  const entries = discoverIslandEntries();
  if (!entries.length) {
    console.log("[islands] no islands/**/*.bundle.{js,ts} entries found");
    return;
  }
  console.log(
    `[islands] building ${entries.length} island(s) [mode=${MODE}${
      WATCH ? ", watch" : ""
    }]`
  );

  // Build each island independently (Rollup forbids `iife` for a multi-entry
  // build). SUCCESS registration into assets.json + the success build_event
  // happen in the `writeBundle` hook (islandRegisterPlugin) so they fire
  // identically for a one-shot build and for every watch rebuild. In watch
  // mode build() returns a RollupWatcher that keeps the process alive; we
  // listen for its ERROR events to publish the BuildError overlay event,
  // exactly like esbuild's watcher does on a failed rebuild.
  for (const entry of entries) {
    const result = await build(islandConfig(entry));
    if (WATCH && result && typeof result.on === "function") {
      result.on("event", (ev) => {
        if (ev.code === "ERROR") {
          console.error(
            `[islands] ${entry.name} build error:`,
            ev.error?.message
          );
          notify_island_error(ev.error).catch(() => {});
        }
      });
    }
  }

  if (!WATCH) console.log("[islands] done");
}

/** Discover island entries → [{ name, entryAbs }]. */
function discoverIslandEntries() {
  const matches = fg.sync("frappe/public/js/islands/**/*.bundle.{js,ts}", {
    cwd: REPO_ROOT,
  });
  return matches.map((rel) => ({
    name: path.basename(rel).replace(/\.(js|ts)$/, ""), // foo.bundle
    entryAbs: path.join(REPO_ROOT, rel),
  }));
}

/** Single-entry IIFE Vite config for one island. */
function islandConfig({ name, entryAbs }) {
  return {
    root: REPO_ROOT,
    configFile: false,
    mode: MODE,
    logLevel: "warn",
    resolve: {
      // One Vue instance across the island and frappe-ui source.
      dedupe: [
        "vue",
        "vue-router",
        "@vue/runtime-core",
        "@vue/runtime-dom",
        "@vue/reactivity",
        "@vue/shared",
      ],
      alias: [
        // Island bundles import the mount helper as
        // `frappe/public/js/frappe/ui/vue_island.js` (the same specifier the
        // esbuild pipeline resolves via nodePaths). Map it to the app dir.
        // (frappe-ui itself resolves through its package `exports` — islands
        // import the `frappe-ui` barrel, no deep-path alias needed.)
        {
          find: /^frappe\/public\//,
          replacement: path.join(REPO_ROOT, "frappe/public/"),
        },
      ],
    },
    css: {
      // SHADOW DOM SPIKE: no CSS-war. Full frappe-ui Tailwind + preflight,
      // then `:root` → `:host` so design tokens land on the shadow host.
      // (No `[data-frappe-ui]` scoping, no !important-stamp — the shadow
      // boundary does the isolation.)
      postcss: {
        plugins: [tailwindcss(TAILWIND_CONFIG), autoprefixer, rootToHost],
      },
    },
    plugins: [
      vue(),
      // frappe-ui's bare `~icons/lucide/<name>` virtual-module resolver (shared
      // with frappe-ui's own build; see frappe-ui/vite/lucideIconsPlugin.js).
      // `enforce: "pre"` so it claims the virtual id before other resolvers.
      { ...lucideIconsPlugin(), enforce: "pre" },
      islandRegisterPlugin(name),
    ],
    build: {
      outDir: DIST_DIR,
      // CRITICAL: the esbuild pipeline writes here too — never wipe it.
      emptyOutDir: false,
      sourcemap: true,
      minify: MODE === "production",
      // false → Vite extracts ONE stylesheet asset for the entry. With a
      // single iife entry + inlineDynamicImports, cssCodeSplit:true makes
      // Vite inject CSS via JS at runtime and emit no .css file; islands
      // load their CSS as a separate `frappe.require` link, so we need a
      // real extracted file.
      cssCodeSplit: false,
      manifest: false,
      rollupOptions: {
        input: entryAbs,
        output: {
          format: "iife",
          // Single self-contained island → no code-splitting.
          inlineDynamicImports: true,
          entryFileNames: "js/[name].[hash].js",
          assetFileNames: (asset) => {
            const n = asset.names?.[0] || asset.name || "";
            // Name the extracted stylesheet after the entry, e.g.
            // `frappe_ui_poc.bundle.<hash>.css` (cssCodeSplit is off, so
            // Vite would otherwise emit a generic `style.css`). This gives
            // the CSS the `.bundle.` name `bundled_asset` resolves.
            return n.endsWith(".css")
              ? `css/${name}.[hash][extname]`
              : "assets/[name].[hash][extname]";
          },
        },
      },
      watch: WATCH ? {} : null,
    },
  };
}

/**
 * Vite/Rollup plugin: after the island's files are written (one-shot AND every
 * watch rebuild), register its hashed outputs in assets.json. `writeBundle` is
 * used (not the build() return value) because in watch mode build() yields a
 * RollupWatcher whose events carry a RollupBuild, not the output list.
 */
function islandRegisterPlugin(name) {
  return {
    name: "frappe-island-register",
    async writeBundle(_options, bundle) {
      const nodes = Object.values(bundle); // fileName → OutputChunk | OutputAsset
      const entryChunk = nodes.find((o) => o.type === "chunk" && o.isEntry);
      const cssAsset = nodes.find(
        (o) => o.type === "asset" && o.fileName.endsWith(".css")
      );

      const relMap = {};
      if (entryChunk) relMap[`${name}.js`] = entryChunk.fileName;
      if (cssAsset) relMap[`${name}.css`] = cssAsset.fileName;

      const urlMap = await write_island_assets(relMap, APP);
      console.log(`[islands] ${name}: ${Object.keys(urlMap).join(", ")}`);
      if (WATCH) {
        await notify_island_build({
          changed_files: Object.values(urlMap),
          live_reload: LIVE_RELOAD,
        });
      }
    },
  };
}

function arg(flag) {
  const i = process.argv.indexOf(flag);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : null;
}
