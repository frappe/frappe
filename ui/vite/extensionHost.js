// Host side of the runtime-extension pipeline: the build emits entry chunks
// re-exporting the shared singletons, and the page's HTML gets an import map
// pointing their bare specifiers at those chunks, so a separately built
// extension's `import 'vue'` lands on the exact module instance the host runs.
const SHARED_DEPS = ["vue", "vue-router", "frappe-ui", "@framework/ui"];

const VIRTUAL_PREFIX = "\0shared-dep:";

export default function extensionHost() {
	let base = "/";
	return {
		name: "framework-ui-extension-host",
		apply: "build",
		configResolved(config) {
			base = config.base;
		},
		buildStart() {
			for (const dep of SHARED_DEPS) {
				this.emitFile({
					type: "chunk",
					id: VIRTUAL_PREFIX + dep,
					name: "shared-" + dep.replace("/", "-").replace("@", ""),
					preserveSignature: "strict",
				});
			}
		},
		resolveId(id) {
			if (id.startsWith(VIRTUAL_PREFIX)) return id;
		},
		load(id) {
			if (!id.startsWith(VIRTUAL_PREFIX)) return;
			return entrySource(id.slice(VIRTUAL_PREFIX.length));
		},
		transformIndexHtml: {
			order: "post",
			handler(html, ctx) {
				if (!ctx.bundle) return html;
				return { html, tags: [importMapTag(ctx.bundle, base)] };
			},
		},
	};
}

// `export *` forwards named exports only; none of the four ships a default
// export today. The map covers bare roots only, so the experimental barrel is
// folded into the bare specifier — subpath imports cannot resolve through it.
function entrySource(dep) {
	if (dep === "@framework/ui")
		return `export * from "@framework/ui";\nexport * from "@framework/ui/experimental";`;
	return `export * from "${dep}";`;
}

function importMapTag(bundle, base) {
	const imports = {};
	for (const dep of SHARED_DEPS) {
		const chunk = Object.values(bundle).find(
			(output) => output.facadeModuleId === VIRTUAL_PREFIX + dep,
		);
		if (!chunk) throw new Error(`no entry chunk emitted for ${dep}`);
		imports[dep] = base + chunk.fileName;
	}
	return {
		tag: "script",
		attrs: { type: "importmap" },
		children: JSON.stringify({ imports }, null, 2),
		injectTo: "head-prepend",
	};
}
