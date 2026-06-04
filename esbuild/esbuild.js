const path = require("path");
const fs = require("fs");
const glob = require("fast-glob");
const esbuild = require("esbuild");
const vue = require("esbuild-plugin-vue3");
// Patch the Vue plugin's internal compileScript so it gets an `fs` option.
//
// Why: @vue/compiler-sfc 3.3+ needs filesystem access to resolve TypeScript
// types referenced in `defineProps<T>()` / `defineEmits<T>()` macros — many
// frappe-ui components use that form (Button, Dialog, FormControl, …) and
// import the type from a sibling `./types.ts`. Without `fs`, compileScript
// throws "No fs option provided to compileScript in non-Node environment"
// and the build fails.
//
// `esbuild-plugin-vue3` 0.3.2 passes only `{ id }` to compileScript. It
// imports its own nested copy of @vue/compiler-sfc, so we patch THAT
// instance (the top-level one wouldn't reach the plugin).
(function patchVueCompileScript() {
	// Resolve from the Vue plugin's location so we patch whichever
	// @vue/compiler-sfc the plugin actually imports — older plugin versions
	// nested their own copy; 0.5.x uses the top-level install.
	const pluginDir = path.dirname(require.resolve("esbuild-plugin-vue3"));
	let sfc;
	try {
		sfc = require(require.resolve("@vue/compiler-sfc", { paths: [pluginDir] }));
	} catch (e) {
		return; // plugin or compiler-sfc not installed (e.g. CI dependency prune)
	}
	if (sfc._frappePatched) return;
	const orig = sfc.compileScript;
	sfc.compileScript = function (descriptor, options) {
		return orig.call(this, descriptor, {
			fs: {
				fileExists: (file) => {
					try {
						return fs.statSync(file).isFile();
					} catch (_) {
						return false;
					}
				},
				readFile: (file) => {
					try {
						return fs.readFileSync(file, "utf-8");
					} catch (_) {
						return undefined;
					}
				},
			},
			...options,
		});
	};
	sfc._frappePatched = true;
})();
const yargs = require("yargs");
const cliui = require("cliui")();
const chalk = require("chalk");
const html_plugin = require("./frappe-html");
const vue_style_plugin = require("./frappe-vue-style");
const rtlcss = require("rtlcss");
const postCssPlugin = require("@frappe/esbuild-plugin-postcss2").default;
const ignore_assets = require("./ignore-assets");
const sass_options = require("./sass_options");
const build_cleanup_plugin = require("./build-cleanup");
// Desk-island Tailwind support: processes `@tailwind utilities;` directives in
// bundle CSS files, scoping all generated utilities to `[data-frappe-ui]`.
const tailwindcss = require("tailwindcss");
const DESK_ISLANDS_TAILWIND_CONFIG = path.resolve(
	__dirname,
	"../tailwind.config.desk-islands.mjs"
);
const frappeUIImportant = require("./postcss-frappe-ui-important");
// Resolves `~icons/lucide/*` virtual imports used by frappe-ui sources that
// haven't migrated to the class-based lucide-* form yet.
const lucideIconsPlugin = require("./lucide-icons");

const {
	app_list,
	assets_path,
	apps_path,
	sites_path,
	get_public_path,
	log,
	log_warn,
	log_error,
	bench_path,
	get_redis_subscriber,
} = require("./utils");

