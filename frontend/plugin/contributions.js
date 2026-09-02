// The vite plugin that synthesises `virtual:frappe/contributions`.
//
// Why synthesise rather than glob: `import.meta.glob` needs a static literal pattern
// and would sweep every app on the bench, installed or not -- and a raw glob loses
// the app name, which is the one attribution the whole contract needs (#42068). The
// Python manifest supplies both: which apps are in the bundle, and what each is
// called.
//
// App, module, doctype and kind all fall out of the PATH. Nothing is parsed out of
// file contents, so a file that fails to import cannot break discovery.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { basename, join } from "node:path";

const VIRTUAL_ID = "virtual:frappe/contributions";
const RESOLVED_ID = "\0" + VIRTUAL_ID;

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
 * `crm_deal` -> `CRM Deal`.
 *
 * Title-casing the folder cannot do this -- it yields "Crm Deal", and acronyms are
 * common in doctype names. The real name is on disk in the doctype's own JSON, which
 * is readable at build time with no site, so the index is built from the definitions
 * rather than guessed from the folder.
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
					// A malformed definition is the doctype loader's problem to report, not
					// the bundler's. Fall back to the folder.
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
	const warnings = [];
	// Every app on the bench, not just the ones in the manifest. A `custom/` folder can
	// name a FOREIGN doctype owned by an app that contributes nothing itself -- and
	// title-casing the folder would then answer "Hd Ticket" where the registry says
	// "HD Ticket", so the contribution would bundle, register and silently never run.
	const names = buildDoctypeNames(allSourceDirs);
	const unscrub = (scrubbed) => names.get(scrubbed) ?? titleCase(scrubbed);

	for (const { app, source_dir } of manifest) {
		for (const module of directories(source_dir)) {
			const modulePath = join(source_dir, module);

			// 1 & 2. Your own doctype: <module>/doctype/<scrubbed>/frontend/{record,list}.js
			const doctypeRoot = join(modulePath, "doctype");
			for (const scrubbed of directories(doctypeRoot)) {
				for (const kind of ["record", "list"]) {
					const file = join(doctypeRoot, scrubbed, "frontend", `${kind}.js`);
					if (isFile(file))
						doctypes.push({ kind, app, doctype: unscrub(scrubbed), file });
				}
			}

			// 3. A foreign doctype: <module>/custom/<scrubbed>/record.js
			//    Same shape as your own; only the folder differs, mirroring the split
			//    frappe already makes for schema customizations (`custom/contact.json`).
			const customRoot = join(modulePath, "custom");
			for (const scrubbed of directories(customRoot)) {
				const file = join(customRoot, scrubbed, "record.js");
				if (isFile(file))
					doctypes.push({ kind: "custom", app, doctype: unscrub(scrubbed), file });
			}

			// 4. A genuinely new page: <module>/frontend/pages/<slug>.js
			//    The `frontend/` segment is load-bearing: `<module>/page/` is already desk
			//    v1's Page doctype and `templates/pages/` is already website templates, so
			//    a bare `<module>/pages/` would sit one character from a different meaning
			//    (#42072).
			const pagesRoot = join(modulePath, "frontend", "pages");
			for (const file of files(pagesRoot)) {
				pages.push({ app, slug: basename(file, ".js"), file: join(pagesRoot, file) });
			}

			// 5. An item kind for the rail and the sidebar:
			//    <module>/navigation_item_type/<scrubbed>/frontend/item.js
			//
			//    Colocated with the type RECORD, in the record's own folder, which is the
			//    doctype pattern rather than the page one. The reason is the same reason
			//    `buildDoctypeNames` exists: the type's real name has to come off the JSON
			//    beside it, never from title-casing the folder. `doctype` title-cases to
			//    "Doctype", and the framework's own first kind is called `DocType` — so the
			//    guessed form is wrong on the very first row, and a renderer registered
			//    under a name no item carries never runs and says nothing.
			const typeRoot = join(modulePath, "navigation_item_type");
			for (const scrubbed of directories(typeRoot)) {
				const file = join(typeRoot, scrubbed, "frontend", "item.js");
				if (!isFile(file)) continue;

				const definition = join(typeRoot, scrubbed, `${scrubbed}.json`);
				const name = recordName(definition);
				if (!name) {
					// A renderer with no type record beside it names nothing. Guessing would
					// register it under a string no item can carry, which is a contribution that
					// silently never runs -- the failure the whole file is arranged to avoid.
					warnings.push(
						`[frappe] ${file} has no ${scrubbed}.json beside it; the item type it renders cannot be named, so it is ignored.`
					);
					continue;
				}

				itemTypes.push({ app, type: name, file });
			}
		}
	}

	return { doctypes, pages, itemTypes, warnings };
}

/** A record's real name, read from its own JSON. `null` if there is no readable one. */
function recordName(definition) {
	if (!isFile(definition)) return null;
	try {
		return JSON.parse(readFileSync(definition, "utf-8")).name ?? null;
	} catch {
		// A malformed record is `import_file`'s problem to report at migrate, not the
		// bundler's. It is still not a name, so the renderer is dropped either way.
		return null;
	}
}

function generate({ doctypes, pages, itemTypes, warnings }) {
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
	// Entries with no usable default export are dropped with a warning naming the file,
	// NOT allowed to throw: this module is imported by main.ts before anything renders,
	// so one app's typo would otherwise fail the mount for every prefix on the bench.
	// Same degrade-don't-fail asymmetry `app_boot` chose on the Python side.
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

	// The renderer for one item kind. `handlers` is the same key the other two carry, so
	// the `usable` filter that drops a file with no default export covers this one too --
	// and it has to, because `registerContributions` indexes these by type NAME and an
	// undefined entry would take a whole kind of item off the rail with no line said.
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

	lines.push("}");

	// Discovery's own complaints, replayed in the browser rather than at build time: a
	// `vite build` scrolls past and nobody reads it, while this reaches the console of the
	// person whose kind is not appearing. Same channel `usable` already uses, for the same
	// audience.
	for (const warning of warnings) {
		lines.push(`console.warn(${JSON.stringify(warning)})`);
	}

	return lines.join("\n");
}

export default function contributions(manifest, allSourceDirs) {
	return {
		name: "frappe-contributions",
		resolveId: (id) => (id === VIRTUAL_ID ? RESOLVED_ID : undefined),
		load(id) {
			if (id !== RESOLVED_ID) return;
			return generate(discover(manifest, allSourceDirs));
		},
	};
}
