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
		map: "Map",
	},
	layout_mapped: {},

	is_app_route(path) {
		if (!path) return;
		// desk paths must begin with /app or doctype route
		if (path.substr(0, 1) === "/") path = path.substr(1);
		path = path.split("/");
		if (path[0]) {
			return path[0] === "app";
		}
	},

	setup() {
		// setup the route names by forming slugs of the given doctypes
		for (let doctype of frappe.boot.user.can_read) {
			this.routes[this.slug(doctype)] = { doctype: doctype };
		}
		if (frappe.boot.doctype_layouts) {
			for (let doctype_layout of frappe.boot.doctype_layouts) {
				this.routes[this.slug(doctype_layout.name)] = {
					doctype: doctype_layout.document_type,
					doctype_layout: doctype_layout.name,
				};
			}
		}
	},

	async route() {
		// resolve the route from the URL or hash
		// translate it so the objects are well defined
		// and render the page as required
		frappe.frappe_toolbar.show_app_logo();
		if (!frappe.app) return;

		let sub_path = this.get_sub_path();
		let current_app = localStorage.current_app;

		if (
			frappe.boot.setup_complete ||
			(current_app && frappe.boot.setup_wizard_not_required_apps?.includes(current_app))
		) {
			!frappe.re_route["setup-wizard"] && (frappe.re_route["setup-wizard"] = "app");
		} else if (!sub_path.startsWith("setup-wizard")) {
			frappe.re_route["setup-wizard"] && delete frappe.re_route["setup-wizard"];
			frappe.set_route(["setup-wizard"]);
		}
		if (this.re_route(sub_path)) return;

		this.current_sub_path = sub_path;
		this.current_route = await this.parse();
		this.set_history(sub_path);
		this.set_active_sidebar_item();
		this.render();
		this.set_title(sub_path);
		this.trigger("change");
	},

	async parse(route) {
		route = this.get_sub_path_string(route).split("/");
		if (!route) return [];
		route = $.map(route, this.decode_component);
		this.set_route_options_from_url();
		return await this.convert_to_standard_route(route);
	},

	async convert_to_standard_route(route) {
		// /app/settings = ["Workspaces", "Settings"]
		// /app/private/settings = ["Workspaces", "private", "Settings"]
		// /app/user = ["List", "User"]
		// /app/user/view/report = ["List", "User", "Report"]
		// /app/user/view/tree = ["Tree", "User"]
		// /app/user/user-001 = ["Form", "User", "user-001"]
		// /app/user/user-001 = ["Form", "User", "user-001"]
		// /app/event/view/calendar/default = ["List", "Event", "Calendar", "Default"]
		if (frappe.workspaces[route[0]]) {
			// public workspace
			route = ["Workspaces", frappe.workspaces[route[0]].name];
		} else if (route[0] == "private") {
			// private workspace
			let private_workspace = route[1] && `${route[1]}-${frappe.user.name.toLowerCase()}`;
			if (!frappe.workspaces[private_workspace]) {
				frappe.msgprint(__("Workspace <b>{0}</b> does not exist", [route[1]]));
				return ["Workspaces"];
			}
			route = ["Workspaces", "private", frappe.workspaces[private_workspace].name];
		} else if (this.routes[route[0]]) {
			// route
			route = await this.set_doctype_route(route);
		}

		return route;
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

			if (route[1] && route[1] === "view" && route[2]) {
				route = this.get_standard_route_for_list(
					route,
					doctype_route,
					meta.force_re_route_to_default_view && meta.default_view
						? meta.default_view
						: null
				);
			} else if (route[1] && route[1] !== "view") {
				let docname = route[1];
				if (route.length > 2) {
					docname = route.slice(1).join("/");
				}
				route = ["Form", doctype_route.doctype, docname];
			} else if (frappe.model.is_single(doctype_route.doctype)) {
				route = ["Form", doctype_route.doctype, doctype_route.doctype];
			} else if (meta.default_view) {
				if (meta.default_view === "Tree") {
					route = ["Tree", doctype_route.doctype];
				} else {
					route = [
						"List",
						doctype_route.doctype,
						this.list_views_route[meta.default_view.toLowerCase()],
					];
				}
			} else {
				route = ["List", doctype_route.doctype, "List"];
			}
			// reset the layout to avoid using incorrect views
			this.doctype_layout = doctype_route.doctype_layout;
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

	async set_active_sidebar_item() {
		frappe.app.sidebar.set_active_workspace_item();
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
							([key, value]) => `${key}=` + encodeURIComponent(JSON.stringify(value))
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
			// called as frappe.set_route('a/b/c')
			route = $.map(route[0].split("/"), this.decode_component);
		}

		if (route && route[0] == "") {
			route.shift();
		}

		if (route && ["desk", "app"].includes(route[0])) {
			// we only need subpath, remove "app" (or "desk")
			route.shift();
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
			return "/app/" + path_string;
		}

		// Resolution order
		// 1. User's default workspace in user doctype
		// 2. Private home
		// 3. Public home
		// 4. First workspace in list of current app
		// 5. First workspace in list
		let private_home = `home-${frappe.user.name.toLowerCase()}`;
		let default_workspace = frappe.router.slug(frappe.boot.user.default_workspace?.name || "");

		let workspace =
			frappe.workspaces[default_workspace] ||
			frappe.workspaces[private_home] ||
			frappe.workspaces["home"] ||
			Object.values(frappe.workspace_map).find((w) => w.app === frappe.current_app) ||
			Object.values(frappe.workspaces)[0];

		if (workspace) {
			return (
				"/app/" + (workspace.public ? "" : "private/") + frappe.router.slug(workspace.name)
			);
		}

		return "/app";
	},

	/**
	 * Changes the URL and calls the router.
	 *
	 * @param {string} path - The desired URI path to replace or push,
	 *    without query string. Example: "/app/todo"
	 * @param {string} query_params - The desired query parameter string.
	 * @returns {void}
	 */
	push_state(path, query_params = "") {
		if (window.location.pathname !== path || window.location.search !== query_params) {
			// push/replace state so the browser looks fine
			const method = frappe.route_flags.replace_route ? "replaceState" : "pushState";
			history[method](null, null, path);

			// now process the route
			this.route();
		}
	},

	get_sub_path_string(route) {
		// return clean sub_path from hash or url
		if (!route) {
			route = window.location.pathname;
		}

		return this.strip_prefix(route);
	},

	strip_prefix(route) {
		if (route.substr(0, 1) == "/") route = route.substr(1); // for /app/sub
		if (route == "app") route = route.substr(4); // for app
		if (route.startsWith("app/")) route = route.substr(4); // for desk/sub
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
