// Synthesises `virtual:frappe/contributions` from the Python manifest, since a raw glob would
// sweep every app on the bench and lose the app name. Everything falls out of the path.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { basename, join } from "node:path";

const VIRTUAL_ID = "virtual:frappe/contributions";
const RESOLVED_ID = "\0" + VIRTUAL_ID;
const STANDARD_PAGES = ["record", "list"];

function directories(path) {
	try {
		return readdirSync(path, { withFileTypes: true })
			.filter((entry) => entry.isDirectory())
			.map((entry) => entry.name);
	} catch {
		return [];
	}
}

function files(path, extension = ".js") {
	try {
		return readdirSync(path, { withFileTypes: true })
			.filter((entry) => entry.isFile() && entry.name.endsWith(extension))
			.map((entry) => entry.name);
	} catch {
		return [];
	}
}

function isFile(path) {
	try {
		return statSync(path).isFile();
	} catch {
		return false;
	}
}

/**
 * `crm_deal` -> `CRM Deal`, read from the doctype's own JSON: title-casing the folder
 * yields "Crm Deal".
 */
function buildDoctypeNames(sourceDirs) {
	const names = new Map();

	for (const source_dir of sourceDirs) {
		for (const module of directories(source_dir)) {
			const doctypeRoot = join(source_dir, module, "doctype");
			for (const scrubbed of directories(doctypeRoot)) {
				const definition = join(doctypeRoot, scrubbed, `${scrubbed}.json`);
				if (!isFile(definition)) continue;
				try {
					const { name } = JSON.parse(readFileSync(definition, "utf-8"));
					if (name) names.set(scrubbed, name);
				} catch {
					// A malformed definition is the doctype loader's to report. Fall back to the folder.
				}
			}
		}
	}

	return names;
}

function titleCase(scrubbed) {
	return scrubbed
		.split("_")
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1))
		.join(" ");
}

export function discover(manifest, allSourceDirs = manifest.map((entry) => entry.source_dir)) {
	const doctypes = [];
	const pages = [];
	const itemTypes = [];
	const replacements = [];
	const warnings = [];
	// Every app on the bench, not just the manifest: a `custom/` folder can name a doctype
	// owned by an app that contributes nothing.
	const names = buildDoctypeNames(allSourceDirs);
	const unscrub = (scrubbed) => names.get(scrubbed) ?? titleCase(scrubbed);

	for (const { app, source_dir } of manifest) {
		for (const module of directories(source_dir)) {
			const modulePath = join(source_dir, module);

			// Your own doctype: <module>/doctype/<scrubbed>/frontend/{record,list}.js
			const doctypeRoot = join(modulePath, "doctype");
			for (const scrubbed of directories(doctypeRoot)) {
				for (const kind of STANDARD_PAGES) {
					const file = join(doctypeRoot, scrubbed, "frontend", `${kind}.js`);
					if (isFile(file))
						doctypes.push({ kind, app, doctype: unscrub(scrubbed), file });
				}

				// A replaced standard page: <module>/doctype/<scrubbed>/frontend/pages.json
				const frontend = join(doctypeRoot, scrubbed, "frontend");
				const declarer = { app, doctype: unscrub(scrubbed), foreign: false };
				replacements.push(...declaredPages(frontend, declarer, warnings));
			}

			// A foreign doctype: <module>/custom/<scrubbed>/{record.js,pages.json}
			const customRoot = join(modulePath, "custom");
			for (const scrubbed of directories(customRoot)) {
				const folder = join(customRoot, scrubbed);
				const file = join(folder, "record.js");
				if (isFile(file))
					doctypes.push({ kind: "custom", app, doctype: unscrub(scrubbed), file });

				const declarer = { app, doctype: unscrub(scrubbed), foreign: true };
				replacements.push(...declaredPages(folder, declarer, warnings));
			}

			// A new page: <module>/frontend/pages/<slug>.js. The `frontend/` segment is load-bearing:
			// `<module>/page/` is desk v1's Page doctype and `templates/pages/` is website templates.
			const pagesRoot = join(modulePath, "frontend", "pages");
			for (const file of files(pagesRoot)) {
				pages.push({ app, slug: basename(file, ".js"), file: join(pagesRoot, file) });
			}

			// An item kind: <module>/navigation_item_type/<scrubbed>/frontend/item.js. Its name comes
			// off the JSON beside it: `doctype` title-cases to "Doctype" and the kind is `DocType`.
			const typeRoot = join(modulePath, "navigation_item_type");
			for (const scrubbed of directories(typeRoot)) {
				const file = join(typeRoot, scrubbed, "frontend", "item.js");
				if (!isFile(file)) continue;

				const definition = join(typeRoot, scrubbed, `${scrubbed}.json`);
				const name = recordName(definition);
				if (!name) {
					// A guessed name would register the renderer under a string no item carries.
					warnings.push(
						`[frappe] ${file} has no ${scrubbed}.json beside it; the item type it renders cannot be named, so it is ignored.`
					);
					continue;
				}

				itemTypes.push({ app, type: name, file });
			}
		}
	}

	warnings.push(...clashes(replacements));
	return { doctypes, pages, itemTypes, replacements, warnings };
}

