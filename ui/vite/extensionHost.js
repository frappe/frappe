// Host side of the runtime-extension pipeline: virtual modules re-export the
// shared singletons, and the page's HTML gets an import map pointing their bare
// specifiers at those modules, so a separately built extension's `import 'vue'`
// lands on the exact module instance the host runs. In a build the virtuals
// become emitted entry chunks; in dev they are served at stable `/@id/` URLs,
// which the dev server re-resolves per request — optimizer URL churn stays
// server-side, never in the map.
const SHARED_DEPS = ["vue", "vue-router", "frappe-ui", "@framework/ui"];

const VIRTUAL_PREFIX = "\0shared-dep:";

// How Vite encodes a `\0`-prefixed module id into a servable URL.
const DEV_ID_PREFIX = "/@id/__x00__shared-dep:";

export default function extensionHost() {
	let base = "/";
	let building = false;
	return {
		name: "framework-ui-extension-host",
		configResolved(config) {
			base = config.base;
			building = config.command === "build";
		},
		buildStart() {
			if (!building) return;
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
			if (id.startsWith(DEV_ID_PREFIX)) return VIRTUAL_PREFIX + id.slice(DEV_ID_PREFIX.length);
		},
		load(id) {
			if (!id.startsWith(VIRTUAL_PREFIX)) return;
			return entrySource(id.slice(VIRTUAL_PREFIX.length));
		},
		transformIndexHtml: {
			order: "post",
			handler(html, ctx) {
				if (building && !ctx.bundle) return html;
				const imports = ctx.bundle ? builtImports(ctx.bundle, base) : devImports();
				return { html, tags: [importMapTag(imports)] };
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

function builtImports(bundle, base) {
	const imports = {};
	for (const dep of SHARED_DEPS) {
		const chunk = Object.values(bundle).find(
			(output) => output.facadeModuleId === VIRTUAL_PREFIX + dep,
		);
		if (!chunk) throw new Error(`no entry chunk emitted for ${dep}`);
		imports[dep] = base + chunk.fileName;
	}
	return imports;
}

function devImports() {
	return Object.fromEntries(SHARED_DEPS.map((dep) => [dep, DEV_ID_PREFIX + dep]));
}

function importMapTag(imports) {
	return {
		tag: "script",
		attrs: { type: "importmap" },
		children: JSON.stringify({ imports }, null, 2),
		injectTo: "head-prepend",
	};
}
