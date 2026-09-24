// Reads a folder's `pages.json` and `pages/` into replacement pages for a doctype's record or
// list address, with a warning for each broken declaration and each clash across apps.

import { readFileSync } from "node:fs";
import { basename, join } from "node:path";
import { files, isFile } from "./folders.js";

export const STANDARD_PAGES = ["record", "list"];

/** The pages a folder's `pages.json` names from the `pages/` folder beside it. */
export function declaredPages(folder, declarer) {
	const pagesRoot = join(folder, "pages");
	const pageNames = files(pagesRoot).map((file) => basename(file, ".js"));
	const warnings = handlerFileWarnings(folder, pageNames, declarer.foreign);

	const path = join(folder, "pages.json");
	const read = readDeclaration(path);
	warnings.push(...read.warnings);
	const found = [];
	for (const [key, page] of Object.entries(read.declaration)) {
		const problem = declarationProblem(key, page, pageNames);
		if (problem) {
			warnings.push(`[frappe] ${path}: ${problem}; that key is ignored.`);
			continue;
		}
		found.push({ ...declarer, key, page, file: join(pagesRoot, `${page}.js`) });
	}
	return { found, warnings, declaration: isFile(path) ? path : null };
}

/** One warning per doctype and key that more than one app replaces. */
export function clashes(replacements) {
	const byTarget = new Map();
	for (const entry of replacements) {
		const target = `${entry.doctype}'s ${entry.key} page`;
		byTarget.set(target, [...(byTarget.get(target) ?? []), entry]);
	}

	const warnings = [];
	for (const [target, entries] of byTarget) {
		if (new Set(entries.map((entry) => entry.app)).size < 2) continue;
		const who = entries.map((entry) => `${entry.app} (${entry.file})`).join(", ");
		warnings.push(
			`[frappe] ${target} is replaced by more than one app: ${who}. The owner's comes first, ` +
				`then custom/ ones in the site's app order, and the last one wins at runtime.`
		);
	}
	return warnings;
}

/** A `.js` file beside `pages/` is a page's reserved handler file or, under `custom/`, a stray. */
function handlerFileWarnings(folder, pageNames, foreign) {
	const warnings = [];
	for (const handler of files(folder)) {
		const name = basename(handler, ".js");
		if (STANDARD_PAGES.includes(name)) continue;

		const file = join(folder, handler);
		if (pageNames.includes(name)) {
			warnings.push(
				`[frappe] ${file} is reserved for the handlers of pages/${handler}; it is ignored.`
			);
		} else if (foreign) {
			warnings.push(`[frappe] ${file} has no pages/${handler} beside it; it is ignored.`);
		}
	}
	return warnings;
}

/** A `pages.json` as an object; `{}` if absent or unreadable. */
function readDeclaration(path) {
	if (!isFile(path)) return { declaration: {}, warnings: [] };

	let declaration;
	try {
		declaration = JSON.parse(readFileSync(path, "utf-8"));
	} catch {
		const warning = `[frappe] ${path} is not valid JSON; the whole file is ignored.`;
		return { declaration: {}, warnings: [warning] };
	}
	if (declaration === null || typeof declaration !== "object" || Array.isArray(declaration)) {
		const warning = `[frappe] ${path} is not a JSON object; the whole file is ignored.`;
		return { declaration: {}, warnings: [warning] };
	}
	return { declaration, warnings: [] };
}

function declarationProblem(key, page, pageNames) {
	if (!STANDARD_PAGES.includes(key))
		return `unknown key ${JSON.stringify(key)}, only "record" and "list" are read`;
	if (typeof page !== "string") return `"${key}" is not a page name`;
	if (STANDARD_PAGES.includes(page))
		return `"${key}" names "${page}", a name reserved for the standard pages`;
	if (!pageNames.includes(page))
		return `"${key}" names "${page}", but there is no pages/${page}.js`;
	return null;
}
