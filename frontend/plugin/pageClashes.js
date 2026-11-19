// Warns when a page's slug is a doctype's or a module's on the bench, or two pages of one app
// share a slug. Warnings only: one bundle serves every site, and the router decides per site.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { isFile } from "./folders.js";

/** `Sales Order` -> `sales-order`, the shell's `slug()`. */
function slug(name) {
	return name.replace(/[ _-]/g, "-").toLowerCase();
}

/** `{slug: doctype}` for the doctypes that have an address; a child table has none. */
function doctypeSlugs(definitions) {
	const doctypes = new Map();
	for (const { name, istable } of definitions) {
		if (!istable) doctypes.set(slug(name), name);
	}
	return doctypes;
}

/** `{slug: module}` from each app's `modules.txt`. */
function moduleSlugs(sourceDirs) {
	const modules = new Map();
	for (const sourceDir of sourceDirs) {
		const path = join(sourceDir, "modules.txt");
		if (!isFile(path)) continue;
		for (const line of readFileSync(path, "utf-8").split("\n")) {
			const module = line.trim();
			if (module) modules.set(slug(module), module);
		}
	}
	return modules;
}

/** One warning per page whose slug a doctype, a module or a page of the same app also has. */
export function pageClashes(pages, manifest, definitions, sourceDirs) {
	const doctypes = doctypeSlugs(definitions);
	const modules = moduleSlugs(sourceDirs);
	const modular = new Set(manifest.filter((entry) => entry.modular).map((entry) => entry.app));
	const warnings = [];

	for (const page of pages) {
		const holder = modular.has(page.app)
			? modules.has(page.slug) && `module '${modules.get(page.slug)}'`
			: doctypes.has(page.slug) && `doctype '${doctypes.get(page.slug)}'`;
		if (!holder) continue;
		warnings.push(
			`[frappe] ${page.file}: the ${holder} has the address /${page.slug}; ` +
				`on a site that has it, the page gets no route.`
		);
	}

	const byApp = new Map();
	for (const page of pages) {
		const key = `${page.app}/${page.slug}`;
		byApp.set(key, [...(byApp.get(key) ?? []), page]);
	}
	for (const shared of byApp.values()) {
		if (shared.length < 2) continue;
		const { app, slug } = shared[0];
		const files = shared.map((page) => page.file).join(", ");
		warnings.push(
			`[frappe] '${app}' ships more than one page named '${slug}': ${files}. ` +
				`None of them gets a route.`
		);
	}

	return warnings;
}
