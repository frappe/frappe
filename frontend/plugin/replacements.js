// Reads a folder's `pages.json` and `pages/` into replacement pages for a doctype's record or
// list address, with a warning for each broken declaration and each clash across apps.

import { readFileSync } from "node:fs";
import { basename, join } from "node:path";
import { files, isFile } from "./folders.js";

export const STANDARD_PAGES = ["record", "list"];

/** The pages a folder's `pages.json` names from the `pages/` folder beside it. */
export function declaredPages(folder, declarer, benchApps) {
	const pagesRoot = join(folder, "pages");
	const pageNames = files(pagesRoot).map((file) => basename(file, ".js"));
	const warnings = handlerFileWarnings(folder, pageNames, declarer.foreign);

	const path = join(folder, "pages.json");
	const read = readDeclaration(path);
	warnings.push(...read.warnings);
	const found = [];
	for (const [key, value] of Object.entries(read.declaration)) {
		const declared = keyEntries(key, value, pageNames, benchApps);
		warnings.push(...declared.warnings.map((warning) => `[frappe] ${path}: ${warning}.`));
		for (const { page, apps } of declared.entries) {
			const file = join(pagesRoot, `${page}.js`);
			found.push({ ...declarer, key, page, ...(apps && { apps }), file });
		}
	}
	return { found, warnings, declaration: isFile(path) ? path : null };
}

/** One warning per doctype, key and app that more than one app replaces; "every app" is one more. */
export function clashes(replacements) {
	const byTarget = new Map();
	for (const entry of replacements) {
		for (const app of entry.apps ?? [null]) {
			const target = `${entry.doctype}'s ${entry.key} page${app ? ` in ${app}` : ""}`;
			byTarget.set(target, [...(byTarget.get(target) ?? []), entry]);
		}
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

/**
 * A key's entries, each `{ page, apps }` with `apps` null for every app. A malformed or
 * ambiguous key gives none; an app not on the bench is kept, so it applies once installed.
 */
function keyEntries(key, value, pageNames, benchApps) {
	const entries = typeof value === "string" ? [{ page: value }] : [value].flat();
	const problem = keyProblem(key, value, entries, pageNames);
	if (problem) return { entries: [], warnings: [`${problem}; that key is ignored`] };

	const warnings = [];
	const scoped = [];
	for (const { page, apps } of entries) {
		if (!apps) {
			scoped.push({ page, apps: null });
			continue;
		}
		if (!apps.length) {
			warnings.push(
				`"${key}" gives "${page}" an empty "apps", and "apps" never means every app; that entry is ignored`
			);
			continue;
		}
		const named = [...new Set(apps)];
		for (const app of named.filter((app) => !benchApps.includes(app)))
			warnings.push(
				`"${key}" names app "${app}" for "${page}", but it is not on the bench; it applies there once that app is installed`
			);
		scoped.push({ page, apps: named });
	}
	return { entries: scoped, warnings };
}

function keyProblem(key, value, entries, pageNames) {
	if (!STANDARD_PAGES.includes(key))
		return `unknown key ${JSON.stringify(key)}, only "record" and "list" are read`;
	if (!entries.length) return `"${key}" is an empty list`;
	for (const entry of entries) {
		const problem = entryProblem(key, entry, pageNames);
		if (problem) return problem;
	}
	return scopeClash(key, entries);
}

function entryProblem(key, entry, pageNames) {
	if (entry === null || typeof entry !== "object" || Array.isArray(entry))
		return `"${key}" is not a page name, a { "page", "apps" } entry or a list of entries`;
	const unknown = Object.keys(entry).find((field) => field !== "page" && field !== "apps");
	if (unknown) return `"${key}" has an entry with the unknown field "${unknown}"`;
	const { page, apps } = entry;
	if (typeof page !== "string") return `"${key}" has an entry with no page name`;
	if (
		apps !== undefined &&
		!(Array.isArray(apps) && apps.every((app) => typeof app === "string"))
	)
		return `"${key}" gives "${page}" an "apps" that is not a list of app names`;
	if (STANDARD_PAGES.includes(page))
		return `"${key}" names "${page}", a name reserved for the standard pages`;
	if (!pageNames.includes(page))
		return `"${key}" names "${page}", but there is no pages/${page}.js`;
	return null;
}

/** Two entries for every app, or one app named in two entries: no entry can win. */
function scopeClash(key, entries) {
	if (entries.filter((entry) => !entry.apps).length > 1)
		return `"${key}" has more than one entry with no "apps"`;
	const named = new Set();
	for (const { apps = [] } of entries) {
		for (const app of new Set(apps)) {
			if (named.has(app)) return `"${key}" names app "${app}" in more than one entry`;
			named.add(app);
		}
	}
	return null;
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
