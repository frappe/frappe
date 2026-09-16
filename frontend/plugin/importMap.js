// The document's import map: the bare names a stored Client Script may import, each pointed at
// a chunk of this bundle. A blob-URL module resolves `import "vue"` through this map or not at all.

export const PUBLISHED = ["vue", "vue-router", "frappe-ui", "@framework/ui"];

const VIRTUAL_PREFIX = "\0published:";

export default function importMap(names = PUBLISHED) {
	let base = "/";
	let building = false;
	return {
		name: "frappe-import-map",
		configResolved(config) {
			base = config.base;
			building = config.command === "build";
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
			// `export *` forwards named exports only; none of the published packages has a default export.
			return `export * from "${id.slice(VIRTUAL_PREFIX.length)}";`;
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

export function chunkName(name) {
	return "published-" + name.replaceAll("@", "").replaceAll("/", "-");
}

/** Each published name's emitted chunk; a name with no chunk fails the build, not the page. */
export function publishedChunks(bundle, names = PUBLISHED) {
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

/** An emitted chunk's CSS, its static imports' included, is written but linked by nobody. */
export function stylesheetTags(chunks, bundle, base, html = "") {
	const files = new Set();
	const seen = new Set();
	const visit = (chunk) => {
		if (!chunk || seen.has(chunk.fileName)) return;
		seen.add(chunk.fileName);
		for (const file of chunk.viteMetadata?.importedCss ?? []) files.add(file);
		for (const imported of chunk.imports ?? []) visit(bundle[imported]);
	};
	Object.values(chunks).forEach(visit);
	return [...files]
		.filter((file) => !html.includes(base + file))
		.map((file) => ({
			tag: "link",
			attrs: { rel: "stylesheet", crossorigin: true, href: base + file },
			injectTo: "head",
		}));
}

/** The dev server re-resolves a virtual id per request, so optimizer churn never reaches the map. */
export function devImports(names = PUBLISHED) {
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