/** The pages a folder's `pages.json` names from the `pages/` folder beside it. */
function declaredPages(folder, declarer, warnings) {
	const pagesRoot = join(folder, "pages");
	const pageNames = files(pagesRoot).map((file) => basename(file, ".js"));
	warnings.push(...handlerFileWarnings(folder, pageNames, declarer.foreign));

	const path = join(folder, "pages.json");
	const declaration = readDeclaration(path, warnings);
	const found = [];
	for (const [key, page] of Object.entries(declaration)) {
		const problem = declarationProblem(key, page, pageNames);
		if (problem) {
			warnings.push(`[frappe] ${path}: ${problem}; that key is ignored.`);
			continue;
		}
		found.push({ ...declarer, key, page, file: join(pagesRoot, `${page}.js`) });
	}
	return found;
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
function readDeclaration(path, warnings) {
	if (!isFile(path)) return {};

	let declaration;
	try {
		declaration = JSON.parse(readFileSync(path, "utf-8"));
	} catch {
		warnings.push(`[frappe] ${path} is not valid JSON; the whole file is ignored.`);
		return {};
	}
	if (declaration === null || typeof declaration !== "object" || Array.isArray(declaration)) {
		warnings.push(`[frappe] ${path} is not a JSON object; the whole file is ignored.`);
		return {};
	}
	return declaration;
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

/** One warning per doctype and key that more than one app replaces. */
function clashes(replacements) {
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

/** A record's real name, read from its own JSON. `null` if there is no readable one. */
function recordName(definition) {
	if (!isFile(definition)) return null;
	try {
		return JSON.parse(readFileSync(definition, "utf-8")).name ?? null;
	} catch {
		// A malformed record is `import_file`'s to report at migrate; it is still not a name.
		return null;
	}
}

function generate({ doctypes, pages, itemTypes, replacements, warnings }) {
	const lines = [
		"// GENERATED by plugin/contributions.js. Do not edit.",
		"function usable(entry) {",
		"  if (entry.handlers) return true",
		"  console.warn(`[frappe] ignoring contribution with no default export: ${entry.__file}`)",
		"  return false",
		"}",
	];
	const imports = [];

	doctypes.forEach((entry, index) => {
		imports.push(`import d${index} from ${JSON.stringify(entry.file)}`);
	});
	pages.forEach((entry, index) => {
		imports.push(`import p${index} from ${JSON.stringify(entry.file)}`);
	});
	itemTypes.forEach((entry, index) => {
		imports.push(`import i${index} from ${JSON.stringify(entry.file)}`);
	});
	replacements.forEach((entry, index) => {
		imports.push(`import r${index} from ${JSON.stringify(entry.file)}`);
	});

	lines.push(...imports);
	lines.push("export default {");

	lines.push("  doctypes: [");
	doctypes.forEach((entry, index) => {
		lines.push(
			`    { kind: ${JSON.stringify(entry.kind === "custom" ? "custom" : entry.kind)}, ` +
				`app: ${JSON.stringify(entry.app)}, doctype: ${JSON.stringify(entry.doctype)}, ` +
				`handlers: d${index}, __file: ${JSON.stringify(entry.file)} },`
		);
	});
	// Dropped with a warning, never a throw: `main.ts` imports this before anything renders,
	// so one app's typo must not fail the mount bench-wide.
	lines.push("  ].filter(usable),");

	lines.push("  pages: [");
	pages.forEach((entry, index) => {
		lines.push(
			`    { app: ${JSON.stringify(entry.app)}, slug: ${JSON.stringify(entry.slug)}, ` +
				`title: p${index}?.title, component: p${index}?.component, ` +
				`handlers: p${index}?.component, __file: ${JSON.stringify(entry.file)} },`
		);
	});
	lines.push("  ].filter(usable),");

	// `handlers` is the same key the other two carry, so `usable` covers item types too.
	lines.push("  itemTypes: [");
	itemTypes.forEach((entry, index) => {
		lines.push(
			`    { app: ${JSON.stringify(entry.app)}, type: ${JSON.stringify(entry.type)}, ` +
				`handlers: i${index}, renderer: i${index}, __file: ${JSON.stringify(
					entry.file
				)} },`
		);
	});
	lines.push("  ].filter(usable),");

	lines.push("  replacements: [");
	replacements.forEach((entry, index) => {
		lines.push(
			`    { app: ${JSON.stringify(entry.app)}, ` +
				`doctype: ${JSON.stringify(entry.doctype)}, key: ${JSON.stringify(entry.key)}, ` +
				`foreign: ${entry.foreign}, ` +
				`title: r${index}?.title, component: r${index}?.component, ` +
				`handlers: r${index}?.component, __file: ${JSON.stringify(entry.file)} },`
		);
	});
	lines.push("  ].filter(usable),");

	lines.push("}");

	// Discovery's warnings are replayed in the browser, where the person missing a kind looks.
	for (const warning of warnings) {
		lines.push(`console.warn(${JSON.stringify(warning)})`);
	}

	return lines.join("\n");
}

/** Prints discovery's warnings in the terminal that runs the build. */
export function report(warnings, logger = console) {
	for (const warning of warnings) logger.warn(warning);
}

export default function contributions(manifest, allSourceDirs) {
	let logger;
	return {
		name: "frappe-contributions",
		configResolved(config) {
			logger = config.logger;
		},
		resolveId: (id) => (id === VIRTUAL_ID ? RESOLVED_ID : undefined),
		load(id) {
			if (id !== RESOLVED_ID) return;
			const found = discover(manifest, allSourceDirs);
			report(found.warnings, logger);
			return generate(found);
		},
	};
}
