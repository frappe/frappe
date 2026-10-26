// The routes every app gets with no declaration. Path is identity, query is context.

import { standardPage } from "@/contributions/registry";
import type { StandardPages } from "@/contributions/types";
import { loadedPage } from "./mainPage";

export function generatedRoutes(modular: boolean) {
	// Two tables, one set of names, so `routeFor` never branches on shape. The shape is
	// fixed per app: one that varied within an app could not be parsed.
	return modular ? modularRoutes() : flatRoutes();
}

function flatRoutes() {
	return [
		{ path: "/", name: "home", component: loaded("home") },

		// /apps/crm/crm-deal
		{ path: "/:doctype", name: "list", component: standardPage("main") },

		// /apps/crm/crm-deal/view/list, the standard list page.
		{ path: "/:doctype/view/list", name: "standard-list", component: loaded("list") },

		// /apps/crm/crm-deal/view/list/open-deals, a saved view of the list kind.
		{ path: "/:doctype/view/list/:viewName", name: "saved-view", component: loaded("list") },

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
		// The home lists modules here; every addressable level lands somewhere.
		{ path: "/", name: "home", component: loaded("home") },

		// /apps/erpnext/accounts, permission-filtered; addresses are not.
		{ path: "/:module", name: "module", component: loaded("module") },

		// /apps/erpnext/accounts/sales-invoice/SI-001
		{ path: "/:module/:doctype", name: "list", component: standardPage("main") },
		{
			path: "/:module/:doctype/view/list",
			name: "standard-list",
			component: loaded("list"),
		},
		{
			path: "/:module/:doctype/view/list/:viewName",
			name: "saved-view",
			component: loaded("list"),
		},
		{ path: "/:module/:doctype/new", name: "new-record", component: loaded("newRecord") },
		{ path: "/:module/:doctype/:name", name: "record", component: standardPage("main") },
		{
			path: "/:module/:doctype/:name/record",
			name: "standard-record",
			component: loaded("record"),
		},
	];
}

/** A lazy standard page, drawn in the frame while its code loads. */
function loaded(key: Exclude<keyof StandardPages, "main">) {
	return loadedPage(standardPage(key));
}

// Deliberately absent: a per-doctype route (the doctype is a param), an opt-out, and a
// per-doctype module segment (modularity belongs to the app, never the doctype).