const argv = yargs
	.usage("Usage: node esbuild [options]")
	.option("apps", {
		type: "string",
		description: "Run build for specific apps",
	})
	.option("skip_frappe", {
		type: "boolean",
		description: "Skip building frappe assets",
	})
	.option("files", {
		type: "string",
		description: "Run build for specified bundles",
	})
	.option("watch", {
		type: "boolean",
		description: "Run in watch mode and rebuild on file changes",
	})
	.option("live-reload", {
		type: "boolean",
		description: `Automatically reload Desk when assets are rebuilt.
			Can only be used with the --watch flag.`,
	})
	.option("production", {
		type: "boolean",
		description: "Run build in production mode",
	})
	.option("run-build-command", {
		type: "boolean",
		description: "Run build command for apps",
	})
	.option("save-metafiles", {
		type: "boolean",
		description:
			"Saves esbuild metafiles for built assets. Useful for analyzing bundle size. More info: https://esbuild.github.io/api/#metafile",
	})
	.option("using-cached", {
		type: "boolean",
		description:
			"Skips build and uses cached build artifacts to update assets.json (used by Bench)",
	})
	.option("esbuild-target", {
		type: "string",
		description: "Specifies the target of the build output.",
	})
	.example("node esbuild --apps frappe,erpnext", "Run build only for frappe and erpnext")
	.example(
		"node esbuild --files frappe/website.bundle.js,frappe/desk.bundle.js",
		"Run build only for specified bundles"
	)
	.version(false).argv;

const APPS = (!argv.apps ? app_list : argv.apps.split(",")).filter(
	(app) => !(argv.skip_frappe && app == "frappe")
);
const FILES_TO_BUILD = argv.files ? argv.files.split(",") : [];
const WATCH_MODE = Boolean(argv.watch);
const PRODUCTION = Boolean(argv.production);
const RUN_BUILD_COMMAND = !WATCH_MODE && Boolean(argv["run-build-command"]);
const ESBUILD_TARGET = argv["esbuild-target"] || "es2017";

const TOTAL_BUILD_TIME = `${chalk.black.bgGreen(" DONE ")} Total Build Time`;
const NODE_PATHS = [].concat(
	// node_modules of apps directly importable
	app_list.map((app) => path.resolve(apps_path, app, "node_modules")).filter(fs.existsSync),
	// import js file of any app if you provide the full path
	app_list.map((app) => path.resolve(apps_path, app)).filter(fs.existsSync)
);
const USING_CACHED = Boolean(argv["using-cached"]);

execute().catch((e) => {
	console.error(e);
	process.exit(1);
});

if (WATCH_MODE) {
	// listen for open files in editor event
	open_in_editor();
}

async function execute() {
	console.time(TOTAL_BUILD_TIME);
	if (USING_CACHED) {
		await update_assets_json_from_built_assets(APPS);
		await update_assets_json_in_cache();
		console.timeEnd(TOTAL_BUILD_TIME);
		process.exit(0);
	}

	let results;
	try {
		results = await build_assets_for_apps(APPS, FILES_TO_BUILD);
	} catch (e) {
		log_error("There were some problems during build");
		log();
		log(chalk.dim(e.stack));
		if (process.env.CI || PRODUCTION) {
			process.kill(process.pid);
		}
		return;
	}

	if (!WATCH_MODE) {
		log_built_assets(results);
		console.timeEnd(TOTAL_BUILD_TIME);
		log();
	} else {
		log("Watching for changes...");
	}
	for (const result of results) {
		await write_assets_json(result.metafile);
	}
	RUN_BUILD_COMMAND && run_build_command_for_apps(APPS);
	if (!WATCH_MODE) {
		process.exit(0);
	}
}

async function update_assets_json_from_built_assets(apps) {
	const assets = await get_assets_json_path_and_obj(false);
	const assets_rtl = await get_assets_json_path_and_obj(true);

	for (const app of apps) {
		await update_assets_obj(app, assets.obj, assets_rtl.obj);
	}

	for (const { obj, path } of [assets, assets_rtl]) {
		const data = JSON.stringify(obj, null, 4);
		await fs.promises.writeFile(path, data);
	}
}

