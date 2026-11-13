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
		if (!canEditLayout(doctype, rights)) return null;
		return routeFor("DocType", doctype.name, { query: row ? { layout, row } : { layout } });
	};
}

/** Whether either editor entry, Customize form or Edit DocType, opens on the doctype. */
export function canEditLayout(
	meta: LayoutMeta,
	rights: { roles: readonly string[]; developerMode: boolean }
): boolean {
	return editorEntries(meta.name, { ...rights, meta }).length > 0;
}
