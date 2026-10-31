// The routes every app gets with no declaration. Path is identity, query is context.

import { standardPage } from "@/contributions/registry";
import type { StandardPages } from "@/contributions/types";
import type { RouteLocation } from "vue-router";
import NothingToOpen from "@/shell/NothingToOpen.vue";
import { loadedPage } from "./mainPage";

export function generatedRoutes(modular: boolean) {
	// Two tables, one set of names, so `routeFor` never branches on shape. The shape is
	// fixed per app: one that varied within an app could not be parsed.
	return modular ? modularRoutes() : flatRoutes();
}

function flatRoutes() {
	return [
		// An app's home redirects to its landing and shows this only when none resolves.
		{ path: "/", name: "home", component: NothingToOpen },

		// /apps/crm/crm-deal
		{ path: "/:doctype", name: "list", component: standardPage("main") },

		// /apps/crm/crm-deal/view/list, the standard list page.
		{ path: "/:doctype/view/list", name: "standard-list", component: loaded("list") },

		// /apps/crm/crm-deal/view/open-deals, a saved view by its key; a view type's name is never a key.
		{ path: "/:doctype/view/:key", name: "saved-view", component: loaded("list") },
		viewRecord("/:doctype/view/record"),

		// /apps/crm/crm-deal/new?status=Open, the standard page whatever an app declared.
		{ path: "/:doctype/new", name: "new-record", component: loaded("newRecord") },

		// /apps/crm/crm-deal/CRM-DEAL-01?view=open-deals&layout=Compact; neither is a path segment.
		{ path: "/:doctype/:name", name: "record", component: standardPage("main") },

		// /apps/crm/crm-deal/CRM-DEAL-01/record, the standard record page.
		{ path: "/:doctype/:name/record", name: "standard-record", component: loaded("record") },
	];
}

function modularRoutes() {
	return [
		{ path: "/", name: "home", component: NothingToOpen },

		// /apps/erpnext/accounts lands on the first row of the module's sidebar.
		{ path: "/:module", name: "module", component: NothingToOpen },

		// /apps/erpnext/accounts/sales-invoice/SI-001
		{ path: "/:module/:doctype", name: "list", component: standardPage("main") },
		{
			path: "/:module/:doctype/view/list",
			name: "standard-list",
			component: loaded("list"),
		},
		{
			path: "/:module/:doctype/view/:key",
			name: "saved-view",
			component: loaded("list"),
		},
		viewRecord("/:module/:doctype/view/record"),
		{ path: "/:module/:doctype/new", name: "new-record", component: loaded("newRecord") },
		{ path: "/:module/:doctype/:name", name: "record", component: standardPage("main") },
		{
			path: "/:module/:doctype/:name/record",
			name: "standard-record",
			component: loaded("record"),
		},
	];
}

/** The index's one route: it belongs to no app, so it has no doctype to address. */
export function indexRoutes() {
	return [{ path: "/", name: "home", component: standardPage("index") }];
}

/** The standard page of the record named "view", which the saved view's route outranks; `record` is never a key. */
function viewRecord(path: string) {
	return {
		path,
		redirect: ({ params, query, hash }: RouteLocation) => ({
			name: "standard-record",
			params: { ...params, name: "view" },
			query,
			hash,
		}),
	};
}

/** A lazy standard page, drawn in the frame while its code loads. */
function loaded(key: Exclude<keyof StandardPages, "main" | "index">) {
	return loadedPage(standardPage(key));
}

// Deliberately absent: a per-doctype route (the doctype is a param), an opt-out, and a
// per-doctype module segment (modularity belongs to the app, never the doctype).
