// The routes EVERY app gets with no declaration at all -- charter item 2's "default
// first" made literal. An app that writes nothing in hooks.py gets all of this at
// /apps/<its own name>.
//
// Note what is a path segment and what is a query param: path is identity, query is
// context (#42068).

export function generatedRoutes() {
  return [
    { path: '/', name: 'home', component: () => import('@/pages/Home.vue') },

    // /apps/crm/crm-deal
    { path: '/:doctype', name: 'list', component: () => import('@/pages/List.vue') },

    // /apps/crm/crm-deal/view/open-deals -- a SAVED view, not a view type. v1's type
    // names (report/kanban/calendar) become reserved saved-view ids.
    { path: '/:doctype/view/:viewName', name: 'saved-view', component: () => import('@/pages/List.vue') },

    // /apps/crm/crm-deal/CRM-DEAL-01?view=open-deals&layout=Compact&from=crm
    // None of those three is a path segment, and that is a decision, not an omission.
    { path: '/:doctype/:name', name: 'record', component: () => import('@/pages/Record.vue') },
  ]
}

// NOT here, deliberately:
//   - no per-doctype route. The doctype is a param, so a bench with 400 doctypes has
//     4 routes, not 1,600. #42066 measured 143 microseconds per werkzeug rule for the
//     server-side equivalent, and that measurement is the reason.
//   - no opt-out. An app cannot hide its doctype from these routes (#42068).
