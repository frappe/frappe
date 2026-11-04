// Reads a folder's `pages.json` and `pages/` into replacement pages for a doctype's record or
// a view type's address, and each page's handler file, with a warning for each broken declaration, each
// stray handler file and each clash across apps.

import { readFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { files, isFile } from "./folders.js";

export const STANDARD_PAGES = ["record", "list"];
/** Not a file: `{"record": "dialog"}` opens the doctype's records in the record dialog. */
export const DIALOG_PAGE = "dialog";

/** The keys a `pages.json` may use: the standard pages, and each view type's name in lower case. */
export function pageKeys(viewTypes) {
	return new Set([...STANDARD_PAGES, ...viewTypes.map((entry) => entry.type.toLowerCase())]);
}

/** One warning per `pages.json` and key that `keys` does not hold. */
export function unknownKeys(replacements, keys) {
	const warnings = new Set();
	for (const { key, file } of replacements.filter((entry) => !keys.has(entry.key)))
		warnings.add(
			`[frappe] ${join(dirname(dirname(file)), "pages.json")}: unknown key ${JSON.stringify(
				key
			)}, ` +
				`only "record" and a view type's name in lower case are read; that key is ignored.`
		);
	return [...warnings];
}

/** The pages a folder's `pages.json` names from the `pages/` folder beside it, and their handler files. */
export function declaredPages(folder, declarer, benchApps) {
	const pagesRoot = join(folder, "pages");
	const pageNames = files(pagesRoot).map((file) => basename(file, ".js"));

	const path = join(folder, "pages.json");
	const read = readDeclaration(path);
	const warnings = [...read.warnings];
	const found = [];
	const dialogs = [];
	for (const [key, value] of Object.entries(read.declaration)) {
		const declared = keyEntries(key, value, pageNames, benchApps);
		warnings.push(...declared.warnings.map((warning) => `[frappe] ${path}: ${warning}.`));
		for (const { page, apps, body } of declared.entries) {
			if (page === DIALOG_PAGE) {
				const file = body && join(pagesRoot, `${body}.js`);
				dialogs.push({ ...declarer, ...(apps && { apps }), ...(file && { body, file }) });
				continue;
			}
			const file = join(pagesRoot, `${page}.js`);
			found.push({ ...declarer, key, page, ...(apps && { apps }), file });
		}
	}
	const declared = new Set(found.map((entry) => entry.page));
	const handlers = handlerFiles(folder, pageNames, declared, declarer);
	warnings.unshift(...handlers.warnings);
	if (pageNames.includes(DIALOG_PAGE))
		warnings.unshift(
			`[frappe] ${join(
				pagesRoot,
				`${DIALOG_PAGE}.js`
			)}: "${DIALOG_PAGE}" is a reserved page name, so this file is ignored.`
		);
	return {
		found,
		dialogs,
		pageScripts: handlers.pageScripts,
		warnings,
		declaration: isFile(path) ? path : null,
	};
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
	for (const { page, apps, body } of entries) {
		if (!apps) {
			scoped.push({ page, apps: null, body });
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
		scoped.push({ page, apps: named, body });
	}
	return { entries: scoped, warnings };
}

function keyProblem(key, value, entries, pageNames) {
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
	const unknown = Object.keys(entry).find((field) => !["page", "apps", "body"].includes(field));
	if (unknown) return `"${key}" has an entry with the unknown field "${unknown}"`;
	const { page, apps, body } = entry;
	if (typeof page !== "string") return `"${key}" has an entry with no page name`;
	if (
		apps !== undefined &&
		!(Array.isArray(apps) && apps.every((app) => typeof app === "string"))
	)
		return `"${key}" gives "${page}" an "apps" that is not a list of app names`;
	if (body !== undefined && page !== DIALOG_PAGE)
		return `"${key}" gives "${page}" a "body", which only the "${DIALOG_PAGE}" entry may have`;
	if (STANDARD_PAGES.includes(page))
		return `"${key}" names "${page}", a name reserved for the standard pages`;
	if (page === DIALOG_PAGE) return dialogProblem(key, body, pageNames);
	if (!pageNames.includes(page))
		return `"${key}" names "${page}", but there is no pages/${page}.js`;
	return null;
}

function dialogProblem(key, body, pageNames) {
	if (key !== "record")
		return `"${key}" names "${DIALOG_PAGE}", which only "record" may name (the record dialog)`;
	if (body === undefined) return null;
	if (typeof body !== "string")
		return `"${key}" gives "${DIALOG_PAGE}" a "body" that is not a page name`;
	if (STANDARD_PAGES.includes(body) || body === DIALOG_PAGE)
		return `"${key}" gives "${DIALOG_PAGE}" the body "${body}", a reserved page name`;
	if (!pageNames.includes(body))
		return `"${key}" gives "${DIALOG_PAGE}" the body "${body}", but there is no pages/${body}.js`;
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

/** A `.js` file beside `pages/` is the handler file of a declared page, or, if not, ignored with a warning. */
function handlerFiles(folder, pageNames, declared, { app, doctype, foreign }) {
	const pageScripts = [];
	const warnings = [];
	for (const handler of files(folder)) {
		const name = basename(handler, ".js");
		if (STANDARD_PAGES.includes(name) || name === DIALOG_PAGE) continue;

		const file = join(folder, handler);
		if (declared.has(name)) {
			pageScripts.push({ app, doctype, page: name, file });
		} else if (pageNames.includes(name)) {
			warnings.push(
				`[frappe] ${file} is the handler file of pages/${handler}, which pages.json does not declare; it is ignored.`
			);
		} else if (foreign) {
			warnings.push(`[frappe] ${file} has no pages/${handler} beside it; it is ignored.`);
		}
	}
	return { pageScripts, warnings };
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
