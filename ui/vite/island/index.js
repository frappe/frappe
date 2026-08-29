// The island build preset. It sets everything the mount contract depends on, so
// an app supplies only its entry list. Usage and options in ../../README.md.
//
// The preset runs one vite build for all of an app's islands. Rollup then lifts
// what two entries share into a chunk both import, and the app pays for Vue and
// frappe-ui once however many islands it ships.
// ../../island/decisions/0002-an-app-builds-its-islands-together.md
//
// What is left after that is three jobs: scan the app's stylesheet from what the
// bundle is made of, weigh each island against a budget, and register the built
// files under the asset keys desk resolves.

import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

import frameworkUI from "../index.js";
import {
	benchPaths,
	findBenchRoot,
	islandCssKey,
	islandJsKey,
	notifyRebuild,
	writeIslandAssets,
} from "./assets.js";
import deskFonts from "./desk-fonts.js";
import rootToHost from "./root-to-host.js";
import { bundleSources, unscannedSources } from "./tailwind-scan.js";
import { writeIslandTailwindConfig } from "./tailwind.js";
import { interop, loadTools } from "./tools.js";
import { islandVue } from "./vue.js";

/**
 * Bytes of JS plus CSS one island may load, before compression.
 *
 * This is a backstop, not a target, and it has to clear a real island to be
 * either. An island carries its own Vue, its own frappe-ui and its own
 * preflight, so the floor is high. The fixture in `tests/`, which renders one
 * frappe-ui Button, weighs 288 kB. Insights' dashboard island, which draws a
 * grid of live charts, weighs 1.78 MB. The failure this catches is higher
 * still: an entry that reaches into the SPA's router graph, measured on the
 * first Insights island at 2.3 MB of JS alone.
 *
 * So the default sits above a working island of that size and below that
 * failure. Apps pin `budget` to their own first clean build, where the number
 * means something.
 */
export const DEFAULT_BUDGET = 2 * 1024 * 1024;

/** The CSS module every entry gets, holding the Tailwind directives. */
const TAILWIND_ENTRY = "virtual:island.css";

/**
 * Build every island of an app.
 *
 * @param {Object} options
 * @param {string} options.app       frappe app the output belongs to, e.g. `insights`
 * @param {string} options.root      the app's frontend directory (the vite root)
 * @param {Object<string,string>} options.entries  asset base name → entry file
 * @param {number} [options.budget]  bytes of JS + CSS one island may load; over it warns
 * @param {string[]} [options.tailwindPlugins]  the app's Tailwind plugins, by module specifier
 * @param {(string|RegExp)[]} [options.allowUnscanned]  escape hatch: bundled
 *        files that hold no classes, so `content` need not scan them
 * @param {(string|RegExp)[]} [options.forbiddenImports]  escape hatch: fail on a matching import
 * @param {import('vite').PluginOption[]} [options.plugins]  extra plugins
 * @param {boolean} [options.production]
 * @param {boolean} [options.watch]
 */
export async function buildIslands(options) {
	const context = await islandContext(options);
	const names = Object.keys(context.entries);

	console.log(
		`[island] building ${names.length} island(s) for ${context.app} ` +
			`[mode=${context.mode}${context.watch ? ", watch" : ""}]`
	);

	const scanned = await discoverSources(context);
	const tailwind = writeIslandTailwindConfig(context, scanned);

	const result = await context.tools.vite.build(
		islandConfig({ ...context, tailwind, scanned: new Set(scanned) })
	);

	if (context.watch && typeof result?.on === "function")
		result.on("event", (event) => {
			if (event.code === "ERROR") console.error("[island]", event.error?.message);
		});
}

/**
 * The source the app's islands are built from, for Tailwind to scan.
 *
 * The preset runs a first build with no stylesheet, keeps its module list, and
 * throws the output away. That pass costs about the time of the real build.
 * ../../island/decisions/0003-tailwind-scans-the-module-list-not-a-glob.md
 */
async function discoverSources(context) {
	const modules = new Set();

	const config = islandConfig({ ...context, tailwind: null });
	config.logLevel = "silent";
	config.build.write = false;
	config.build.watch = null;
	config.plugins = config.plugins
		.filter((plugin) => plugin?.name !== "island-emit")
		.concat({
			name: "island-discover",
			generateBundle(_options, bundle) {
				for (const node of Object.values(bundle))
					if (node.type === "chunk")
						for (const id of Object.keys(node.modules)) modules.add(id);
			},
		});

	await context.tools.vite.build(config);
	return bundleSources(modules);
}

