// The add-row picker's View step: a doctype, then one of its views from `list_views`.
import { runMethod } from "@framework/ui/api";
import { __ } from "@/i18n";
import type { EditorRow, Scope } from "./draft";

/** One entry of `list_views`: a plain view has no layer. */
export type ListedView = {
	key: string;
	label: string;
	type: string;
	layer: "own" | "site" | "app" | null;
};

export type ViewType = { name: string; label: string; icon: string | null };

/** The server's refusal of an own view at the site level (`navigation_item_type/view/view.py`). */
export const PUBLISH_FIRST = () => __("Publish this view first, so everyone can open it.");

/** `list_views(doctype, app)` for one doctype: plain views first, then own, site and app. */
export async function fetchViews(doctype: string, app: string): Promise<ListedView[]> {
	const response = await runMethod<Record<string, ListedView[]>>(
		"frappe.desk.doctype.doctype_view.api.list_views",
		{ doctype, app },
		{ http: "GET" }
	);
	return response.data[doctype] ?? [];
}

/** The views a level can name: a view that is only the person's own cannot open for everyone. */
export function pickableViews(views: ListedView[], scope: Scope): ListedView[] {
	return views.filter((view) => scope === "user" || view.layer !== "own");
}

/** The row a view adds. The label and icon are the view's at this moment and do not follow a rename. */
export function viewRow(
	doctype: string,
	view: ListedView,
	types: ViewType[]
): Omit<EditorRow, "key"> {
	const icon = types.find((type) => type.name === view.type)?.icon;
	return {
		item_type: "View",
		link_doctype: "DocType",
		link_to: doctype,
		payload: { view: view.key },
		label: view.label,
		...(icon ? { icon } : {}),
	};
}

/** The view key a View row names, or "" when its payload holds none. */
export function viewKeyOf(row: EditorRow): string {
	const key = row.payload?.view;
	return typeof key === "string" ? key : "";
}
