# Routing and boot data

## Page routes

- Studio creates one route for each page. The published build includes
  published pages only. The route's `name` is the page title. For example, use
  `router.push({ name: "Ticket", params: { name } })` to open a Ticket page.
  Changing the title breaks code that uses the old route name.
- Create a page for each new screen. For a custom 404 page, set its route to
  `/:pathMatch(.*)*`.

## Boot data

Set the Frappe app's hook to
`studio_app_boot = {"<studio_app>": "dotted.path.get_boot"}`.
The named function must return a dict.

Pages, bindings, and the router config read this data from the global `boot`
object. For example, use `boot.onboarding_complete`. Keys can be missing.
Use `?.` when accessing nested keys that may be missing.

## App router config

Put app-wide aliases, redirects, and guards in the app's router config.
A page script runs after route matching and is too late for this work.

Keep the config at the app root and use `export default`:

- In a custom app, use `router.js` in the file store (Studio App File).
- In a standard app, use `router.ts` or `router.js` under
  `<frappe_app>/studio/<studio_app>/`. Read the existing file before editing it
  and keep its extension. Create `router.ts` if neither file exists.

`router` is a Vue Router `Router`. `route` is a route record. Guards, aliases,
and options follow Vue Router behavior. Studio adds three optional config keys:

- `routerOptions`: options for `createRouter`, except `routes` and `history`.
- `extendRoute(route)`: change each page's route record before the router
  exists.
- `setup(router)`: configure the live router. Register guards with
  `router.beforeEach`, `router.afterEach`, or `router.beforeResolve`.
  Use `router.addRoute` for redirects only when necessary.

```js
export default {
	routerOptions: { scrollBehavior: () => ({ top: 0 }) },
	extendRoute(route) {
		if (route.name === "Tasks") route.alias = "/todo"
	},
	setup(router) {
		router.beforeEach((to) => {
			if (boot.onboarding_complete === false && to.name !== "Onboarding") {
				return { name: "Onboarding" }
			}
		})
	},
}
```