async function update_assets_obj(app, assets, assets_rtl) {
	const app_path = path.join(apps_path, app, app);
	const dist_path = path.join(app_path, "public", "dist");
	const files = await glob("**/*.bundle.*.{js,css}", { cwd: dist_path });
	const assets_dist = path.join("assets", app, "dist");
	const prefix = path.join("/", assets_dist);

	// eg: "js/marketplace.bundle.6SCSPSGQ.js"
	for (const file of files) {
		const source_path = path.join(dist_path, file);
		const dest_path = path.join(sites_path, assets_dist, file);

		// Copy asset file from app/public to sites/assets
		if (!fs.existsSync(dest_path)) {
			const dest_dir = path.dirname(dest_path);
			fs.mkdirSync(dest_dir, { recursive: true });
			fs.copyFileSync(source_path, dest_path);
		}

		// eg: [ "marketplace", "bundle", "6SCSPSGQ", "js" ]
		const parts = path.basename(file).split(".");

		// eg: "marketplace.bundle.js"
		const key = [...parts.slice(0, -2), parts.at(-1)].join(".");

		// eg: "js/marketplace.bundle.6SCSPSGQ.js"
		const value = path.join(prefix, file);
		if (file.includes("-rtl")) {
			assets_rtl[`rtl_${key}`] = value;
		} else {
			assets[key] = value;
		}
	}
}

function build_assets_for_apps(apps, files) {
	let { include_patterns, ignore_patterns } = files.length
		? get_files_to_build(files)
		: get_all_files_to_build(apps);

	return glob(include_patterns, { ignore: ignore_patterns }).then((files) => {
		let output_path = assets_path;

		let file_map = {};
		let style_file_map = {};
		let rtl_style_file_map = {};
		for (let file of files) {
			let relative_app_path = path.relative(apps_path, file);
			let app = relative_app_path.split(path.sep)[0];

			let extension = path.extname(file);
			let output_name = path.basename(file, extension);
			if ([".css", ".scss", ".less", ".sass", ".styl"].includes(extension)) {
				output_name = path.join("css", output_name);
			} else if ([".js", ".ts"].includes(extension)) {
				output_name = path.join("js", output_name);
			}
			output_name = path.join(app, "dist", output_name);

			if (
				Object.keys(file_map).includes(output_name) ||
				Object.keys(style_file_map).includes(output_name)
			) {
				log_warn(`Duplicate output file ${output_name} generated from ${file}`);
			}
			if ([".css", ".scss", ".less", ".sass", ".styl"].includes(extension)) {
				style_file_map[output_name] = file;
				rtl_style_file_map[output_name.replace("/css/", "/css-rtl/")] = file;
			} else {
				file_map[output_name] = file;
			}
		}
		let build = build_files({
			files: file_map,
			outdir: output_path,
		});
		let style_build = build_style_files({
			files: style_file_map,
			outdir: output_path,
		});
		let rtl_style_build = build_style_files({
			files: rtl_style_file_map,
			outdir: output_path,
			rtl_style: true,
		});
		return Promise.all([build, style_build, rtl_style_build]);
	});
}

function get_all_files_to_build(apps) {
	let include_patterns = [];
	let ignore_patterns = [];

	for (let app of apps) {
		let public_path = get_public_path(app);
		include_patterns.push(
			path.resolve(public_path, "**", "*.bundle.{js,ts,css,sass,scss,less,styl,jsx}")
		);
		ignore_patterns.push(
			path.resolve(public_path, "node_modules"),
			path.resolve(public_path, "dist"),
			// frappe-ui Desk islands: `*.bundle.{js,ts}` under `js/islands/` are
			// built by the Vite pipeline (esbuild/build-islands.mjs), not esbuild.
			path.resolve(public_path, "js", "islands")
		);
	}

	return {
		include_patterns,
		ignore_patterns,
	};
}

function get_files_to_build(files) {
	// files: ['frappe/website.bundle.js', 'erpnext/main.bundle.js']
	let include_patterns = [];
	let ignore_patterns = [];

	for (let file of files) {
		let [app, bundle] = file.split("/");
		let public_path = get_public_path(app);
		include_patterns.push(path.resolve(public_path, "**", bundle));
		ignore_patterns.push(
			path.resolve(public_path, "node_modules"),
			path.resolve(public_path, "dist"),
			// See get_all_files_to_build: islands build via Vite, not esbuild.
			path.resolve(public_path, "js", "islands")
		);
	}

	return {
		include_patterns,
		ignore_patterns,
	};
}

