// Where the "Edit layout" entries open the DocType editor. They take the editor entries' right
// from what the shell holds, so drawing them makes no request.
import { inject, toValue, type MaybeRefOrGetter } from "vue";
import { useRouter, type RouteLocationRaw } from "vue-router";
import type { Boot } from "@/boot";
import { editorEntries } from "@/pages/doctypeEditor/entries/editorEntries";
import { routeFor } from "@/router/routeFor";

/** The editor's `?layout=`. */
export type EditorLayout = "details" | "side-panel" | "quick-entry" | "new-record";

export interface LayoutMeta {
	name: string;
	custom?: unknown;
	issingle?: unknown;
}

/** The editor's route at one of the doctype's layouts; `null` without the right, or where the router has no editor. */
export function useEditLayoutRoute(meta: MaybeRefOrGetter<LayoutMeta | null | undefined>) {
	const boot = inject<Boot | null>("boot", null);
	const router = useRouter();
	return (layout: EditorLayout, row?: string | null): RouteLocationRaw | null => {
		const doctype = toValue(meta);
		if (!boot || !doctype || !router.hasRoute("doctype-editor")) return null;
		const rights = { roles: boot.session.roles ?? [], developerMode: boot.developer_mode };
		const modes = editorEntries(doctype.name, { ...rights, meta: doctype }).map((entry) => entry.mode);
		if (!modes.length) return null;
		const query = { mode: editorMode(modes, row), layout, ...(row ? { row } : {}) };
		return routeFor("DocType", doctype.name, { query });
	};
}

/** The editor opens Design when it may; a site row needs Customize, as Design on an app's DocType reads no site rows. */
function editorMode(modes: string[], row?: string | null): "design" | "customize" {
	if (row && !row.startsWith("app:") && modes.includes("Customize")) return "customize";
	return modes.includes("Design") ? "design" : "customize";
}
