// The bare name `vue` is the runtime build for every importer, the file the shell's
// `import "vue"` already gets. A CommonJS package such as vuedraggable would `require` the
// full build, whose template compiler would compile in the browser any template the compile
// step missed. The exact match leaves `vue/...` subpaths alone; see CLAUDE.md, "Imports".

import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

export default {
	find: /^vue$/,
	replacement: join(here, "..", "node_modules", "vue", "dist", "vue.runtime.esm-bundler.js"),
};
