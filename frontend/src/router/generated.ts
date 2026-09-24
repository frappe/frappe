// The routes every app gets with no declaration. Path is identity, query is context.

const Home = () => import("@/pages/Home.vue");
const List = () => import("@/pages/List.vue");
const Record = () => import("@/pages/Record.vue");
const Module = () => import("@/pages/Module.vue");
const MainPage = () => import("@/pages/MainPage.vue");

/** The page each main address opens when no app declared one in its place. */
export const standardPages = { list: List, record: Record };

export function generatedRoutes(modular: boolean) {
	// Two tables, one set of names, so `routeFor` never branches on shape. The shape is
	// fixed per app: one that varied within an app could not be parsed.
	return modular ? modularRoutes() : flatRoutes();
}

function flatRoutes() {
	return [
		{ path: "/", name: "home", component: Home },

		// /apps/crm/crm-deal
		{ path: "/:doctype", name: "list", component: MainPage },

		// /apps/crm/crm-deal/view/list, the standard list page.
		{ path: "/:doctype/view/list", name: "standard-list", component: List },

		// /apps/crm/crm-deal/view/list/open-deals, a saved view of the list kind.
		{ path: "/:doctype/view/list/:viewName", name: "saved-view", component: List },

		// /apps/crm/crm-deal/CRM-DEAL-01?view=open-deals&layout=Compact; neither is a path segment.
		{ path: "/:doctype/:name", name: "record", component: MainPage },

		// /apps/crm/crm-deal/CRM-DEAL-01/record, the standard record page.
		{ path: "/:doctype/:name/record", name: "standard-record", component: Record },
	];
}

function modularRoutes() {
	return [
		// The home lists modules here; every addressable level lands somewhere.
		{ path: "/", name: "home", component: Home },

		// /apps/erpnext/accounts, permission-filtered; addresses are not.
		{ path: "/:module", name: "module", component: Module },

		// /apps/erpnext/accounts/sales-invoice/SI-001
		{ path: "/:module/:doctype", name: "list", component: MainPage },
		{
			path: "/:module/:doctype/view/list",
			name: "standard-list",
			component: List,
		},
		{
			path: "/:module/:doctype/view/list/:viewName",
			name: "saved-view",
			component: List,
		},
		{ path: "/:module/:doctype/:name", name: "record", component: MainPage },
		{
			path: "/:module/:doctype/:name/record",
			name: "standard-record",
			component: Record,
		},
	];
}

// Deliberately absent: a per-doctype route (the doctype is a param), an opt-out, and a
// per-doctype module segment (modularity belongs to the app, never the doctype).
