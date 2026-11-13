// The list and record ⋯ entries that open the DocType editor. They read only what the shell
// holds (roles, developer mode, the DocType's meta), so a page makes no request to draw them.
import type { RouteLocationRaw } from "vue-router";
import { routeFor } from "@/router/routeFor";

// The editor's `EditorMode`, spelled out: the record and list pages import this file, and the
// editor imports theirs.
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
	custom?: boolean;
	single?: boolean;
}

/** Mirrors `mode.py`: Customize Form's write is the System Manager's, and Design on a standard DocType needs developer mode. */
export function editorEntries(doctype: string, rights: EntryRights): EditorEntry[] {
	if (!doctype || !rights.roles.includes("System Manager")) return [];
	const entries: EditorEntry[] = [];
	if (!rights.custom && !rights.single)
		entries.push({ name: "customize_form", label: "Customize form", icon: "lucide-paintbrush", mode: "Customize" });
	if (rights.custom || rights.developerMode)
		entries.push({ name: "edit_doctype", label: "Edit DocType", icon: "lucide-pencil-ruler", mode: "Design" });
	return entries;
}

export function editorRoute(doctype: string, mode: EditorMode): RouteLocationRaw {
	return routeFor("DocType", doctype, { query: { mode: mode.toLowerCase() } });
}
