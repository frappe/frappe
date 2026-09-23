// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// route urls to their virtual pages

// re-route map (for rename)
frappe.provide("frappe.views");
frappe.re_route = { "#login": "" };
frappe.route_titles = {};
frappe.route_flags = {};
frappe.route_history = [];
frappe.view_factory = {};
frappe.view_factories = [];
frappe.route_options = null;
frappe.open_in_new_tab = false;
frappe.route_hooks = {};

window.addEventListener("popstate", (e) => {
	// forward-back button, just re-render based on current route
	frappe.router.route();
	e.preventDefault();
	return false;
});

// Capture all clicks so that the target is managed with push-state
$("body").on("click", "a", function (e) {
	const target_element = e.currentTarget;
	const href = target_element.getAttribute("href");
	const is_on_same_host = target_element.hostname === window.location.hostname;

	if (frappe.router.show_external_link_warning_if_needed(target_element)) {
		e.preventDefault();
		return; // warning shown
	}

	if (target_element.getAttribute("target") === "_blank") {
		return;
	}

	const override = (route) => {
		e.preventDefault();
		frappe.set_route(route);
		return false;
	};

	// click handled, but not by href
	if (
		!is_on_same_host || // external link
		target_element.getAttribute("onclick") || // has a handler
		e.ctrlKey ||
		e.metaKey || // open in a new tab
		href === "#" // hash is home
	) {
		return;
	}

	if (frappe.router.is_app_route(target_element.pathname)) {
		// target has "/app, this is a v2 style route.
		if (target_element.search) {
			frappe.route_options = {};
			let params = new URLSearchParams(target_element.search);
			for (const [key, value] of params) {
				frappe.route_options[key] = value;
			}
		}
		if (target_element.hash) {
			frappe.route_hash = target_element.hash;
		}
		return override(target_element.pathname);
	}
});

