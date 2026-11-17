// The DocType sidebar: when the active rail item is a DocType, the panel lists that DocType's views.
import { markRaw, ref, shallowRef, type Component } from "vue";
import type { NavigationItem } from "@/boot";

/** The doctype whose views the shell sidebar lists now; the list's crumb menu then holds acts only. */
export const viewsSidebarDoctype = ref<string | null>(null);

// The body is a page piece (it lists views and runs the list's acts): `main.ts` registers it, so the shell imports no page.
export const viewsSidebarBody = shallowRef<Component | null>(null);

/** Registers the component that draws the views sidebar's body; it takes `doctype` and `title`. */
export function registerViewsSidebar(body: Component) {
	viewsSidebarBody.value = markRaw(body);
}

/** The rail item's DocType when its sidebar is the views panel; a single has no list, so no views. */
export function viewsSidebarFor(
	owner: NavigationItem | undefined,
	isSingle: (doctype: string) => boolean
): { doctype: string; title: string } | null {
	if (owner?.item_type !== "DocType" || !owner.link_to) return null;
	if (isSingle(owner.link_to)) return null;
	return { doctype: owner.link_to, title: owner.label || owner.link_to };
}

const VIEW_ROUTES = new Set(["list", "standard-list", "saved-view"]);

/** The view key the address shows, or null on a page that is no view (a record, say). */
export function openViewKey(route: { name?: unknown; params: Record<string, unknown> }): string | null {
	if (route.name === "saved-view") return String(route.params.key);
	return VIEW_ROUTES.has(String(route.name)) ? "list" : null;
}
