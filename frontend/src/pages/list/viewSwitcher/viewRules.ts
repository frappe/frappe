// Who may do what to a view, as the server decides it.
import type { ListedView } from "@/list/listedViews";

/** One act the view's menu may offer, in the order the menu lists them. */
export type ViewAct =
	| "rename"
	| "publish"
	| "delete"
	| "restore"
	| "set_mine"
	| "clear_mine"
	| "set_site"
	| "clear_site";

/** The acts open to `admin` on `view`. */
export function actsOn(view: ListedView, admin: boolean): ViewAct[] {
	const { layer } = view;
	const pointers = view.default_for ?? [];
	const shared = layer === "site" && admin;
	const out: ViewAct[] = [];
	if (layer === "own" || shared) out.push("rename");
	if (layer === "own" && admin) out.push("publish");
	if (view.overrides_app) {
		if (admin) out.push("restore");
	} else if (layer === "own" || shared) out.push("delete");
	out.push(pointers.includes("user") ? "clear_mine" : "set_mine");
	if (admin) out.push(pointers.includes("site") ? "clear_site" : "set_site");
	return out;
}

/** An own view must be published before it can be everyone's default. */
export function siteDefaultBlocked(view: ListedView): boolean {
	return view.layer === "own";
}

/** A site administrator; Administrator holds every role. */
export function isSiteAdmin(roles: readonly string[]): boolean {
	return roles.includes("System Manager");
}
