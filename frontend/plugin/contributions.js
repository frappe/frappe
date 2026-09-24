// Synthesises `virtual:frappe/contributions` from the Python manifest, since a raw glob would
// sweep every app on the bench and lose the app name. Everything falls out of the path.

import { readFileSync } from "node:fs";
import { basename, join } from "node:path";
import { directories, files, isFile } from "./folders.js";
import { STANDARD_PAGES, clashes, declaredPages } from "./replacements.js";

const VIRTUAL_ID = "virtual:frappe/contributions";
const RESOLVED_ID = "\0" + VIRTUAL_ID;

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
	const declarations = [];
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
				const owned = declaredPages(frontend, declarer);
				replacements.push(...owned.found);
				warnings.push(...owned.warnings);
				if (owned.declaration) declarations.push(owned.declaration);
			}

			// A foreign doctype: <module>/custom/<scrubbed>/{record.js,pages.json}
			const customRoot = join(modulePath, "custom");
			for (const scrubbed of directories(customRoot)) {
				const folder = join(customRoot, scrubbed);
				const file = join(folder, "record.js");
				if (isFile(file))
					doctypes.push({ kind: "custom", app, doctype: unscrub(scrubbed), file });

				const declarer = { app, doctype: unscrub(scrubbed), foreign: true };
				const custom = declaredPages(folder, declarer);
				replacements.push(...custom.found);
				warnings.push(...custom.warnings);
				if (custom.declaration) declarations.push(custom.declaration);
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
	return { doctypes, pages, itemTypes, replacements, declarations, warnings };
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
			// `pages.json` is read, never imported, so vite would not reload the module on an edit.
			for (const declaration of found.declarations) this.addWatchFile(declaration);
			report(found.warnings, logger);
			return generate(found);
		},
	};
}
