const path = require("path");
const fs = require("fs");
const { fileURLToPath } = require("url");
const { sass, sass_options, app_paths, node_modules_paths } = require("./sass_compiler");

// Plain .css files are not handled here on purpose: esbuild's native CSS
// loader already resolves @imports (via nodePaths), watches the files, and
// errors on unresolvable imports.
module.exports = {
	name: "frappe-style",
	setup(build) {
		build.onLoad({ filter: /\.(scss|sass)$/ }, async (args) => {
			const result = await sass.compileAsync(args.path, sass_options);
			const watch_files = result.loadedUrls
				.filter((url) => url.protocol === "file:")
				.map((url) => fileURLToPath(url));
			return {
				contents: with_inline_sourcemap(result.css, result.sourceMap),
				loader: "css",
				resolveDir: path.dirname(args.path),
				watchFiles: watch_files,
				warnings: find_leftover_imports(result.css, args.path),
			};
		});

		// Kept only for apps that still ship a .bundle.less (e.g. lms); sass is
		// the supported style language.
		build.onLoad({ filter: /\.less$/ }, async (args) => {
			const less = require("less");
			const source = await fs.promises.readFile(args.path, "utf-8");
			const result = await less.render(source, { filename: args.path });
			return {
				contents: result.css,
				loader: "css",
				resolveDir: path.dirname(args.path),
				watchFiles: [args.path, ...(result.imports || [])],
				warnings: find_leftover_imports(result.css, args.path),
			};
		});
	},
};

// esbuild picks up inline source maps from loaded contents and chains them
// into the final .css.map; sources arrive as file: URLs which devtools (and
// esbuild's relative-path rewriting) expect as plain paths.
function with_inline_sourcemap(css, map) {
	if (!map) return css;
	map.sources = map.sources.map((source) =>
		source.startsWith("file:") ? fileURLToPath(source) : source
	);
	const encoded = Buffer.from(JSON.stringify(map)).toString("base64");
	return `${css}\n/*# sourceMappingURL=data:application/json;charset=utf-8;base64,${encoded} */\n`;
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