function build_files({ files, outdir }) {
	// lucideIconsPlugin must run before vue() so `~icons/lucide/*` imports
	// inside .vue <script> blocks are resolved before Vue tries to.
	//
	// `compilerOptions.expressionPlugins: ['typescript']` enables TS syntax
	// inside <template> expressions (non-null assertions `foo!.bar`, type
	// casts, etc.) which several frappe-ui components use — notably
	// Combobox/MultiSelect/Popover. Without it, the Babel-based template
	// expression parser inside @vue/compiler-sfc throws on tokens like `!]`.
	let build_plugins = [
		lucideIconsPlugin,
		vue({
			compilerOptions: {
				expressionPlugins: ["typescript"],
			},
		}),
		html_plugin,
		build_cleanup_plugin,
		vue_style_plugin,
	];
	if (WATCH_MODE) build_plugins.push(watch_plugin);
	return build_or_watch(get_build_options(files, outdir, build_plugins));
}

/**
 * esbuild plugin that deduplicates Vue ecosystem packages.
 * When frappe-ui is installed as a local file: dep, its own node_modules may
 * contain different versions of vue/vue-router that would be bundled as
 * separate module instances, breaking cross-bundle Symbol injection.
 * This plugin forces all such imports to resolve through frappe's node_modules,
 * explicitly targeting the ESM bundler entry so esbuild gets the right file.
 */
function dedup_vue_plugin(frappe_node_modules) {
	const pkgs = [
		"vue",
		"vue-router",
		"@vue/runtime-core",
		"@vue/runtime-dom",
		"@vue/reactivity",
		"@vue/shared",
	];
	const filter = new RegExp(`^(${pkgs.map((p) => p.replace("/", "\\/")).join("|")})$`);

	// Resolve the best ESM bundler entry from a package.json exports field value.
	// Handles both string values and nested condition objects.
	function resolve_export(value, priority = ["default", "import", "browser", "require"]) {
		if (typeof value === "string") return value;
		if (typeof value === "object" && value !== null) {
			for (const cond of priority) {
				if (value[cond] !== undefined) {
					return resolve_export(value[cond], priority);
				}
			}
		}
		return null;
	}

	const resolved_cache = {};
	return {
		name: "dedup-vue",
		setup(build) {
			build.onResolve({ filter }, (args) => {
				if (!resolved_cache[args.path]) {
					try {
						const pkg_dir = path.resolve(frappe_node_modules, args.path);
						const pkg_json = JSON.parse(
							require("fs").readFileSync(path.join(pkg_dir, "package.json"), "utf-8")
						);
						// Prefer exports['.']['import'] → module → main
						const export_entry =
							pkg_json.exports && pkg_json.exports["."]
								? resolve_export(
										pkg_json.exports["."]["import"] || pkg_json.exports["."]
								  )
								: null;
						const rel = export_entry || pkg_json.module || pkg_json.main || "index.js";
						resolved_cache[args.path] = path.resolve(pkg_dir, rel);
					} catch (e) {
						return null; // Let esbuild handle it normally if package not found
					}
				}
				return { path: resolved_cache[args.path] };
			});
		},
	};
}

/**
 * Resolve `frappe-ui` and `frappe-ui/*` imports through the symlink-resolved
 * `realpath` of the linked submodule, then walk the package's `exports` map
 * manually.
 *
 * Why this is still needed even though esbuild 0.14+ understands `exports`:
 * with `"frappe-ui": "link:./frappe-ui"`, yarn places a relative symlink at
 * `node_modules/frappe-ui` whose target esbuild sometimes resolves against
 * the wrong cwd, picking up a stale ../node_modules/frappe-ui/index.js
 * fallback instead of the real `src/index.ts` entry. Realpath-ing first
 * sidesteps that.
 *
 * The `frappe-ui/desk` subpath that this used to be scoped around is gone
 * (we now compile from `frappe-ui` source). The plugin stays because the
 * `link:` symlink edge case applies to the bare `frappe-ui` entry too.
 */
