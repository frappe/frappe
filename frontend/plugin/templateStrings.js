// Compiles each `template:` string in an app's `.js` and `.ts` files with the module the server runs.

import { realpathSync } from "node:fs";
import { compileScript, TEMPLATE_KEY } from "../templateCompiler/compileScript.mjs";

// No query: a `.vue` file's script block arrives as `Field.vue?vue&type=script&lang.ts`.
const APP_FILE = /^[^?]*\.[jt]s$/;

export default function templateStrings() {
	return {
		name: "frappe-template-strings",
		// Before vite strips types, so an error's line is the author's line in a `.ts` file.
		enforce: "pre",
		transform(source, id) {
			if (!APP_FILE.test(id) || !TEMPLATE_KEY.test(source) || !isAppFile(id)) return null;
			const { code, map, errors } = compileScript(source, { filename: id });
			if (errors.length) this.error(buildError(id, errors));
			if (code === source) return null;
			return { code, map };
		},
	};
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
