import type { RouteLocationRaw } from "vue-router";
import { routeFor } from "@/router/routeFor";

// Not imported from the editor: that would close a record <-> doctypeEditor folder loop.
type EditorMode = "Design" | "Customize";

export interface EditorEntry {
	name: "customize_form" | "edit_doctype";
	label: string;
	icon: string;
	mode: EditorMode;
}

export interface EntryRights {
	roles: readonly string[];
	developerMode: boolean;
	/** `null` until it loads: a custom DocType or a Single must not offer Customize meanwhile. */
	meta: { custom?: unknown; issingle?: unknown } | null | undefined;
}

// `core_doctypes_list` in frappe/model/__init__.py: `mode.py` refuses Customize on these.
const CORE_DOCTYPES = new Set([
	"DefaultValue",
	"DocType",
	"DocField",
	"DocPerm",
	"DocType Action",
	"DocType Link",
	"User",
	"Role",
	"Has Role",
	"Page",
	"Module Def",
	"Print Format",
	"Report",
	"Customize Form",
	"Customize Form Field",
	"Property Setter",
	"Custom Field",
	"Client Script",
]);

export function editorEntries(doctype: string, rights: EntryRights): EditorEntry[] {
	const { meta } = rights;
	if (!doctype || !meta || !rights.roles.includes("System Manager")) return [];
	const entries: EditorEntry[] = [];
	if (!meta.custom && !meta.issingle && !CORE_DOCTYPES.has(doctype))
		entries.push({ name: "customize_form", label: "Customize form", icon: "lucide-paintbrush", mode: "Customize" });
	if (meta.custom || rights.developerMode)
		entries.push({ name: "edit_doctype", label: "Edit DocType", icon: "lucide-pencil-ruler", mode: "Design" });
	return entries;
}

export function editorRoute(doctype: string, mode: EditorMode): RouteLocationRaw {
	return routeFor("DocType", doctype, { query: { mode: mode.toLowerCase() } });
}