function frappe_ui_plugin(frappe_node_modules) {
	let frappe_ui_dir = null;
	try {
		frappe_ui_dir = require("fs").realpathSync(path.resolve(frappe_node_modules, "frappe-ui"));
	} catch (e) {
		return { name: "frappe-ui-resolve", setup() {} }; // package not present
	}

	const pkg_json = JSON.parse(
		require("fs").readFileSync(path.join(frappe_ui_dir, "package.json"), "utf-8")
	);
	const exports_map = pkg_json.exports || {};

	function resolve_export(value, priority = ["import", "module", "default", "require"]) {
		if (typeof value === "string") return value;
		if (value && typeof value === "object") {
			for (const cond of priority) {
				if (value[cond] !== undefined) return resolve_export(value[cond], priority);
			}
		}
		return null;
	}

	return {
		name: "frappe-ui-resolve",
		setup(build) {
			build.onResolve({ filter: /^frappe-ui(\/|$)/ }, (args) => {
				const sub =
					args.path === "frappe-ui" ? "." : "./" + args.path.slice("frappe-ui/".length);

				// 1. Try the package's exports map first.
				const entry = exports_map[sub];
				if (entry) {
					const rel = resolve_export(entry);
					if (rel) return { path: path.resolve(frappe_ui_dir, rel) };
				}

				// 2. Bare import → `main`/`module` field.
				if (args.path === "frappe-ui") {
					const main = pkg_json.module || pkg_json.main || "index.js";
					return { path: path.resolve(frappe_ui_dir, main) };
				}

				// 3. Fall through to direct file resolution. The package's
				// `exports` map intentionally hides `./src/*` subpaths from
				// external consumers, but Desk islands deliberately deep-import
				// from `frappe-ui/src/components/<X>` so the barrel doesn't drag
				// in components (Calendar, TextEditor) that use Vue-3.4 / TS
				// syntax our pinned `@vue/compiler-sfc@^3.2.26` can't parse.
				// Try the requested path with common file/index resolutions.
				const sub_rel = args.path.slice("frappe-ui/".length); // e.g. src/components/Button
				const candidates = [
					sub_rel + ".ts",
					sub_rel + ".js",
					sub_rel + ".vue",
					path.join(sub_rel, "index.ts"),
					path.join(sub_rel, "index.js"),
					path.join(sub_rel, "index.vue"),
					// Bare file (only if the requested path itself names a file,
					// not a directory).
					sub_rel,
				];
				const fs = require("fs");
				for (const c of candidates) {
					const abs = path.resolve(frappe_ui_dir, c);
					try {
						const st = fs.statSync(abs);
						if (st.isFile()) return { path: abs };
					} catch (_) {
						// ENOENT — try next candidate
					}
				}
				return null;
			});
		},
	};
}

// Resolve postcss-import via tailwindcss (it's a transitive dep we already
// have on disk; saves adding a direct dep). Required by esbuild 0.15+ which
// natively bundles CSS @import directives — without inlining them at the
// PostCSS stage first, esbuild's resolver would try to follow them relative
// to the temp dir the postcss plugin stages files in and ENOENT.
const postcssImport = require(require.resolve("postcss-import", {
	paths: [require.resolve("tailwindcss")],
}));

