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
 * The CSS-war (Tailwind-vs-Bootstrap isolation) stays framework-owned: the
 * PostCSS chain below runs the desk-islands Tailwind config + the
 * `!important`-stamping plugin, both in this repo — NOT in frappe-ui.
 *
 * Usage (see package.json):
 *   node esbuild/build-islands.mjs --mode production
 *   node esbuild/build-islands.mjs --mode development --watch
 */
import { build } from "vite";
import vue from "@vitejs/plugin-vue";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as LucideIcons from "lucide-static";

const require = createRequire(import.meta.url);
const fg = require("fast-glob");
const autoprefixer = require("autoprefixer");
const tailwindcss = require("tailwindcss");
const frappeUIImportant = require("./postcss-frappe-ui-important.js");
const { write_island_assets, notify_island_build, notify_island_error, sites_path } = require(
	"./island-assets.js"
);

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const APP = "frappe";
const DIST_DIR = path.join(sites_path, "assets", APP, "dist");
const TAILWIND_CONFIG = path.join(REPO_ROOT, "tailwind.config.desk-islands.mjs");

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
		`[islands] building ${entries.length} island(s) [mode=${MODE}${WATCH ? ", watch" : ""}]`
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
					console.error(`[islands] ${entry.name} build error:`, ev.error?.message);
					notify_island_error(ev.error).catch(() => {});
				}
			});
		}
	}

	if (!WATCH) console.log("[islands] done");
}

/** Discover island entries → [{ name, entryAbs }]. */
function discoverIslandEntries() {
	const matches = fg.sync("frappe/public/js/islands/**/*.bundle.{js,ts}", { cwd: REPO_ROOT });
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
				// frappe-ui's `exports` map only exposes the `.` barrel, but islands
				// deep-import `frappe-ui/src/components/<X>` so the barrel doesn't drag
				// in components (TextEditor, Charts) whose heavy deps (tiptap, echarts)
				// aren't installed for the linked clone. Alias bypasses exports
				// enforcement for the `src/` subtree.
				{ find: /^frappe-ui\/src\//, replacement: path.join(REPO_ROOT, "frappe-ui/src/") },
				// Island bundles import the mount helper as
				// `frappe/public/js/frappe/ui/vue_island.js` (the same specifier the
				// esbuild pipeline resolves via nodePaths). Map it to the app dir.
				{ find: /^frappe\/public\//, replacement: path.join(REPO_ROOT, "frappe/public/") },
			],
		},
		css: {
			// Framework-owned CSS-war chain: tailwindcss (scoped, `[data-frappe-ui]`
			// utilities) → autoprefixer → !important-stamp (so the rules beat
			// Bootstrap's !important helpers).
			postcss: {
				plugins: [tailwindcss(TAILWIND_CONFIG), autoprefixer, frappeUIImportant],
			},
		},
		plugins: [vue(), lucideIconsPlugin(), islandRegisterPlugin(name)],
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
			const cssAsset = nodes.find((o) => o.type === "asset" && o.fileName.endsWith(".css"));

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

/**
 * Resolve `~icons/lucide/<name>` virtual imports used by frappe-ui source.
 *
 * Vite analog of esbuild/lucide-icons.js — framework-side and dependency-free
 * (no unplugin-auto-import / unplugin-vue-components, unneeded for islands'
 * explicit imports and which would write *.d.ts litter). Behaviour matches
 * frappe-ui/vite/lucideIcons.js: read SVGs from lucide-static, normalize
 * stroke-width 2 → 1.5, map camelCase keys to kebab variants, render a tiny Vue
 * component per icon (placeholder for icons removed in lucide v1).
 */
function lucideIconsPlugin() {
	const VIRTUAL_PREFIX = "~icons/lucide/";
	const RESOLVED_PREFIX = "\0frappe-ui-lucide/";
	const FALLBACK_INNER_HTML =
		'<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>';
	const warned = new Set();
	const icons = buildIconMap();

	return {
		name: "frappe-island-lucide-icons",
		enforce: "pre",
		resolveId(id) {
			if (id.startsWith(VIRTUAL_PREFIX)) {
				return RESOLVED_PREFIX + id.slice(VIRTUAL_PREFIX.length);
			}
		},
		load(id) {
			const normalized = id.split("?", 1)[0];
			if (!normalized.startsWith(RESOLVED_PREFIX)) return;
			const name = normalized.slice(RESOLVED_PREFIX.length);
			const svg = icons[name];
			if (!svg) {
				if (!warned.has(name)) {
					warned.add(name);
					this.warn(
						`[frappe-island-lucide-icons] icon "${name}" not found in lucide-static; ` +
							`rendering a placeholder. Replace ~icons/lucide/${name} with a valid icon.`
					);
				}
				return iconModule(FALLBACK_INNER_HTML, name);
			}
			const inner = svg.match(/<svg[^>]*>([\s\S]*)<\/svg>/);
			const innerHTML = inner ? inner[1].replace(/>\s+</g, "><").trim() : "";
			return iconModule(innerHTML);
		},
	};

	function iconModule(innerHTML, missing) {
		const missingAttr = missing ? `'data-lucide-missing': ${JSON.stringify(missing)},` : "";
		return `
import { h } from 'vue'
export default {
  inheritAttrs: false,
  render() {
    return h('svg', {
      xmlns: 'http://www.w3.org/2000/svg',
      width: '24', height: '24', viewBox: '0 0 24 24',
      fill: 'none', stroke: 'currentColor', 'stroke-width': '1.5',
      'stroke-linecap': 'round', 'stroke-linejoin': 'round',
      ${missingAttr}
      ...this.$attrs,
      innerHTML: ${JSON.stringify(innerHTML)},
    })
  }
}`;
	}

	function buildIconMap() {
		const out = {};
		for (const key in LucideIcons) {
			if (key === "default") continue;
			let svg = LucideIcons[key];
			if (typeof svg === "string" && svg.includes("stroke-width")) {
				svg = svg.replace(/stroke-width="2"/g, 'stroke-width="1.5"');
			}
			out[key] = svg;
			for (const dash of camelToDash(key)) if (dash !== key) out[dash] = svg;
		}
		return out;
	}

	function camelToDash(key) {
		let withNumber = key.replace(/[A-Z0-9]/g, (m) => "-" + m.toLowerCase());
		if (withNumber.startsWith("-")) withNumber = withNumber.slice(1);
		let withoutNumber = key.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase());
		if (withoutNumber.startsWith("-")) withoutNumber = withoutNumber.slice(1);
		return withNumber !== withoutNumber ? [withNumber, withoutNumber] : [withNumber];
	}
}
