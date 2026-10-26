// The routes every app gets with no declaration. Path is identity, query is context.

import { standardPage } from "@/contributions/registry";

export function generatedRoutes(modular: boolean) {
	// Two tables, one set of names, so `routeFor` never branches on shape. The shape is
	// fixed per app: one that varied within an app could not be parsed.
	return modular ? modularRoutes() : flatRoutes();
}

function flatRoutes() {
	return [
		{ path: "/", name: "home", component: standardPage("home") },

		// /apps/crm/crm-deal
		{ path: "/:doctype", name: "list", component: standardPage("main") },

		// /apps/crm/crm-deal/view/list, the standard list page.
		{ path: "/:doctype/view/list", name: "standard-list", component: standardPage("list") },

		// /apps/crm/crm-deal/view/list/open-deals, a saved view of the list kind.
		{ path: "/:doctype/view/list/:viewName", name: "saved-view", component: standardPage("list") },

		// /apps/crm/crm-deal/new?status=Open, the standard page whatever an app declared.
		{ path: "/:doctype/new", name: "new-record", component: standardPage("newRecord") },

		// /apps/crm/crm-deal/CRM-DEAL-01?view=open-deals&layout=Compact; neither is a path segment.
		{ path: "/:doctype/:name", name: "record", component: standardPage("main") },

		// /apps/crm/crm-deal/CRM-DEAL-01/record, the standard record page.
		{ path: "/:doctype/:name/record", name: "standard-record", component: standardPage("record") },
	];
}

function modularRoutes() {
	return [
		// The home lists modules here; every addressable level lands somewhere.
		{ path: "/", name: "home", component: standardPage("home") },

		// /apps/erpnext/accounts, permission-filtered; addresses are not.
		{ path: "/:module", name: "module", component: standardPage("module") },

		// /apps/erpnext/accounts/sales-invoice/SI-001
		{ path: "/:module/:doctype", name: "list", component: standardPage("main") },
		{
			path: "/:module/:doctype/view/list",
			name: "standard-list",
			component: standardPage("list"),
		},
		{
			path: "/:module/:doctype/view/list/:viewName",
			name: "saved-view",
			component: standardPage("list"),
		},
		{ path: "/:module/:doctype/new", name: "new-record", component: standardPage("newRecord") },
		{ path: "/:module/:doctype/:name", name: "record", component: standardPage("main") },
		{
			path: "/:module/:doctype/:name/record",
			name: "standard-record",
			component: standardPage("record"),
		},
	];
}

// Deliberately absent: a per-doctype route (the doctype is a param), an opt-out, and a
// per-doctype module segment (modularity belongs to the app, never the doctype).