function build_style_files({ files, outdir, rtl_style = false }) {
	// postcss-import must run FIRST in the postcss chain so it consumes
	// `@import` directives (including ones using sass-importer-style bare
	// specifiers like `frappe/public/...`) before tailwindcss or anything
	// else runs. We point its `path` resolver at the same directories sass
	// uses, so bundle CSS files that did `@import "frappe/public/..."` keep
	// working unchanged on the newer esbuild.
	let plugins = [
		postcssImport({
			path: sass_options.includePaths,
			// CSS @imports inside .scss files are out of scope for postcss-import
			// (sass handles those). Limit to .css files.
			filter: (id) =>
				!id.endsWith(".scss") && !id.endsWith(".sass") && !id.endsWith(".less"),
		}),
	];
	if (rtl_style) {
		plugins.push(rtlcss);
	}

	let build_plugins = [
		ignore_assets,
		build_cleanup_plugin,
		postCssPlugin({
			plugins: plugins,
			sassOptions: sass_options,
		}),
	];

	// Process `@tailwind utilities;` in desk-island CSS bundles.
	// tailwindcss must run before autoprefixer; frappeUIImportant must run last
	// so it stamps !important on the freshly generated scoped utilities.
	plugins.push(tailwindcss(DESK_ISLANDS_TAILWIND_CONFIG));
	plugins.push(require("autoprefixer"));
	plugins.push(frappeUIImportant);
	if (WATCH_MODE) build_plugins.push(watch_plugin);
	return build_or_watch(get_build_options(files, outdir, build_plugins));
}

// As of esbuild 0.17 the `watch`/`incremental` build options and the
// `onRebuild` callback were removed in favour of the context API. In watch
// mode we create a context, run the initial build via rebuild() (so callers
// still get a result with a metafile), and then start watching. Rebuilds are
// handled by `watch_plugin` via the onEnd hook.
async function build_or_watch(options) {
	if (!WATCH_MODE) {
		return esbuild.build(options);
	}
	let context = await esbuild.context(options);
	let result = await context.rebuild();
	await context.watch();
	return result;
}

function get_build_options(files, outdir, plugins) {
	const frappe_node_modules = path.resolve(__dirname, "../node_modules");
	return {
		entryPoints: files,
		entryNames: "[dir]/[name].[hash]",
		target: [ESBUILD_TARGET],
		outdir,
		sourcemap: true,
		bundle: true,
		metafile: true,
		minify: PRODUCTION,
		nodePaths: NODE_PATHS,
		define: {
			"process.env.NODE_ENV": JSON.stringify(PRODUCTION ? "production" : "development"),
			__VUE_OPTIONS_API__: JSON.stringify(true),
			__VUE_PROD_DEVTOOLS__: JSON.stringify(false),
			// Substitute `import.meta.env.*` reads at build time so Vite-style
			// dev/prod gates inside frappe-ui (e.g.
			//   `if (import.meta.env.DEV) console.warn(...)`) keep working
			// under esbuild's es2017 target — where `import.meta` itself is
			// substituted with an empty object and `import.meta.env.DEV` would
			// otherwise crash at runtime.
			//
			// Per esbuild's `define` semantics these key paths replace the
			// whole expression, so `import.meta.env.DEV` becomes the literal
			// value below — no `import.meta` reference survives.
			"import.meta.env.DEV": JSON.stringify(!PRODUCTION),
			"import.meta.env.PROD": JSON.stringify(PRODUCTION),
			"import.meta.env.MODE": JSON.stringify(PRODUCTION ? "production" : "development"),
			"import.meta.env.SSR": JSON.stringify(false),
			// Fallback for code that destructures `import.meta.env` as a whole
			// or reads keys we haven't enumerated above. Anything missing
			// resolves to `undefined`, matching Vite's runtime shape.
			"import.meta.env": JSON.stringify({
				DEV: !PRODUCTION,
				PROD: PRODUCTION,
				MODE: PRODUCTION ? "production" : "development",
				SSR: false,
			}),
		},
		plugins: [
			dedup_vue_plugin(frappe_node_modules),
			frappe_ui_plugin(frappe_node_modules),
			...plugins,
		],
	};
}