frappe.router = {
	current_route: null,
	routes: {},
	// slug -> shell, and the shell the URL on screen names, or null when it names none. Nothing
	// writes the shell into a URL yet, so `current_shell` is only ever set by a hand-typed one.
	shell_routes: {},
	current_shell: null,
	factory_views: ["form", "list", "report", "tree", "print", "dashboard"],
	list_views: [
		"list",
		"kanban",
		"report",
		"calendar",
		"tree",
		"gantt",
		"dashboard",
		"image",
		"inbox",
		"map",
	],
	list_views_route: {
		list: "List",
		kanban: "Kanban",
		report: "Report",
		calendar: "Calendar",
		tree: "Tree",
		gantt: "Gantt",
		dashboard: "Dashboard",
		image: "Image",
		inbox: "Inbox",
		file: "Home",
		home: "Home",
		map: "Map",
	},
	layout_mapped: {},

	is_app_route(path) {
		if (!path) return;
		// desk paths must begin with /app or doctype route
		if (path.substr(0, 1) === "/") path = path.substr(1);
		path = path.split("/");
		if (path[0]) {
			return path[0] === "desk";
		}
	},

	setup() {
		// setup the route names by forming slugs of the given doctypes
		for (let doctype of frappe.boot.user.can_read) {
			this.routes[this.slug(doctype)] = { doctype: doctype };
		}
		this.setup_shell_routes();
	},

	// slug -> shell, over the shells this user has. Built here rather than on demand because the
	// payload it comes from does not change during a session, and the parser reads it on every
	// route.
	setup_shell_routes() {
		this.shell_routes = {};
		for (let shell of Object.keys(frappe.boot.module_sidebars || {})) {
			this.shell_routes[this.shell_slug(shell)] = shell;
		}

		// `private` is a segment the desk already spends: `/desk/private/<workspace>` names a
		// user's own workspace. There is a `Private` module with a shell of its own, so its slug
		// lands on the same segment, and reading that segment as a shell would turn
		// `/desk/private/settings` from someone's private workspace into the public one of that
		// name. The reserved word wins, and the `Private` shell is reached the way it always
		// was.
		delete this.shell_routes["private"];
	},

	async route() {
		// resolve the route from the URL or hash
		// translate it so the objects are well defined
		// and render the page as required
		if (!frappe.app) return;

		let sub_path = this.get_sub_path();

		if (frappe.boot.setup_complete) {
			!frappe.re_route["setup-wizard"] && (frappe.re_route["setup-wizard"] = "app");
		} else if (
			frappe.boot.setup_wizard_url &&
			!frappe.boot.setup_wizard_url.startsWith("/app/") &&
			!frappe.boot.setup_wizard_url.startsWith("/desk/")
		) {
			window.location.replace(frappe.boot.setup_wizard_url);
			return;
		} else if (!sub_path.startsWith("setup-wizard")) {
			frappe.re_route["setup-wizard"] && delete frappe.re_route["setup-wizard"];
			frappe.set_route(["setup-wizard"]);
		}
		if (this.re_route(sub_path)) return;

		this.current_sub_path = sub_path;
		this.current_route = await this.parse();
		this.write_shell_into_url();

		this.set_history(sub_path);
		this.render();
		this.set_title(sub_path);
		this.trigger("change", this);
	},

	async parse(route) {
		route = this.get_sub_path_string(route).split("/");
		if (!route) return [];
		route = $.map(route, this.decode_component);
		route = this.take_shell_from(route);
		this.set_route_options_from_url();
		return await this.convert_to_standard_route(route);
	},

	async convert_to_standard_route(route) {
		// /desk/settings = ["Workspaces", "Settings"]
		// /desk/private/settings = ["Workspaces", "private", "Settings"]
		// /desk/user = ["List", "User"]
		// /desk/user/view/report = ["List", "User", "Report"]
		// /desk/user/view/tree = ["Tree", "User"]
		// /desk/user/user-001 = ["Form", "User", "user-001"]
		// /desk/user/user-001 = ["Form", "User", "user-001"]
		// /desk/event/view/calendar/default = ["List", "Event", "Calendar", "Default"]
		switch (this.segment_kind(route[0])) {
			case "workspace":
				return ["Workspaces", frappe.workspaces[route[0]].name];

			case "private": {
				let private_workspace = route[1] && frappe.router.slug(`${route[1]}`);
				if (!frappe.workspaces[private_workspace]) {
					frappe.msgprint(
						__("Workspace <b>{0}</b> does not exist", [
							frappe.utils.xss_sanitise(route[1]),
						])
					);
					return ["Workspaces"];
				}
				return ["Workspaces", "private", frappe.workspaces[private_workspace].name];
			}

			case "doctype":
				return await this.set_doctype_route(route);

			default:
				// A page, or a word the desk does not know: both are left for `render_page`.
				// Clear stale layout -- standard routes skip set_doctype_route where it is
				// normally reset.
				this.doctype_layout = null;
				return route;
		}
	},

	// What the first segment of a route names, or null when the desk has never heard of it.
	//
	// One list, in one place, because two things need it and they must not drift apart:
	// `convert_to_standard_route` turns a segment into a standard route, and `take_shell_from`
	// decides whether a shell may be taken off the front of one. When they disagreed,
	// `/desk/<shell>/query-report/<name>` rendered nothing at all.
	//
	// Ordered as the desk resolves: a workspace first, since a workspace slug and a doctype slug
	// collide on 31 segments with erpnext installed and the workspace has always won.
	segment_kind(segment) {
		if (!segment) return null;
		if (frappe.workspaces?.[segment]) return "workspace";
		if (segment === "private") return "private";
		if (this.routes[segment]) return "doctype";

		// Two registries, because there are two kinds of page. `page_info` holds the `Page`
		// documents this user may see; `standard_pages` holds the ones the desk registers in
		// itself, which are documents nowhere. `query-report` is the second kind, and
		// `pageview.with_page` reads both, so this does too.
		if (frappe.boot.page_info?.[segment] || frappe.standard_pages?.[segment]) return "page";

		// A standard route, which is the spelling the desk used before friendly URLs and still
		// honours: `/desk/List/DocType/List`, `/desk/Form/User/Administrator`. The desk never
		// writes one any more, so the only URLs in this shape are old bookmarks and old links,
		// and they have to keep working.
		//
		// Last, because a view name and a doctype slug collide: `Report` is both a view and a
		// doctype, and `/desk/report` has always been the Report list.
		//
		// `render_page` decides what these name by looking for a view factory, so this asks the
		// same registry rather than keeping a list of view names beside it that could drift.
		if (frappe.views?.[frappe.utils.to_title_case(segment) + "Factory"]) return "view";

		return null;
	},

	doctype_route_exist(route) {
		route = this.get_sub_path_string(route).split("/");
		return this.routes[route[0]];
	},

	set_doctype_route(route) {
		let doctype_route = this.routes[route[0]];

		return frappe.model.with_doctype(doctype_route.doctype).then(() => {
			// doctype route
			let meta = frappe.get_meta(doctype_route.doctype);
			this.meta = meta;
			let default_view = meta.default_view;
			if (default_view === "Report" && !frappe.model.can_get_report(doctype_route.doctype)) {
				default_view = null;
			}
			if (route[1] && route[1] === "view" && route[2]) {
				route = this.get_standard_route_for_list(
					route,
					doctype_route,
					meta.force_re_route_to_default_view && default_view ? default_view : null
				);
			} else if (route[1] && route[1] !== "view") {
				let docname = route[1];
				if (route.length > 2) {
					docname = route.slice(1).join("/");
				}
				route = ["Form", doctype_route.doctype, docname];
			} else if (frappe.model.is_single(doctype_route.doctype)) {
				route = ["Form", doctype_route.doctype, doctype_route.doctype];
			} else if (default_view) {
				if (default_view === "Tree") {
					route = ["Tree", doctype_route.doctype];
				} else {
					route = [
						"List",
						doctype_route.doctype,
						this.list_views_route[default_view.toLowerCase()],
					];
				}
			} else {
				route = ["List", doctype_route.doctype, "List"];
			}

			const from_route_options = frappe.route_options?.layout;
			const from_url = new URLSearchParams(window.location.search).get("layout");
			const layout_param = from_route_options || from_url;

			this.doctype_layout = null;
			if (layout_param) {
				const matched = (frappe.boot.doctype_layouts || []).find(
					(l) => l.name === layout_param && l.document_type === doctype_route.doctype
				);
				if (matched) this.doctype_layout = matched.name;
				if (from_route_options) delete frappe.route_options.layout;
			}

			const _url = new URL(window.location.href);
			if (this.doctype_layout) {
				_url.searchParams.set("layout", this.doctype_layout);
			} else {
				_url.searchParams.delete("layout");
			}
			history.replaceState(history.state, "", _url.toString());

			return route;
		});
	},

	get_standard_route_for_list(route, doctype_route, default_view) {
		let standard_route;
		let _route = default_view || route[2] || "";

		if (_route.toLowerCase() === "tree") {
			standard_route = ["Tree", doctype_route.doctype];
		} else {
			let new_route = this.list_views_route[_route.toLowerCase()];
			let re_route = route[2].toLowerCase() !== new_route?.toLowerCase();

			if (re_route) {
				/**
				 * In case of force_re_route, the url of the route should change,
				 * if the _route and route[2] are different, it means there is a default_view
				 * with force_re_route enabled.
				 *
				 * To change the url, to the correct view, the route[2] is changed with default_view
				 *
				 * Eg: If default_view is set to Report with force_re_route enabled and user routes
				 * to List,
				 * route: [todo, view, list]
				 * default_view: report
				 *
				 * replaces the list to report and re-routes to the new route but should be replaced in
				 * the history since the list route should not exist in history as we are rerouting it to
				 * report
				 */
				frappe.route_flags.replace_route = true;

				route[2] = _route.toLowerCase();
				this.set_route(route);
			}

			standard_route = [
				"List",
				doctype_route.doctype,
				this.list_views_route[_route.toLowerCase()],
			];

			// calendar / kanban / dashboard / folder
			if (route[3]) standard_route.push(...route.slice(3, route.length));
		}

		return standard_route;
	},

	set_history() {
		frappe.route_history.push(this.current_route);
		frappe.ui.hide_open_dialog();
	},

	render() {
		if (this.current_route[0]) {
			this.render_page();
		} else {
			// Show home
			frappe.views.pageview.show("");
		}
	},

	render_page() {
		// create the page generator (factory) object and call `show`
		// if there is no generator, render the `Page` object

		const route = this.current_route;
		const factory = frappe.utils.to_title_case(route[0]);
		if (route[1] && frappe.views[factory + "Factory"]) {
			route[0] = factory;
			// has a view generator, generate!
			if (!frappe.view_factory[factory]) {
				frappe.view_factory[factory] = new frappe.views[factory + "Factory"]();
			}

			frappe.view_factory[factory].show();
		} else {
			// show page
			const route_name = frappe.utils.xss_sanitise(route[0]);
			if (frappe.views.pageview) {
				frappe.views.pageview.show(route_name);
			}
		}
	},

	re_route(sub_path) {
		if (frappe.re_route[sub_path] !== undefined) {
			// after saving a doc, for example,
			// "new-doctype-1" and the renamed "TestDocType", both exist in history
			// now if we try to go back,
			// it doesn't allow us to go back to the one prior to "new-doctype-1"
			// Hence if this check is true, instead of changing location hash,
			// we just do a back to go to the doc previous to the "new-doctype-1"
			const re_route_val = this.get_sub_path(frappe.re_route[sub_path]);
			if (re_route_val === this.current_sub_path) {
				window.history.back();
			} else {
				frappe.set_route(re_route_val);
			}

			return true;
		}
	},

	set_title(sub_path) {
		if (frappe.route_titles[sub_path]) {
			frappe.utils.set_title(frappe.route_titles[sub_path]);
		}
	},

	set_route() {
		// set the route (push state) with given arguments
		// example 1: frappe.set_route('a', 'b', 'c');
		// example 2: frappe.set_route(['a', 'b', 'c']);
		// example 3: frappe.set_route('a/b/c');
		let route = Array.from(arguments);

		return new Promise((resolve) => {
			route = this.get_route_from_arguments(route);
			route = this.convert_from_standard_route(route);
			let sub_path = this.make_url(route);
			sub_path += frappe.route_hash || "";
			frappe.route_hash = null;
			if (frappe.open_in_new_tab) {
				localStorage["route_options"] = JSON.stringify(frappe.route_options);
				window.open(sub_path, "_blank");
				frappe.open_in_new_tab = false;
			} else {
				try {
					const route_options = frappe.route_options || {};
					const query_params = Object.entries(route_options)
						.map(
							([key, value]) =>
								`${key}=` +
								encodeURIComponent(
									value !== null && typeof value === "object"
										? JSON.stringify(value)
										: String(value)
								)
						)
						.join("&");
					this.push_state(sub_path, query_params ? `?${query_params}` : "");
				} catch (e) {
					this.push_state(sub_path);
				}
			}
			setTimeout(() => {
				frappe.after_ajax &&
					frappe.after_ajax(() => {
						resolve();
					});
			}, 100);
		}).finally(() => (frappe.route_flags = {}));
	},

	get_route_from_arguments(route) {
		if (route.length === 1 && $.isArray(route[0])) {
			// called as frappe.set_route(['a', 'b', 'c']);
			route = route[0];
		}
		if (route.length === 1 && route[0] && route[0].includes("/")) {
			// called as frappe.set_route('a/b/c') or frappe.set_route('/desk/a/b?x=1')
			const qIdx = route[0].indexOf("?");
			let path = qIdx >= 0 ? route[0].slice(0, qIdx) : route[0];
			let query_string = qIdx >= 0 ? route[0].slice(qIdx + 1) : null;
			if (query_string) {
				frappe.route_options = frappe.route_options || {};
				new URLSearchParams(query_string).forEach((v, k) => (frappe.route_options[k] = v));
			}
			route = $.map(path.split("/"), this.decode_component);
		}

		if (route && route[0] == "") {
			route.shift();
		}

		if (route && ["desk", "app"].includes(route[0])) {
			// we only need subpath, remove "app" (or "desk")
			route.shift();
		}

		// Drop the shell, for the same reason the prefix above is dropped: it is part of the
		// address, not part of the route. `make_url` spells routes without one and
		// `write_shell_into_url` puts it back afterwards, so keeping it here would only give the
		// same place two spellings.
		//
		// A route arrives carrying one whenever it was read off the page rather than built:
		// `set_route(location.pathname)`, or the body-level handler above passing the `href` of a
		// link that resolved against a URL the desk had already written a shell into. Every
		// relative link on the page is now such a link, including `href=""`, which is how a
		// button that meant to do nothing to the route ended up re-routing.
		//
		// Left in, `push_state` compares a path with a shell against `path_on_screen()`, which
		// has none, reads every self-link as a move, and re-renders the page under it -- throwing
		// away whatever the render was holding. The form sidebar lost its "Show All" this way.
		if (this.begins_with_shell(route)) {
			route.shift();
		}

		// Handle cases where "/" is part of the name
		if (route[0] === "Form" && route.length > 3) {
			route = [route[0], route[1], route.slice(2).join("/")];
		}

		return route;
	},

	convert_from_standard_route(route) {
		// ["List", "Sales Order"] => /sales-order
		// ["Form", "Sales Order", "SO-0001"] => /sales-order/SO-0001
		// ["Tree", "Account"] = /account/view/tree

		const view = route[0] ? route[0].toLowerCase() : "";
		let new_route = route;
		if (view === "list") {
			if (route[2] && route[2] !== "list" && !$.isPlainObject(route[2])) {
				new_route = [this.slug(route[1]), "view", route[2].toLowerCase()];

				// calendar / inbox / file folder
				if (route[3]) new_route.push(...route.slice(3, route.length));
			} else {
				if ($.isPlainObject(route[2])) {
					frappe.route_options = route[2];
				}
				new_route = [this.slug(route[1])];
			}
		} else if (view === "form") {
			new_route = [this.slug(route[1])];
			if (route[2]) {
				// if not single
				new_route.push(route[2]);
			}
		} else if (view === "tree") {
			new_route = [this.slug(route[1]), "view", "tree"];
		}

		return new_route;
	},

	slug_parts(route) {
		// slug doctype

		// if app is part of the route, then first 2 elements are "" and "app"
		if (route[0] && this.factory_views.includes(route[0].toLowerCase())) {
			route[0] = route[0].toLowerCase();
			route[1] = this.slug(route[1]);
		}
		return route;
	},

	// This writes no shell into the path, and `write_shell_into_url` puts it there once the route
	// has been parsed. Doing it here looks tidier and cannot be made correct: `set_route` also
	// takes a path, `frappe.set_route("/desk/item/ITEM-0001")`, which arrives already slugged and
	// no longer says which segment is the entity, so the shell would be picked by reading a
	// document's name as one.
	make_url(params) {
		let path_string = $.map(params, function (a) {
			if ($.isPlainObject(a)) {
				frappe.route_options = a;
				return null;
			} else {
				return encodeURIComponent(String(a));
			}
		}).join("/");

		if (path_string) {
			return "/desk/" + path_string;
		}

		if (params.length == 0) {
			return "/desk";
		}
		// Resolution order
		// 1. User's default workspace in user doctype
		// 2. Private home
		// 3. Public home
		// 4. First workspace in list of current app
		// 5. First workspace in list

		return "/desk";
	},

	/**
	 * Changes the URL and calls the router.
	 *
	 * @param {string} path - The desired URI path to replace or push,
	 *    without query string. Example: "/desk/todo"
	 * @param {string} query_params - The desired query parameter string.
	 * @returns {void}
	 */
	push_state(path, query_params = "") {
		if (this.path_on_screen() !== path || window.location.search !== query_params) {
			// push/replace state so the browser looks fine
			const method = frappe.route_flags.replace_route ? "replaceState" : "pushState";
			history[method](null, null, path + query_params);

			// now process the route
			this.route();
		}
	},

	// The path on screen, spelled the way `make_url` would have spelled it: without the shell.
	//
	// `push_state` has to answer whether it is being asked for somewhere else, and it cannot
	// compare the address bar against what it is handed, because the two describe the same place
	// in two spellings. `set_route` writes no shell, since `make_url` is also given ready-made
	// paths and cannot tell which segment is the entity, while `write_shell_into_url` always
	// writes one. The path for the route already on screen therefore arrives here exactly one
	// segment shorter than the URL it is being compared with.
	//
	// Compared literally it reads as a change every time, and a page that re-issues its own route
	// while rendering never settles: `set_route` drops the shell, the router writes it back, the
	// re-render calls `set_route` again. `permission-manager` does precisely that, from a Link
	// field whose `change` fires on every render because a field with no document behind it has
	// no old value to be equal to. It looped for as long as the tab was open, flickering and
	// filling the back button with entries nobody had visited.
	path_on_screen() {
		const path = window.location.pathname;
		if (!this.current_shell) return path;

		// `current_shell` is only ever set by taking a shell off the front of the route or by
		// writing one there, so whenever it is set there is a shell segment to drop.
		return "/desk/" + this.strip_prefix(path).split("/").slice(1).join("/");
	},

	get_sub_path_string(route) {
		// return clean sub_path from hash or url
		if (!route) {
			route = window.location.pathname;
		}

		return this.strip_prefix(route);
	},

	strip_prefix(route) {
		if (route.substr(0, 1) == "/") route = route.substr(1); // for /desk/sub
		if (route == "desk") route = route.substr(4); // for app
		if (route.startsWith("desk/")) route = route.substr(4); // for desk/sub
		if (route.substr(0, 1) == "/") route = route.substr(1);
		if (route.substr(0, 1) == "#") route = route.substr(1);
		if (route.substr(0, 1) == "!") route = route.substr(1);
		return route;
	},

	get_sub_path(route) {
		var sub_path = this.get_sub_path_string(route);
		route = $.map(sub_path.split("/"), this.decode_component).join("/");

		return route;
	},

	set_route_options_from_url() {
		// set query parameters as frappe.route_options
		let query_string = window.location.search;

		if (!frappe.route_options) {
			frappe.route_options = {};
		}

		if (localStorage.getItem("route_options")) {
			frappe.route_options = JSON.parse(localStorage.getItem("route_options"));
			localStorage.removeItem("route_options");
		}

		let params = new URLSearchParams(query_string);
		for (const [key, value] of params) {
			frappe.route_options[key] = value;
		}
	},

	decode_component(r) {
		try {
			return decodeURIComponent(r);
		} catch (e) {
			if (e instanceof URIError) {
				// legacy: not sure why URIError is ignored.
				return r;
			} else {
				throw e;
			}
		}
	},

	slug(name) {
		return name.toLowerCase().replace(/ /g, "-");
	},

	// A shell reaches the URL through this rather than through `slug`, because a shell may be
	// named with an `&`. hrms named two that way deliberately: a module folder is an imported
	// Python package and cannot hold one, so the sidebar's own name is the only place the
	// ampersand can live. `&` is legal in a path, but `%26` is not something anyone types or
	// reads, so it is spelled out here and `Shift & Attendance` becomes `shift-and-attendance`.
	//
	// This is deliberately not reversible, and does not need to be. A segment is turned back into
	// a shell by looking it up in `shell_routes`, never by transforming it, so the only thing
	// required of this is that two shells do not collide on one slug.
	shell_slug(name) {
		return name.toLowerCase().replace(/&/g, " and ").trim().replace(/\s+/g, "-");
	},

	// Take a leading shell off the route, when it is carrying one, and remember it.
	//
	// `/desk/stock/item` is the Item list in the Stock shell; `/desk/item/ITEM-0001` is a form.
	// Both are two segments, so their shape cannot tell them apart, and the answer comes from
	// what the segments name: the first has to be a shell this user has, and what follows it has
	// to name something the desk can route to on its own. In the first, `stock` is a shell and
	// `item` is a doctype, so the shell comes off. In the second, `item` is not a shell, so
	// nothing does.
	//
	// A shell whose slug is also a doctype is never taken off the front. On a site with erpnext
	// and hrms there are three: `Workflow`, `Newsletter` and `Raven Bot` each name a module with a
	// sidebar and a doctype at once. `/desk/workflow/<name>` has always been a Workflow form, and
	// the parser runs before any document is fetched, so it cannot ask whether a Workflow called
	// `item` exists before reading `/desk/workflow/item` as the Item list. The doctype wins, the
	// same way a workspace wins over a doctype in `segment_kind`, and `write_shell_into_url`
	// never writes one of these shells in front of another route, so the desk does not produce
	// a URL it would then misread.
	//
	// A one-segment route never carries a shell. `/desk/stock` stays the Stock workspace it has
	// always been, and a shell is reached through the two-segment form instead.
	take_shell_from(route) {
		if (!this.begins_with_shell(route)) {
			this.current_shell = null;
			return route;
		}

		this.current_shell = this.shell_routes[route[0]];
		return route.slice(1);
	},

	// Whether a route begins with a shell segment that can be taken off the front, by the rule
	// `take_shell_from` describes. Asked separately by `get_route_from_arguments`, which has to
	// drop a shell without adopting it.
	begins_with_shell(route) {
		if (route.length <= 1 || !this.shell_routes?.[route[0]]) return false;
		if (this.segment_kind(route[0]) === "doctype") return false;
		return this.route_names_something(route[1]);
	},

	// The shell a URL for this route should name, or null when the desk cannot say yet.
	//
	// The rule itself lives on the sidebar, which is what holds the payload it is decided from.
	// This is only the way in, and it answers null before there is a sidebar to ask -- during the
	// first route of a cold load, and on a site where setup is not complete.
	shell_for_route(route) {
		return frappe.app?.sidebar?.shell_for_route?.(route) || null;
	},

	// Put the shell into the URL on screen when it is missing or naming one that cannot show the
	// route. `/desk/item` becomes `/desk/stock/item`; `/desk/geo/item` becomes it too.
	//
	// This is what makes every URL that reaches the desk carry a shell, whoever wrote it: a link
	// in an email, a bookmark from before this existed, an href built by a part of the desk that
	// never asked. `set_route` writes the shell in from the start, so a URL the desk itself
	// produced arrives correct and this does nothing.
	//
	// `history.replaceState` rather than `set_route`: the page is already rendering the right
	// thing and only the address bar is behind, so pushing would put a URL nobody visited into
	// the back button. Replacing is also what makes this safe to call on every route, since it
	// does not call `route()` and so cannot loop.
	//
	// The path is rebuilt by putting the shell in front of what is already there rather than by
	// regenerating it from the route, so a document whose name needed encoding keeps the exact
	// spelling it arrived with.
	write_shell_into_url() {
		if (!this.current_route?.length) return;

		const shell = this.shell_for_route(this.current_route);
		if (!shell || shell === this.current_shell) return;

		let rest = this.strip_prefix(window.location.pathname);
		// Drop the shell already there, which is a shell that cannot show this route.
		if (this.current_shell) rest = rest.split("/").slice(1).join("/");
		if (!rest) return;

		// Nothing is gained by saying it twice. `/desk/build` is the Build workspace, and its
		// shell is Build, so `/desk/build/build` would add a segment and no information. Most
		// workspaces are named after the shell they live in -- 30 of 52 on a site with erpnext
		// and hrms -- and the ones that are not, such as `Invoicing` under Accounts, are exactly
		// the ones where the shell is worth saying.
		//
		// It falls out of the same rule for the reserved segment: `/desk/private/<workspace>`
		// under the `Private` shell already begins with `private`, so it is left alone too,
		// while a private workspace belonging to some other module still gets that module.
		//
		// "Left alone" means no segment is added, not that the URL is kept. A stale shell has
		// already been dropped from `rest` above, and it still has to leave the address bar:
		// `/desk/stock/build` is the Build workspace under a shell that cannot show it, and
		// returning here without writing kept `stock` on screen and in every link copied from
		// it.
		const slug = this.shell_slug(shell);
		const names_itself = rest === slug || rest.startsWith(slug + "/");

		// A shell that is also a doctype cannot go in front: `/desk/workflow/item` reads back as
		// the Workflow named `item`, not the Item list (see `take_shell_from`). The route keeps
		// no shell in its URL, and the sidebar stays on the shell on screen until a reload.
		const unwritable = !names_itself && this.segment_kind(slug) === "doctype";
		const path = "/desk/" + (names_itself || unwritable ? rest : slug + "/" + rest);
		if (path === window.location.pathname) return;

		// `path_on_screen` strips one segment whenever this is set, so it has to say what the URL
		// now spells: the shell when one was written, nothing when the route already begins with
		// its own shell's slug or the shell could not be written.
		this.current_shell = names_itself || unwritable ? null : shell;
		history.replaceState(
			history.state,
			"",
			path + window.location.search + window.location.hash
		);
	},

	// Whether a segment names something the desk can route to on its own, which is what a shell
	// has to be followed by before it may be taken off the front of a route.
	route_names_something(segment) {
		return !!this.segment_kind(segment);
	},

	show_external_link_warning_if_needed(/** @type {HTMLAnchorElement} */ aElement) {
		try {
			if (!aElement?.href) {
				return false; // not a true link
			}

			// Get the external link handling type
			/** @type {'Always' | 'Ask' | 'Never' | null} */
			const showWarningWhen = frappe.boot.show_external_link_warning || "Never";
			if (showWarningWhen == "Never") {
				return false; // the feature is disabled
			}

			// Check that the origin is external (does not prevent self-clickjacking on GET endpoints)
			const url = new URL(aElement.href);
			const hostname = url.hostname;

			// For blob: URLs, skip the link check
			if (url.protocol === "blob:") {
				return false; // blob: URLs are not checked
			}
			if (hostname === window.location.hostname) {
				return false; // self-linking is allowed
			}

			// Check if the origin was ignored by the user
			const localStorageKey = `skip-external-link-warning:${hostname}`;
			if (showWarningWhen == "Ask" && localStorage.getItem(localStorageKey)) {
				return false; // user chose to skip warning forever
			}

			// Check if the link if inside the confirmation popup
			const incominSkipToken = aElement.getAttribute("data-skip-link-warning");
			if (incominSkipToken && sessionStorage.getItem(incominSkipToken) == "1") {
				return false; // anchor is the confirmation itself
			}

			// Finally, show the warning
			const dialog = new frappe.ui.Dialog({
				title: __("Warning"),
				primary_action: null,
				fields: [
					{
						fieldname: "warning_html",
						fieldtype: "HTML",
					},
					{
						fieldname: "confirm_checkbox",
						fieldtype: "Check",
						label: __("Do not warn me again about {0}", [
							frappe.utils.escape_html(hostname).bold(),
						]),
						default: 0,
						hidden: showWarningWhen == "Always",
						change() {
							if (dialog.get_value("confirm_checkbox")) {
								localStorage.setItem(localStorageKey, "1");
							} else {
								localStorage.removeItem(localStorageKey);
							}
						},
					},
				],
			});

			const warningElement = dialog.fields_dict.warning_html.$wrapper.get(0);

			const introElement = document.createElement("p");
			introElement.textContent = __(
				"You are about to open an external link. To confirm, click the link again."
			);
			warningElement.appendChild(introElement);

			const boxElement = document.createElement("div");
			boxElement.classList.add("border", "rounded-lg", "p-3", "mt-6", "mb-6", "text-center");
			warningElement.appendChild(boxElement);

			const hintElement = document.createElement("p");
			hintElement.classList.add("text-sm", "mb-1");
			hintElement.textContent = __("You will be redirected to:");
			boxElement.appendChild(hintElement);

			const confirmElement = document.createElement("a");
			confirmElement.classList.add("text-sm", "font-mono");
			confirmElement.style.wordBreak = "break-all";
			confirmElement.textContent = aElement.href;
			confirmElement.href = aElement.href;
			confirmElement.target = aElement.target;
			confirmElement.addEventListener("click", () => dialog.hide(), { capture: true });

			// Add a token to skip the warning when clicking inside the confirmation dialog
			const skipToken = frappe.utils.get_random(16);
			confirmElement.setAttribute("data-skip-link-warning", skipToken);
			sessionStorage.setItem(skipToken, "1");
			boxElement.appendChild(confirmElement);

			dialog.show();
			return true; // prevent default handling
		} catch (e) {
			console.error(e);
		}
		return false;
	},
};

// global functions for backward compatibility
frappe.get_route = () => frappe.router.current_route;
frappe.get_route_str = () => frappe.router.current_route.join("/");
frappe.set_route = function () {
	return frappe.router.set_route.apply(frappe.router, arguments);
};

frappe.get_prev_route = function () {
	if (frappe.route_history && frappe.route_history.length > 1) {
		return frappe.route_history[frappe.route_history.length - 2];
	} else {
		return [];
	}
};

frappe.set_re_route = function () {
	var tmp = frappe.router.get_sub_path();
	frappe.set_route.apply(null, arguments);
	frappe.re_route[tmp] = frappe.router.get_sub_path();
};

frappe.has_route_options = function () {
	return Boolean(Object.keys(frappe.route_options || {}).length);
};

frappe.utils.make_event_emitter(frappe.router);
