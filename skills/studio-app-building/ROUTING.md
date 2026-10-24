# Routing and boot data

- Studio creates the router: one route per published page. A route's `name` is
  the page title (`router.push({ name: "Ticket", params: { name } })`), so a
  retitle breaks code that names the page. A new screen is a new page; a custom
  404 is a page with route `/:pathMatch(.*)*`.
- App-wide routing goes in the app's router config, not a page script (which
  runs after the route already matched). It is plain vue-router: `router` is a
  vue-router `Router`, `route` a route record, and guards, aliases and options
  behave as in the vue-router docs; Studio only adds the three keys below.
  Custom apps keep it in the `Studio App.router_script` field as a bare object
  literal; standard apps in `<frappe_app>/studio/<studio_app>/router.ts` with
  `export default`.

  ```js
  {
  	routerOptions: { scrollBehavior: () => ({ top: 0 }) }, // createRouter options, minus routes/history
  	extendRoute(route) {
  		// each page record before the router exists; mutate it
  		if (route.name === "Tasks") route.alias = "/todo"
  	},
  	setup(router) {
  		// the live router: guards like router.beforeEach, router.afterEach, router.beforeResolve etc and redirects with router.addRoute if absolutely necessary.
  		router.beforeEach((to) => {
  			if (boot.onboarding_complete === false && to.name !== "Onboarding") {
  				return { name: "Onboarding" }
  			}
  		})
  	},
  }
  ```

- Boot data comes from the Frappe app's hook,
  `studio_app_boot = {"<studio_app>": "dotted.path.get_boot"}`, a function
  returning a dict. Pages, bindings and the router config read it as the global
  `boot` (`boot.onboarding_complete`); a key may be missing, so guard nested ones with `?.`.
