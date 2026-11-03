// Builds Flow's chat as the frappe.flow.chat island, which the launcher's panel and the
// /flow page both mount. Output: sites/assets/frappe/dist/flow/, registered in assets.json.
import { fileURLToPath } from "node:url";

import { buildIslands } from "@framework/ui/vite/island";

// frappe-ui's `exports` map hides its source; the core components import it by path
const frappeUISource = fileURLToPath(new URL("./node_modules/frappe-ui/src", import.meta.url));
const sourceImports = {
	name: "frappe-ui-source",
	enforce: "pre",
	resolveId(source, importer) {
		if (source.startsWith("frappe-ui/src/"))
			return this.resolve(frappeUISource + source.slice("frappe-ui/src".length), importer, {
				skipSelf: true,
			});
	},
};

// Tailwind's breakpoints ask the window's width; in a panel beside a page the island's own width
// is what counts, so width-only media queries become container queries on the island's host
const WIDTH_QUERY = /@media\s*(not all and\s*)?(\((?:min|max)-width:\s*[\d.]+px\))\s*\{/g;
const containerQueries = {
	name: "island-container-queries",
	enforce: "post",
	generateBundle(_options, bundle) {
		for (const asset of Object.values(bundle))
			if (asset.type === "asset" && asset.fileName.endsWith(".css"))
				asset.source = String(asset.source).replace(
					WIDTH_QUERY,
					(_match, not, query) => `@container ${not ? "not " : ""}${query}{`
				);
	},
};

// the island's one entry holds its code, and CodeField, loaded later, imports from it. Without
// this, Rollup moves the code into a chunk behind a stub entry, which the launcher's prefetch of
// the entry would miss
const wholeEntry = {
	name: "island-whole-entry",
	config: () => ({ build: { rollupOptions: { preserveEntrySignatures: "allow-extension" } } }),
};

await buildIslands({
	app: "frappe",
	root: import.meta.dirname,
	// framework's own islands own frappe/dist/island
	subdir: "flow",
	entries: { "frappe.flow.chat": "frontend/src/island.js" },
	budget: 1.5 * 1024 * 1024,
	plugins: [sourceImports, containerQueries, wholeEntry],
	production: process.argv.includes("--production"),
	watch: process.argv.includes("--watch"),
});
