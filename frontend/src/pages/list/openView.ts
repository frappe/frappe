// Opens one of a doctype's views from the switcher.
import type { Router } from "vue-router";
import { routeFor } from "@/router/routeFor";
import { skipDefaultOnce } from "@/router/skipDefault";

/** The plain List skips the person's default for this visit. */
export function openView(router: Router, doctype: string, key: string) {
	if (key !== "list") return router.push(routeFor(doctype, null, { view: key }));
	skipDefaultOnce(doctype);
	return router.push(routeFor(doctype));
}
