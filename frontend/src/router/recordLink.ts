// The record pages a Link or Dynamic Link field opens, through `routeFor`, so a replacement page wins.
import type { Router } from "vue-router";
import type { RecordLink } from "@framework/ui/components/Fields/types";
import { routeFor, urlFor } from "./routeFor";

export function recordLink(router: Router): RecordLink {
	return {
		href(doctype, name) {
			// A doctype with no address throws.
			try {
				return urlFor(doctype, name);
			} catch {
				return null;
			}
		},
		open: (doctype, name) => void router.push(routeFor(doctype, name)),
	};
}
