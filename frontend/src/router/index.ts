// HOW ONE ROUTER SERVES N PREFIXES.
//
// The router's base is `boot.shell_base`, set at runtime, and every route path in the
// system is prefix-relative. There is exactly one prefix live in a given page load --
// the one the request came in at -- so the router never sees two.
//
// The rejected alternative was `base: '/'` with prefix-carrying route paths. Its only
// advantage is cross-prefix `router.push`, and that is precisely what boot being
// prefix-scoped already makes impossible without a re-fetch: arriving at `/apps/desk`
// carrying `/apps/crm`'s boot gives you the wrong app's contributed keys with nothing
// to notice it. So it pays a real cost -- the prefix leaves hooks.py and enters JS --
// to enable something already known not to be free (#42072).
//
// The consequence that shapes main.ts: the router CANNOT be a module-scope singleton.

import { createRouter, createWebHistory } from "vue-router";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";
import { generatedRoutes } from "./generated";
import { contributedRoutes } from "./contributed";
import { isModular } from "./routeFor";

export function createShellRouter(boot: Boot, addresses: Addresses) {
	const modular = isModular(boot);

	const router = createRouter({
		// The prefix, asked for at runtime. The one line this file argues about.
		history: createWebHistory(boot.shell_base),
		routes: [
			// Order matters and is not arbitrary: contributed pages match BEFORE generated
			// doctype routes, because `/deals` must beat `/:doctype`. They share one flat
			// namespace (#42068) -- and since #42211 that namespace holds MODULES too, both
			// sitting at depth one.
			//
			// #42068 said an install-time check would guard it. It is NOT built -- neither
			// `install.py` nor the manifest validates slugs -- so today a page file named
			// `crm-deal.js` silently shadows the CRM Deal list, and under a modular prefix a
			// page named `accounts.js` would shadow the Accounts module. Still fog on the
			// map, now one item wider.
			...contributedRoutes(boot.app),
			...generatedRoutes(modular),
			{
				path: "/:pathMatch(.*)*",
				name: "not-found",
				component: () => import("@/shell/NotFound.vue"),
			},
		],
	});

	// Canonicalise the doctype segment TO its slug -- never away from it. The slug is
	// the address, so a pasted `/apps/crm/CRM Deal/CRM-DEAL-01` is redirected to
	// `/apps/crm/crm-deal/CRM-DEAL-01` and not the other way about. Rewriting the
	// param to the real doctype name would put `CRM Deal` in the URL bar, which is the
	// opposite of "path is identity" (#42068).
	//
	// Synchronous, because the table came down with the address fetch before the router
	// existed; CRM's frontend2 needs a server round-trip in `beforeResolve` today.
	router.beforeResolve((to) => {
		// A modular prefix has to agree about the module too, and it is checked FIRST:
		// `/apps/erpnext/nonsense/sales-invoice/SI-001` addresses nothing, and letting it
		// through would render the record under a module it does not belong to -- the URL
		// asserting something false, which is the whole reason the segment is the
		// doctype's own module and never the app's (#42211 §1).
		if (modular && typeof to.params.module === "string" && to.params.module) {
			if (!addresses.hasModule(to.params.module)) {
				// The segment is not a module. Before calling it a miss, ask whether it is a
				// DOCTYPE -- which is what a flat two-segment address looks like once it has
				// been parsed by a modular route table. `/apps/erpnext/sales-invoice/SI-001`
				// is somebody's old link, or a reader who deleted the module out of the path.
				// It gets what a wrong-cased doctype segment already gets: a redirect to the
				// canonical address, because there is one record and one address for it.
				//
				// Only these two forms, and only when the first segment resolves to a
				// doctype. Anything longer is genuinely ambiguous -- which is the whole
				// reason the shape is fixed per app -- and stays a miss.
				const flat = flatAddress(to, addresses);
				return flat ?? miss(to);
			}
		}

		const segment = to.params.doctype;
		if (typeof segment !== "string" || !segment) return true;
		if (addresses.doctypeOf(segment)) {
			return modular ? checkModule(to, addresses) : true;
		}

		const canonical = addresses.slugOfName(segment);
		if (canonical)
			return {
				...to,
				params: { ...to.params, doctype: canonical },
				replace: true,
			};

		// A segment that is neither a slug nor a doctype is a route miss, and the SHELL
		// owns that state -- an app cannot brand its own 404 (#42072). Without this the
		// `/:doctype` route swallows every unknown path and shows an empty list, which
		// reads as "this doctype has no records" rather than "there is no such thing".
		// The document was already served at 200; the miss is the router's to report.
		return miss(to);
	});

	return router;
}

/**
 * `/sales-invoice` or `/sales-invoice/SI-001` seen through a modular route table:
 * the flat form of an address this prefix spells with a module. Returns the canonical
 * location, or null if the first segment names no doctype.
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

	// `/:module/:doctype` matched, so the second segment is really a docname. A third
	// segment cannot be read this way: `/a/b/c` under a modular table is already a
	// complete record address, and re-reading it as a flat one would need a rule for
	// which of the two wins.
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

function miss(to: { path: string }) {
	return {
		name: "not-found",
		params: { pathMatch: to.path.slice(1).split("/") },
		replace: true,
	};
}

/** Under a modular prefix the module segment must be the doctype's OWN module. */
function checkModule(to: any, addresses: Addresses) {
	const doctype = addresses.doctypeOf(String(to.params.doctype));
	const address = doctype ? addresses.addressOf(doctype) : null;
	if (!address || address[1] === to.params.module) return true;

	// Not a 404: the record exists and this is the wrong spelling of its address, which
	// is exactly the case the slug canonicalisation above already redirects. Same
	// treatment, same reason -- one record, one canonical address.
	return { ...to, params: { ...to.params, module: address[1] }, replace: true };
}

/** The real doctype behind a URL segment, or null if the site does not serve one. */
export function resolveDoctype(
	addresses: Addresses,
	segment: string
): string | null {
	return addresses.doctypeOf(segment);
}
