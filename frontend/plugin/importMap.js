// The document's import map: the names a stored Client Script may import, each pointed at a chunk
// of this bundle. The names are the manifest's `import_map` entries, checked in Python before vite starts.

import { join } from "node:path";

const VIRTUAL_PREFIX = "\0published:";

export default function importMap(manifest) {
	// A manifest from before the hook has no `import_map` at all, not even frappe's four names.
	if (!manifest.some((entry) => entry.import_map)) {
		throw new Error(
			"manifest.json predates the import_map hook; run `bench build --app frappe`."
		);
	}
	const published = publishedTargets(manifest);
	const names = Object.keys(published);
	let base = "/";
	let building = false;
	let logger = console;
	return {
		name: "frappe-import-map",
		configResolved(config) {
			base = config.base;
			building = config.command === "build";
			logger = config.logger;
		},
		buildStart() {
			if (!building) return;
			// One entry chunk per name; rolldown hoists what the shell also uses into shared chunks.
			for (const name of names) {
				this.emitFile({
					type: "chunk",
					id: VIRTUAL_PREFIX + name,
					name: chunkName(name),
					preserveSignature: "strict",
				});
			}
		},
		resolveId(id) {
			if (id.startsWith(VIRTUAL_PREFIX)) return id;
		},
		load(id) {
			if (!id.startsWith(VIRTUAL_PREFIX)) return;
			// `export *` forwards named exports only: a published file's default export is not published.
			return `export * from ${JSON.stringify(published[id.slice(VIRTUAL_PREFIX.length)])};`;
		},
		generateBundle(_options, bundle) {
			// Every published chunk's stylesheets join every cold load, so the author sees the cost.
			for (const line of sizeReport(publishedChunks(bundle, names), bundle))
				logger.info(line);
		},
		transformIndexHtml: {
			order: "post",
			handler(html, ctx) {
				if (building && !ctx.bundle) return html;
				if (!ctx.bundle) return { html, tags: [importMapTag(devImports(names))] };
				const chunks = publishedChunks(ctx.bundle, names);
				return {
					html,
					tags: [
						importMapTag(builtImports(chunks, base)),
						...stylesheetTags(chunks, ctx.bundle, base, html),
					],
				};
			},
		},
	};
}

/** Each published name's module, in `apps.txt` order; a file value is rooted at the app's source dir. */
export function publishedTargets(manifest) {
	const targets = {};
	for (const { source_dir, import_map } of manifest) {
		for (const [name, value] of Object.entries(import_map ?? {})) {
			targets[name] = isFileValue(value) ? join(source_dir, value) : value;
		}
	}
	return targets;
}

/** The manifest's rule: a `.` or `/` prefix is a file, anything else a declared package. */
export function isFileValue(value) {
	return value.startsWith(".") || value.startsWith("/");
}

export function chunkName(name) {
	return "published-" + name.replaceAll("@", "").replaceAll("/", "-");
}

/** Each published name's emitted chunk; a name with no chunk fails the build, not the page. */
export function publishedChunks(bundle, names) {
	const chunks = {};
	for (const name of names) {
		const chunk = Object.values(bundle).find(
			(output) => output.facadeModuleId === VIRTUAL_PREFIX + name
		);
		if (!chunk) throw new Error(`no entry chunk emitted for ${name}`);
		chunks[name] = chunk;
	}
	return chunks;
}

export function builtImports(chunks, base) {
	return Object.fromEntries(
		Object.entries(chunks).map(([name, chunk]) => [name, base + chunk.fileName])
	);
}

/** The stylesheets a set of chunks brings in, their static imports' included, walked once. */
export function reachableCss(chunks, bundle) {
	const files = new Set();
	const seen = new Set();
	const visit = (chunk) => {
		if (!chunk || seen.has(chunk.fileName)) return;
		seen.add(chunk.fileName);
		for (const file of chunk.viteMetadata?.importedCss ?? []) files.add(file);
		for (const imported of chunk.imports ?? []) visit(bundle[imported]);
	};
	Object.values(chunks).forEach(visit);
	return [...files];
}

/** An emitted chunk's CSS, its static imports' included, is written but linked by nobody. */
export function stylesheetTags(chunks, bundle, base, html = "") {
	return reachableCss(chunks, bundle)
		.filter((file) => !html.includes(base + file))
		.map((file) => ({
			tag: "link",
			attrs: { rel: "stylesheet", crossorigin: true, href: base + file },
			injectTo: "head",
		}));
}

/** One line per published name: its own chunk, and the CSS it reaches. */
export function sizeReport(chunks, bundle) {
	return Object.entries(chunks).map(([name, chunk]) => {
		const css = reachableCss({ [name]: chunk }, bundle).reduce(
			(total, file) => total + (bundle[file]?.source?.length ?? 0),
			0
		);
		return (
			`published ${name.padEnd(24)} ${kilobytes(chunk.code?.length ?? 0)} js` +
			(css ? ` + ${kilobytes(css)} css` : "")
		);
	});
}

function kilobytes(bytes) {
	return `${(bytes / 1000).toFixed(2)} kB`;
}

/** The dev server re-resolves a virtual id per request, so optimizer churn never reaches the map. */
export function devImports(names) {
	return Object.fromEntries(names.map((name) => [name, "/@id/__x00__published:" + name]));
}

export function importMapTag(imports) {
	return {
		tag: "script",
		attrs: { type: "importmap" },
		children: JSON.stringify({ imports }, null, 2),
		// Ahead of the module script and its preloads: a map after any module is ignored.
		injectTo: "head-prepend",
	};
}