// Replaces the old `onRebuild` watch callback (removed in esbuild 0.17). The
// onEnd hook fires after every build, so the first invocation (the initial
// build, whose assets.json is written by execute()) is skipped; subsequent
// rebuilds update assets.json and notify the browser.
const watch_plugin = {
	name: "frappe-watch",
	setup(build) {
		let first_build = true;
		build.onEnd(async (result) => {
			if (first_build) {
				first_build = false;
				return;
			}

			if (result.errors.length) {
				log_error("There was an error during rebuilding changes.");
				log();
				let error = {
					errors: result.errors,
					stack: result.errors.map((e) => e.text).join("\n"),
				};
				log(chalk.dim(error.stack));
				notify_redis({ error });
			} else {
				let { new_assets_json, prev_assets_json } = await write_assets_json(
					result.metafile
				);

				let changed_files;
				if (prev_assets_json) {
					changed_files = get_rebuilt_assets(prev_assets_json, new_assets_json);

					let timestamp = new Date().toLocaleTimeString();
					let message = `${timestamp}: Compiled ${changed_files.length} files...`;
					log(chalk.yellow(message));
					for (let filepath of changed_files) {
						let filename = path.basename(filepath);
						log("    " + filename);
					}
					log();
				}
				notify_redis({ success: true, changed_files });
			}
		});
	},
};

function log_built_assets(results) {
	let outputs = {};
	for (const result of results) {
		outputs = Object.assign(outputs, result.metafile.outputs);
	}
	let column_widths = [60, 20];
	cliui.div(
		{
			text: chalk.cyan.bold("File"),
			width: column_widths[0],
		},
		{
			text: chalk.cyan.bold("Size"),
			width: column_widths[1],
		}
	);
	cliui.div("");

	let output_by_dist_path = {};
	for (let outfile in outputs) {
		if (outfile.endsWith(".map")) continue;
		let data = outputs[outfile];
		outfile = path.resolve(outfile);
		outfile = path.relative(assets_path, outfile);
		let filename = path.basename(outfile);
		let dist_path = outfile.replace(filename, "");
		output_by_dist_path[dist_path] = output_by_dist_path[dist_path] || [];
		output_by_dist_path[dist_path].push({
			name: filename,
			size: (data.bytes / 1000).toFixed(2) + " Kb",
		});
	}

	for (let dist_path in output_by_dist_path) {
		let files = output_by_dist_path[dist_path];
		cliui.div({
			text: dist_path,
			width: column_widths[0],
		});

		for (let i in files) {
			let file = files[i];
			let branch = "";
			if (i < files.length - 1) {
				branch = "├─ ";
			} else {
				branch = "└─ ";
			}
			let color = file.name.endsWith(".js") ? "green" : "blue";
			cliui.div(
				{
					text: branch + chalk[color]("" + file.name),
					width: column_widths[0],
				},
				{
					text: file.size,
					width: column_widths[1],
				}
			);
		}
		cliui.div("");
	}
	log(cliui.toString());
}

// to store previous build's assets.json for comparison
let prev_assets_json;
let curr_assets_json;

async function write_assets_json(metafile) {
	let rtl = false;
	prev_assets_json = curr_assets_json;
	let out = {};
	for (let output in metafile.outputs) {
		let info = metafile.outputs[output];
		let asset_path = "/" + path.relative(sites_path, output);
		if (info.entryPoint) {
			let key = path.basename(info.entryPoint);
			if (key.endsWith(".css") && asset_path.includes("/css-rtl/")) {
				rtl = true;
				key = `rtl_${key}`;
			}
			out[key] = asset_path;
		}
	}

	let { obj: assets_json, path: assets_json_path } = await get_assets_json_path_and_obj(rtl);
	// update with new values
	let new_assets_json = Object.assign({}, assets_json, out);
	curr_assets_json = new_assets_json;

	await fs.promises.writeFile(assets_json_path, JSON.stringify(new_assets_json, null, 4));
	await update_assets_json_in_cache();
	if (argv["save-metafiles"]) {
		// use current timestamp in readable formate as a suffix for filename
		let current_timestamp = new Date().getTime();
		const metafile_name = `meta-${current_timestamp}.json`;
		await fs.promises.writeFile(`${metafile_name}`, JSON.stringify(metafile));
		log(`Saved metafile as ${metafile_name}`);
	}
	return {
		new_assets_json,
		prev_assets_json,
	};
}