/** Everything the config is derived from, resolved once. */
export async function islandContext(options) {
	if (!options.app) throw new Error("island: `app` is required");
	if (!options.root) throw new Error("island: `root` is required");
	if (!Object.keys(options.entries ?? {}).length) throw new Error("island: no entries to build");

	// Vite reports module ids as real paths. A root reached through a symlink
	// would never match the entry it resolves to.
	const root = fs.realpathSync(path.resolve(options.root));

	const entries = Object.fromEntries(
		Object.entries(options.entries).map(([name, file]) => {
			if (!/^[\w.-]+$/.test(name))
				throw new Error(
					`island: entry name "${name}" must be a bare word — it becomes ` +
						"an assets.json key and an output file name."
				);
			return [name, fs.realpathSync(path.resolve(root, file))];
		})
	);

	return {
		...options,
		root,
		entries,
		paths: benchPaths(findBenchRoot(root), options.app),
		mode: options.production ? "production" : "development",
		budget: options.budget ?? DEFAULT_BUDGET,
		tools: await loadTools(root),
	};
}

/** The one vite config that builds all of an app's islands. */
export function islandConfig(context) {
	const { tools } = context;
	const entryPaths = new Set(Object.values(context.entries));

	return {
		root: context.root,
		base: `${context.paths.urlPrefix}/`,
		configFile: false,
		envFile: false,
		publicDir: false,
		mode: context.mode,
		logLevel: "warn",
		define: {
			__VUE_OPTIONS_API__: "true",
			__VUE_PROD_DEVTOOLS__: "false",
			__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: "false",
		},
		css: {
			postcss: {
				// The discovery pass gets no Tailwind config. It runs to
				// produce the module list the config needs.
				plugins: [
					...(context.tailwind ? [interop(tools.tailwindcss)(context.tailwind)] : []),
					interop(tools.autoprefixer),
					rootToHost,
					deskFonts,
				],
			},
		},
		plugins: [
			// The mount contract is `@framework/ui` source the app compiles in
			// place, so its own bare imports resolve against the app.
			...frameworkUI(),
			// `pre`, so this plugin claims `~icons/lucide/<name>` first.
			{ ...tools.lucideIcons.lucideIconsPlugin(), enforce: "pre" },
			tailwindEntry(entryPaths),
			...(context.forbiddenImports?.length
				? [forbiddenImports(context.forbiddenImports)]
				: []),
			islandVue(interop(tools.vue)),
			emitIslands(context),
			...(context.plugins ?? []),
		],
		build: {
			outDir: context.paths.distDir,
			// The app's islands own this directory, so emptying it cannot touch
			// the legacy pipeline's output or another app's islands. An entry
			// the app has dropped leaves in the same build.
			emptyOutDir: true,
			minify: context.mode === "production" ? "esbuild" : false,
			sourcemap: false,
			// One stylesheet for the app, adopted into every island's shadow
			// root. ../../island/decisions/0004-an-app-ships-one-island-stylesheet.md
			cssCodeSplit: false,
			modulePreload: false,
			reportCompressedSize: false,
			target: "esnext",
			rollupOptions: {
				input: context.entries,
				// Desk imports an island for its `mount` export. Without this
				// flag vite treats each entry as an app entry, drops its
				// exports, and tree-shakes the island away.
				preserveEntrySignatures: "exports-only",
				output: {
					format: "es",
					entryFileNames: "[name].island.[hash].js",
					chunkFileNames: "chunks/[name].[hash].js",
					// Rollup 4 reports `names`, and vite's extracted
					// stylesheet arrives with `name` alone.
					assetFileNames: (asset) =>
						(asset.names?.[0] ?? asset.name ?? "").endsWith(".css")
							? `${context.app}.island.[hash][extname]`
							: "assets/[name].[hash][extname]",
				},
			},
			watch: context.watch ? {} : null,
		},
	};
}

/**
 * Give every entry the app's stylesheet. The preset owns what an island sheet
 * holds, so it injects the directives instead of the app writing them.
 *
 * All entries import the same virtual module, and `cssCodeSplit: false` collects
 * the build's CSS into one file, so the directives are compiled once.
 */
function tailwindEntry(entryPaths) {
	return {
		name: "island-tailwind-entry",
		enforce: "pre",
		resolveId(source) {
			return source === TAILWIND_ENTRY ? TAILWIND_ENTRY : null;
		},
		load(id) {
			return id === TAILWIND_ENTRY
				? "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n"
				: null;
		},
		transform(code, id) {
			if (!entryPaths.has(id.split("?")[0])) return null;
			return { code: `import "${TAILWIND_ENTRY}";\n${code}`, map: null };
		},
	};
}

/** Optional, app-local: refuse an import the app has decided not to allow. */
function forbiddenImports(patterns) {
	const matches = (source) =>
		patterns.some((pattern) =>
			pattern instanceof RegExp ? pattern.test(source) : source === pattern
		);

	return {
		name: "island-forbidden-imports",
		enforce: "pre",
		resolveId(source, importer) {
			if (matches(source))
				this.error(
					`island: ${source} is a forbidden import` +
						(importer ? ` (from ${importer})` : "")
				);
			return null;
		},
	};
}

