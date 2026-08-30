// The routes EVERY app gets with no declaration at all -- charter item 2's "default
// first" made literal. An app that writes nothing in hooks.py gets all of this at
// /apps/<its own name>.
//
// Note what is a path segment and what is a query param: path is identity, query is
// context (#42068), as narrowed by #42210 -- context that must survive a paste earns
// a path segment, which is how the prefix itself came to be one.

const Home = () => import("@/pages/Home.vue");
const List = () => import("@/pages/List.vue");
const Record = () => import("@/pages/Record.vue");
const Module = () => import("@/pages/Module.vue");

export function generatedRoutes(modular: boolean) {
	// TWO tables, one set of NAMES. The modular table is the flat one shifted a segment
	// deeper, and the route names are identical in both -- which is what lets
	// `routeFor` build `{ name: 'record', params }` without branching on shape, and
	// every consumer stay ignorant of which app it is running in.
	//
	// No in-app ambiguity, because the shape is fixed per app (#42211). It is precisely
	// a shape that varied WITHIN an app that would be unparseable: frappe's `Workflow`
	// module and `Workflow` doctype share a slug, so nothing could tell
	// `/workflow/LEAVE-APPROVAL` from `/workflow/workflow`.
	return modular ? modularRoutes() : flatRoutes();
}

function flatRoutes() {
	return [
		{ path: "/", name: "home", component: Home },

		// /apps/crm/crm-deal
		{ path: "/:doctype", name: "list", component: List },

		// /apps/crm/crm-deal/view/open-deals -- a SAVED view, not a view type. v1's type
		// names (report/kanban/calendar) become reserved saved-view ids.
		{ path: "/:doctype/view/:viewName", name: "saved-view", component: List },

		// /apps/crm/crm-deal/CRM-DEAL-01?view=open-deals&layout=Compact
		// Neither of those two is a path segment, and that is a decision, not an omission.
		{ path: "/:doctype/:name", name: "record", component: Record },
	];
}

function modularRoutes() {
	return [
		// The app home lists MODULES rather than doctypes here. The address walks all the
		// way up -- record, module, app, /apps -- because an addressable level that 404s
		// is a navigation dead end, and a reader who deletes the tail of a URL expects to
		// land somewhere (#42211 §6).
		{ path: "/", name: "home", component: Home },

		// /apps/erpnext/accounts -- framework-generated, permission-FILTERED. Addressability
		// is permission-independent; navigation is filtered. Nobody pastes a module page as
		// a record link, so filtering it changes no address's shape.
		{ path: "/:module", name: "module", component: Module },

		// /apps/erpnext/accounts/sales-invoice/SI-001
		{ path: "/:module/:doctype", name: "list", component: List },
		{
			path: "/:module/:doctype/view/:viewName",
			name: "saved-view",
			component: List,
		},
		{ path: "/:module/:doctype/:name", name: "record", component: Record },
	];
}

// NOT here, deliberately:
//   - no per-doctype route. The doctype is a param, so a bench with 553 doctypes has
//     4 routes, not 2,212. #42066 measured 143 microseconds per werkzeug rule for the
//     server-side equivalent, and that measurement is the reason.
//   - no opt-out. An app cannot hide its doctype from these routes (#42068).
//   - no per-doctype module segment. Modularity is a property of the APP, never of
//     the doctype: emitting a module "whenever the doctype has one" would stop a
//     non-modular app being able to serve a foreign doctype at all (#42211 §2).
