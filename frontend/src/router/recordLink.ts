// The record pages a Link or Dynamic Link field opens, through `routeFor`, so a replacement page wins.
import type { Router } from "vue-router";
import type { RecordLink } from "@framework/ui/fields/types";
import { routeFor } from "./routeFor";

/** The address of a record, or of a doctype's list without a name; `null` when the doctype has none. */
export function hrefFor(router: Router, doctype: string, name?: string | null): string | null {
	try {
		return router.resolve(routeFor(doctype, name)).href;
	} catch {
		return null;
	}
}

export function recordLink(router: Router): RecordLink {
	return {
		href: (doctype, name) => hrefFor(router, doctype, name),
		open: (doctype, name) => void router.push(routeFor(doctype, name)),
	};
}
