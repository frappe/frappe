// Builds Flow's chat as the frappe.flow.chat island, which the launcher's panel and the
// /flow page both mount. Output: sites/assets/frappe/dist/flow/, registered in assets.json.
import { fileURLToPath } from "node:url";

import { buildIslands } from "@framework/ui/vite/island";

import containerQueries from "./container-queries.mjs";

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
