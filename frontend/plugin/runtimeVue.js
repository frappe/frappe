// The bare name `vue`, exact match, is Vue's runtime build for every importer, CommonJS ones too.
// Subpaths such as `vue/...` stay unaliased; see CLAUDE.md, "Imports".

import { createRequire } from "node:module";

export default {
	find: /^vue$/,
	replacement: createRequire(import.meta.url).resolve("vue/dist/vue.runtime.esm-bundler.js"),
};
