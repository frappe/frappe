const path = require("path");
const fs = require("fs");
const { pathToFileURL, fileURLToPath } = require("url");
const postcss = require("postcss");
const autoprefixer = require("autoprefixer");
const { apps_path, app_list } = require("./utils");

// sass-embedded runs the native dart-sass compiler out of process, which is
// 2-4x faster than the pure-JS `sass` package. Fall back to `sass` on
// platforms without a prebuilt native binary; both expose the same modern
// compile API.
let sass;
try {
	sass = require("sass-embedded");
} catch (e) {
	sass = require("sass");
}

const app_paths = app_list.map((app) => path.resolve(apps_path, app));
const node_modules_paths = app_paths
	.map((app_path) => path.resolve(app_path, "node_modules"))
	.filter(fs.existsSync);

// Resolves webpack-style "~package/..." imports against every app's
// node_modules. Returns an extension-less file: URL; sass applies its own
// partial/extension/index resolution to whatever we return, so the probe only
// has to find which node_modules directory can satisfy the import.
const tilde_importer = {
	findFileUrl(url) {
		if (!url.startsWith("~")) return null;
		url = url.slice(1);
		for (const base of node_modules_paths) {
			const candidate = path.join(base, url);
			if (sass_target_exists(candidate)) {
				return pathToFileURL(candidate);
			}
		}
		return null;
	},
};

function sass_target_exists(base) {
	let stat = fs.statSync(base, { throwIfNoEntry: false });
	if (stat?.isFile()) return true;
	const dir = path.dirname(base);
	const name = path.basename(base);
	for (const prefix of ["", "_"]) {
		for (const ext of [".scss", ".sass", ".css"]) {
			if (fs.existsSync(path.join(dir, prefix + name + ext))) return true;
		}
	}
	if (stat?.isDirectory()) {
		for (const index of ["_index.scss", "_index.sass", "index.scss", "index.sass"]) {
			if (fs.existsSync(path.join(base, index))) return true;
		}
	}
	return false;
}

const sass_options = {
	loadPaths: [...node_modules_paths, ...app_paths],
	importers: [tilde_importer],
	quietDeps: true,
	// Frappe's stylesheets still use @import and pre-module built-ins;
	// migrating them is a separate project and the warning spam would drown
	// real problems. The feature-detect keeps the fallback `sass` (which may
	// predate these deprecation ids) working.
	silenceDeprecations: ["import", "global-builtin", "color-functions", "if-function"].filter(
		(id) => sass.deprecations?.[id]
	),
	sourceMap: true,
	sourceMapIncludeSources: true,
};

module.exports = {
	name: "frappe-style",
	setup(build) {
		build.onLoad({ filter: /\.(scss|sass)$/ }, async (args) => {
			const result = await sass.compileAsync(args.path, sass_options);
			const watch_files = result.loadedUrls
				.filter((url) => url.protocol === "file:")
				.map((url) => fileURLToPath(url));
			const { contents, warnings } = await postprocess(
				result.css,
				args.path,
				result.sourceMap,
				watch_files
			);
			return {
				contents,
				loader: "css",
				resolveDir: path.dirname(args.path),
				watchFiles: watch_files,
				warnings,
			};
		});

		// Plain CSS — both .bundle.css entries and .css files that sass emitted
		// as plain-CSS @imports (which esbuild resolves and inlines) — still
		// goes through autoprefixer, like every stylesheet in the bundle.
		build.onLoad({ filter: /\.css$/ }, async (args) => {
			const source = await fs.promises.readFile(args.path, "utf-8");
			const watch_files = [args.path];
			const { contents, warnings } = await postprocess(source, args.path, null, watch_files);
			return {
				contents,
				loader: "css",
				resolveDir: path.dirname(args.path),
				watchFiles: watch_files,
				warnings,
			};
		});

		// Kept only for apps that still ship a .bundle.less (e.g. lms); sass is
		// the supported style language.
		build.onLoad({ filter: /\.less$/ }, async (args) => {
			const less = require("less");
			const source = await fs.promises.readFile(args.path, "utf-8");
			const result = await less.render(source, { filename: args.path });
			const watch_files = [args.path, ...(result.imports || [])];
			const { contents, warnings } = await postprocess(
				result.css,
				args.path,
				null,
				watch_files
			);
			return {
				contents,
				loader: "css",
				resolveDir: path.dirname(args.path),
				watchFiles: watch_files,
				warnings,
			};
		});
	},
};

async function postprocess(css, from, prev_map, watch_files) {
	const result = await postcss([autoprefixer]).process(css, {
		from,
		map: { prev: prev_map || undefined, inline: true, sourcesContent: true },
	});
	for (const message of result.messages) {
		if (message.type === "dependency") {
			watch_files.push(message.file);
		}
	}
	return { contents: result.css, warnings: find_leftover_imports(css, from) };
}

function is_external_url(url) {
	return (
		url.startsWith("http:") ||
		url.startsWith("https:") ||
		url.startsWith("//") ||
		url.startsWith("data:") ||
		url.startsWith("/assets/")
	);
}

// Sass emits `@import "...css"` as a plain-CSS import (it never consults
// importers for URLs ending in .css); esbuild then resolves and inlines those
// from the compiled bundle. An import esbuild can't resolve either would
// silently ship a broken @import to browsers; flag it.
function find_leftover_imports(css, from) {
	const warnings = [];
	const resolve_dir = path.dirname(from);
	const import_re = /^@import\s+(?:url\()?\s*["']?([^"'()\s;]+)/gm;
	let match;
	while ((match = import_re.exec(css))) {
		const url = match[1];
		if (is_external_url(url)) continue;
		// esbuild resolves and inlines @imports left in the compiled CSS (its
		// nodePaths include every app directory); only flag the ones it won't
		// be able to find.
		const candidates = [resolve_dir, ...node_modules_paths, ...app_paths];
		if (candidates.some((base) => fs.existsSync(path.resolve(base, url)))) continue;
		warnings.push({
			text: `"${url}" was not inlined and will reach the browser as a plain CSS @import. Sass does not inline @import URLs ending in ".css"; drop the extension (e.g. @import "${url.replace(
				/\.css$/,
				""
			)}") to inline the file.`,
			location: { file: from },
		});
	}
	return warnings;
}