/**
 * Weigh each island, check it against the budget and the stylesheet, then
 * register the whole app's islands in assets.json.
 *
 * All of it sits in one `writeBundle` hook. It is the only hook a watcher
 * replays, and the first one that sees the stylesheet, because vite's css-post
 * plugin emits it after every user `generateBundle`. Rollup runs `writeBundle`
 * hooks in parallel, so a separate gate plugin could not run before this one.
 */
function emitIslands(context) {
	const { budget, paths } = context;

	return {
		name: "island-emit",
		async writeBundle(_options, bundle) {
			const css = Object.values(bundle).find((node) => node.fileName.endsWith(".css"));
			const style = css ? measure(css.source) : { raw: 0, gzip: 0 };

			const relMap = {};
			for (const [name, entry] of entryChunks(bundle)) {
				const js = sum(reachable(bundle, entry.fileName).map((n) => measure(n.code)));
				console.log(`[island] ${name}: ${report(js)} JS, ${report(style)} CSS`);

				// A warning, not an error. The budget is a number an app tunes as its
				// island grows, and a build that stops leaves the island's assets on
				// disk with no `assets.json` entry — a broken island, for a size the
				// app may well accept. `forbiddenImports` is the check that fails the
				// build, because it names a recoupling rather than measuring one.
				if (js.raw + style.raw > budget)
					this.warn(
						`island ${name} loads ${kb(js.raw + style.raw)} of JS + CSS, ` +
							`over the ${kb(budget)} budget. An entry this size ` +
							"pulls in something it should not. Check the entry's " +
							"import graph, or raise `budget` deliberately."
					);

				relMap[islandJsKey(name)] = entry.fileName;
				if (css) relMap[islandCssKey(name)] = css.fileName;
			}

			assertSheetScannedTheBundle(context, bundle, this);
			notifyRebuild(await writeIslandAssets(paths, relMap));
		},
	};
}

/** Entry name → its chunk. Rollup names an entry chunk after its input key. */
function entryChunks(bundle) {
	return Object.values(bundle)
		.filter((node) => node.type === "chunk" && node.isEntry)
		.map((chunk) => [chunk.name, chunk]);
}

/**
 * Every chunk the browser loads to run one entry.
 *
 * Static imports only. A dynamic import is work the island deferred, and
 * charging the entry for it would leave an island no way to defer anything.
 */
function reachable(bundle, entryFileName) {
	const seen = new Set();
	const queue = [entryFileName];

	while (queue.length) {
		const fileName = queue.pop();
		if (seen.has(fileName)) continue;
		const node = bundle[fileName];
		if (node?.type !== "chunk") continue;
		seen.add(fileName);
		queue.push(...node.imports);
	}

	return [...seen].map((fileName) => bundle[fileName]);
}

/**
 * Refuse a bundle built from source the stylesheet never read.
 *
 * A full build derives the scan list from the module list, so this check fires
 * only under `watch`. There the scan list is fixed at start-up.
 * ../../island/decisions/0003-tailwind-scans-the-module-list-not-a-glob.md
 */
function assertSheetScannedTheBundle(context, bundle, plugin) {
	const modules = new Set();
	for (const node of Object.values(bundle))
		if (node.type === "chunk") for (const id of Object.keys(node.modules)) modules.add(id);

	const unscanned = unscannedSources({
		modules,
		scanned: context.scanned,
		allowUnscanned: context.allowUnscanned ?? [],
	});
	if (!unscanned.length) return;

	const relative = unscanned.map((file) => path.relative(context.root, file));
	plugin.error(
		`the island stylesheet was not scanned from ${relative.length} file(s) ` +
			`the bundle is built from:\n  ${relative.join("\n  ")}\n` +
			"A Tailwind class written in one of these gets no rule, and no " +
			"other check reports it. Restart the build to scan them."
	);
}

/* --------------------------------------------------------------- measuring */

function measure(source) {
	const buffer = Buffer.isBuffer(source) ? source : Buffer.from(source);
	return { raw: buffer.length, gzip: zlib.gzipSync(buffer, { level: 9 }).length };
}

const sum = (sizes) =>
	sizes.reduce((a, b) => ({ raw: a.raw + b.raw, gzip: a.gzip + b.gzip }), {
		raw: 0,
		gzip: 0,
	});

const kb = (bytes) => `${(bytes / 1024).toFixed(1)} kB`;
const report = ({ raw, gzip }) => `${kb(raw)} raw / ${kb(gzip)} gzip`;
