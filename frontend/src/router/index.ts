// One router per document, based at `boot.shell_base`; every route path is prefix-relative.
// It is created after boot, never at module scope: the base comes out of boot.

import { createRouter, createWebHistory } from "vue-router";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";
import { declaredReplacements } from "@/contributions/registry";
import { generatedRoutes } from "./generated";
import { contributedRoutes } from "./contributed";
import { isModular } from "./routeFor";
import { preloadMainPage } from "./mainPage";

const RECORD_ROUTES = new Set(["record", "standard-record"]);

export function createShellRouter(boot: Boot, addresses: Addresses) {
	const modular = isModular(boot);
	warnIgnoredListPages(addresses);

	const router = createRouter({
		history: createWebHistory(boot.shell_base),
		routes: [
			// Contributed pages match before generated routes: `/deals` must beat `/:doctype`.
			// Nothing validates a page slug against a doctype or module slug; a clash shadows silently.
			...contributedRoutes(boot.app),
			...generatedRoutes(modular),
			{
				path: "/:pathMatch(.*)*",
				name: "not-found",
				component: () => import("@/shell/NotFound.vue"),
			},
		],
	});

	// Canonicalise the doctype segment to its slug, never away from it: the slug is the address.
	router.beforeResolve((to) => {
		// The module is checked first: a record must not render under a module it does not belong to.
		if (modular && typeof to.params.module === "string" && to.params.module) {
			if (!addresses.hasModule(to.params.module)) {
				// Not a module: it may be a flat address read through a modular table, somebody's old
				// link. Redirect it to the canonical address; anything longer is ambiguous and stays a miss.
				const flat = flatAddress(to, addresses);
				return flat ?? miss(to);
			}
		}

		const segment = to.params.doctype;
		if (typeof segment !== "string" || !segment) return true;
		const doctype = addresses.doctypeOf(segment);
		if (doctype) {
			// A single has no list to show: its list address is the document, as `routeFor` spells
			// it. The module segment is checked on the next pass, as for any record.
			if (addresses.isSingle(doctype) && !RECORD_ROUTES.has(String(to.name))) {
				// Named params only: a saved view's `viewName` has no slot on the record route.
				const params: Record<string, string> = { doctype: segment, name: doctype };
				if (typeof to.params.module === "string") params.module = to.params.module;
				return { name: "record", params, query: to.query, replace: true };
			}
			return modular ? checkModule(to, addresses) : true;
		}

		const canonical = addresses.slugOfName(segment);
		if (canonical)
			return {
				...to,
				params: { ...to.params, doctype: canonical },
				replace: true,
			};

		// The shell owns the miss; otherwise `/:doctype` swallows every unknown path as an empty list.
		return miss(to);
	});

	// After the guard above, so the page loads for the final address, never a redirected one.
	router.beforeResolve((to) => preloadMainPage(to, addresses));

	return router;
}

/**
 * The flat form of an address this prefix spells with a module, `/sales-invoice` or
 * `/sales-invoice/SI-001`. Returns the canonical location, or null.
 */
function flatAddress(to: any, addresses: Addresses) {
	const doctype = addresses.doctypeOf(String(to.params.module));
	const address = doctype ? addresses.addressOf(doctype) : null;
	if (!address || !address[1]) return null;

	const params: Record<string, string> = {
		module: address[1],
		doctype: address[0],
	};

	// `/:module` matched -- the list.
	if (!to.params.doctype)
		return { name: "list", params, query: to.query, replace: true };

	// `/:module/:doctype` matched, so the second segment is a docname. Three segments is
	// already a complete record address and is not re-read.
	if (!to.params.name) {
		return {
			name: "record",
			params: { ...params, name: String(to.params.doctype) },
			query: to.query,
			replace: true,
		};
	}

	return null;
}

/** A single has no list, so a list page declared for one never opens. */
function warnIgnoredListPages(addresses: Addresses) {
	for (const page of declaredReplacements()) {
		if (page.key !== "list" || !addresses.isSingle(page.doctype)) continue;
		console.warn(
			`[frappe] '${page.app}' replaces the list page of '${page.doctype}', a single with no ` +
				"list; the declaration is ignored."
		);
	}
}

function miss(to: { path: string }) {
	return {
		name: "not-found",
		params: { pathMatch: to.path.slice(1).split("/") },
		replace: true,
	};
}

/** Under a modular prefix the module segment must be the doctype's own module. */
function checkModule(to: any, addresses: Addresses) {
	const doctype = addresses.doctypeOf(String(to.params.doctype));
	const address = doctype ? addresses.addressOf(doctype) : null;
	if (!address || address[1] === to.params.module) return true;

	// Not a miss: the record exists and this is the wrong spelling of its address.
	return { ...to, params: { ...to.params, module: address[1] }, replace: true };
}

/** The real doctype behind a URL segment, or null if the site does not serve one. */
export function resolveDoctype(
	addresses: Addresses,
	segment: string
): string | null {
	return addresses.doctypeOf(segment);
}
