// Compiles each `template:` string in an app's `.js` and `.ts` files with the server's module.

import { realpathSync } from "node:fs";
import { compileScript, TEMPLATE_KEY } from "../templateCompiler/compileScript.mjs";

// No query: a `.vue` file's script block arrives as `Field.vue?vue&type=script&lang.ts`.
const APP_FILE = /^[^?]*\.[jt]s$/;

export default function templateStrings() {
	const compile = { name: "frappe-template-strings", transform };
	return {
		...compile,
		// Before vite strips types, so an error's line is the author's line in a `.ts` file.
		enforce: "pre",
		// In dev, `@framework/ui` is pre-bundled, and vite plugins do not run inside the pre-bundle.
		config: () => ({ optimizeDeps: { rolldownOptions: { plugins: [compile] } } }),
	};
}

function transform(source, id) {
	if (!APP_FILE.test(id) || !TEMPLATE_KEY.test(source) || !isAppFile(id)) return null;
	const { code, map, errors } = compileScript(source, { filename: id });
	if (errors.length) this.error(buildError(id, errors));
	if (code === source) return null;
	return { code, map };
}

// By the real path: `@framework/ui` arrives through a link in `node_modules`.
function isAppFile(id) {
	return !id.includes("/node_modules/") || !realpathSync(id).includes("/node_modules/");
}

function buildError(id, errors) {
	const [first] = errors;
	const lines = errors.map((error) => `${id}:${error.line}:${error.column} ${error.message}`);
	return {
		message: `Template error\n${lines.join("\n")}`,
		id,
		loc: { file: id, line: first.line, column: first.column - 1 },
	};
}
