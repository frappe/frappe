// The address a path is redirected to by the router's guard, resolved without navigating.

import { START_LOCATION, type Router, type RouteLocationRaw } from "vue-router";
import type { Addresses } from "@/addresses";

/** The guard's address redirects, as a location; null when the address is already canonical or a miss. */
export function canonicalAddress(to: any, addresses: Addresses) {
	// The module segment exists only on a modular prefix's routes.
	const modular = typeof to.params.module === "string" && to.params.module;
	if (modular) {
		// Not a module: it may be a flat address read through a modular table, somebody's old link.
		if (!addresses.hasModule(to.params.module)) return flatAddress(to, addresses);
	}

	const segment = to.params.doctype;
	if (typeof segment !== "string" || !segment) return null;

	const doctype = addresses.doctypeOf(segment);
	if (!doctype) {
		const slug = addresses.slugOfName(segment);
		return slug ? { ...to, params: { ...to.params, doctype: slug }, replace: true } : null;
	}

	return modular ? wrongModule(to, addresses, doctype) : null;
}

/** Where `to` ends up after the address redirects, as the path the shell is standing on. */
export function canonicalPath(
	router: Router,
	addresses: Addresses,
	to: RouteLocationRaw
): string {
	// Never against the current route, or every row would redraw on each route change.
	let resolved = router.resolve(to, START_LOCATION);
	// Bounded: a redirect chain is two hops at most, and a loop must not hang the shell.
	for (let hop = 0; hop < 3; hop += 1) {
		const next = canonicalAddress(resolved, addresses);
		if (!next) break;
		resolved = router.resolve(next, START_LOCATION);
	}

	return resolved.path;
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
		const name = String(to.params.doctype);
		if (name === "new") return { name: "new-record", params, query: to.query, replace: true };
		return { name: "record", params: { ...params, name }, query: to.query, replace: true };
	}

	return null;
}

function wrongModule(to: any, addresses: Addresses, doctype: string) {
	const address = addresses.addressOf(doctype);
	if (!address || address[1] === to.params.module) return null;

	// Not a miss: the record exists and this is the wrong spelling of its address.
	return { ...to, params: { ...to.params, module: address[1] }, replace: true };
}