async function update_assets_json_in_cache() {
	// Redis won't be present during docker image build
	if (process.env.FRAPPE_DOCKER_BUILD) {
		return;
	}

	// update assets_json cache in redis, so that it can be read directly by python
	let client = get_redis_subscriber("redis_cache");
	// handle error event to avoid printing stack traces
	try {
		await client.connect();
	} catch (e) {
		log_warn("Cannot connect to redis_cache to update assets_json");
	}
	client.del("assets_json", (err) => {
		client.unref();
	});
}

async function get_assets_json_path_and_obj(is_rtl) {
	const file_name = is_rtl ? "assets-rtl.json" : "assets.json";
	const assets_json_path = path.resolve(assets_path, file_name);
	let assets_json;
	try {
		assets_json = await fs.promises.readFile(assets_json_path, "utf-8");
	} catch (error) {
		assets_json = "{}";
	}
	assets_json = JSON.parse(assets_json);
	return { obj: assets_json, path: assets_json_path };
}

function run_build_command_for_apps(apps) {
	let cwd = process.cwd();
	let { execSync } = require("child_process");

	for (let app of apps) {
		if (app === "frappe") continue;

		let root_app_path = path.resolve(apps_path, app);
		let package_json = path.resolve(root_app_path, "package.json");
		let node_modules = path.resolve(root_app_path, "node_modules");

		if (!fs.existsSync(package_json)) {
			continue;
		}

		let { scripts } = require(package_json);
		if (!scripts?.build) {
			continue;
		}

		process.chdir(root_app_path);
		if (!fs.existsSync(node_modules)) {
			log(
				`\nInstalling dependencies for ${chalk.bold(app)} (because node_modules not found)`
			);
			execSync("yarn install --frozen-lockfile", { encoding: "utf8", stdio: "inherit" });
		}

		log("\nRunning build command for", chalk.bold(app));
		execSync("yarn build", { encoding: "utf8", stdio: "inherit" });
	}

	process.chdir(cwd);
}

async function notify_redis({ error, success, changed_files }) {
	// notify redis which in turns tells socketio to publish this to browser
	let subscriber = get_redis_subscriber("redis_queue");
	try {
		await subscriber.connect();
	} catch (e) {
		log_warn("Cannot connect to redis_queue for browser events");
	}

	let payload = null;
	if (error) {
		let formatted = await esbuild.formatMessages(error.errors, {
			kind: "error",
			terminalWidth: 100,
		});
		let stack = error.stack.replace(new RegExp(bench_path, "g"), "");
		payload = {
			error,
			formatted,
			stack,
		};
	}
	if (success) {
		payload = {
			success: true,
			changed_files,
			live_reload: argv["live-reload"],
		};
	}

	await subscriber.publish(
		"events",
		JSON.stringify({
			event: "build_event",
			message: payload,
		})
	);
}

async function open_in_editor() {
	let subscriber = get_redis_subscriber("redis_queue");
	try {
		await subscriber.connect();
	} catch (e) {
		log_warn("Cannot connect to redis_queue for open_in_editor events");
	}
	subscriber.subscribe("open_in_editor", (file) => {
		file = JSON.parse(file);
		let file_path = path.resolve(file.file);
		log("Opening file in editor:", file_path);
		let launch = require("launch-editor");
		launch(`${file_path}:${file.line}:${file.column}`);
	});
}

function get_rebuilt_assets(prev_assets, new_assets) {
	let added_files = [];
	let old_files = Object.values(prev_assets);
	let new_files = Object.values(new_assets);

	for (let filepath of new_files) {
		if (!old_files.includes(filepath)) {
			added_files.push(filepath);
		}
	}
	return added_files;
}
