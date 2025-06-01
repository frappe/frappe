// Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// route urls to their virtual pages

// re-route map (for rename)
nts.provide("nts.views");
nts.re_route = { "#login": "" };
nts.route_titles = {};
nts.route_flags = {};
nts.route_history = [];
nts.view_factory = {};
nts.view_factories = [];
nts.route_options = null;
nts.open_in_new_tab = false;
nts.route_hooks = {};

$(window).on("hashchange", function (e) {
	// v1 style routing, route is in hash
	if (window.location.hash && !nts.router.is_app_route(e.currentTarget.pathname)) {
		let sub_path = nts.router.get_sub_path(window.location.hash);
		nts.router.push_state(sub_path);
		return false;
	}
});

window.addEventListener("popstate", (e) => {
	// forward-back button, just re-render based on current route
	nts.router.route();
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
		nts.set_route(route);
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

	if (href && href.startsWith("#")) {
		// target startswith "#", this is a v1 style route, so remake it.
		return override(target_element.hash);
	}

	if (nts.router.is_app_route(target_element.pathname)) {
		// target has "/app, this is a v2 style route.
		if (target_element.search) {
			nts.route_options = {};
			let params = new URLSearchParams(target_element.search);
			for (const [key, value] of params) {
				nts.route_options[key] = value;
			}
		}
		if (target_element.hash) {
			nts.route_hash = target_element.hash;
		}
		return override(target_element.pathname);
	}
});

nts.router = {
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
		for (let doctype of nts.boot.user.can_read) {
			this.routes[this.slug(doctype)] = { doctype: doctype };
		}
		if (nts.boot.doctype_layouts) {
			for (let doctype_layout of nts.boot.doctype_layouts) {
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

		if (!nts.app) return;

		let sub_path = this.get_sub_path();
		if (nts.boot.setup_complete) {
			!nts.re_route["setup-wizard"] && (nts.re_route["setup-wizard"] = "app");
		} else if (!sub_path.startsWith("setup-wizard")) {
			nts.re_route["setup-wizard"] && delete nts.re_route["setup-wizard"];
			nts.set_route(["setup-wizard"]);
		}
		if (this.re_route(sub_path)) return;

		this.current_sub_path = sub_path;
		this.current_route = await this.parse();
		this.set_history(sub_path);
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

		if (nts.workspaces[route[0]]) {
			// public workspace
			route = ["Workspaces", nts.workspaces[route[0]].title];
		} else if (route[0] == "private") {
			// private workspace
			let private_workspace = route[1] && `${route[1]}-${nts.user.name.toLowerCase()}`;
			if (!nts.workspaces[private_workspace] && localStorage.new_workspace) {
				let new_workspace = JSON.parse(localStorage.new_workspace);
				if (nts.router.slug(new_workspace.title) === route[1]) {
					nts.workspaces[private_workspace] = new_workspace;
				}
			}
			if (!nts.workspaces[private_workspace]) {
				nts.msgprint(__("Workspace <b>{0}</b> does not exist", [route[1]]));
				return ["Workspaces"];
			}
			route = ["Workspaces", "private", nts.workspaces[private_workspace].title];
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

		return nts.model.with_doctype(doctype_route.doctype).then(() => {
			// doctype route
			let meta = nts.get_meta(doctype_route.doctype);

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
			} else if (nts.model.is_single(doctype_route.doctype)) {
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
				nts.route_flags.replace_route = true;

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
		nts.route_history.push(this.current_route);
		nts.ui.hide_open_dialog();
	},

	render() {
		if (this.current_route[0]) {
			this.render_page();
		} else {
			// Show home
			nts.views.pageview.show("");
		}
	},

	render_page() {
		// create the page generator (factory) object and call `show`
		// if there is no generator, render the `Page` object

		const route = this.current_route;
		const factory = nts.utils.to_title_case(route[0]);

		if (route[1] && nts.views[factory + "Factory"]) {
			route[0] = factory;
			// has a view generator, generate!
			if (!nts.view_factory[factory]) {
				nts.view_factory[factory] = new nts.views[factory + "Factory"]();
			}

			nts.view_factory[factory].show();
		} else {
			// show page
			const route_name = nts.utils.xss_sanitise(route[0]);
			if (nts.views.pageview) {
				nts.views.pageview.show(route_name);
			}
		}
	},

	re_route(sub_path) {
		if (nts.re_route[sub_path] !== undefined) {
			// after saving a doc, for example,
			// "new-doctype-1" and the renamed "TestDocType", both exist in history
			// now if we try to go back,
			// it doesn't allow us to go back to the one prior to "new-doctype-1"
			// Hence if this check is true, instead of changing location hash,
			// we just do a back to go to the doc previous to the "new-doctype-1"
			const re_route_val = this.get_sub_path(nts.re_route[sub_path]);
			if (re_route_val === this.current_sub_path) {
				window.history.back();
			} else {
				nts.set_route(re_route_val);
			}

			return true;
		}
	},

	set_title(sub_path) {
		if (nts.route_titles[sub_path]) {
			nts.utils.set_title(nts.route_titles[sub_path]);
		}
	},

	set_route() {
		// set the route (push state) with given arguments
		// example 1: nts.set_route('a', 'b', 'c');
		// example 2: nts.set_route(['a', 'b', 'c']);
		// example 3: nts.set_route('a/b/c');
		let route = Array.from(arguments);

		return new Promise((resolve) => {
			route = this.get_route_from_arguments(route);
			route = this.convert_from_standard_route(route);
			let sub_path = this.make_url(route);
			sub_path += nts.route_hash || "";
			nts.route_hash = null;
			if (nts.open_in_new_tab) {
				localStorage["route_options"] = JSON.stringify(nts.route_options);
				window.open(sub_path, "_blank");
				nts.open_in_new_tab = false;
			} else {
				this.push_state(sub_path);
			}
			setTimeout(() => {
				nts.after_ajax &&
					nts.after_ajax(() => {
						resolve();
					});
			}, 100);
		}).finally(() => (nts.route_flags = {}));
	},

	get_route_from_arguments(route) {
		if (route.length === 1 && $.isArray(route[0])) {
			// called as nts.set_route(['a', 'b', 'c']);
			route = route[0];
		}

		if (route.length === 1 && route[0] && route[0].includes("/")) {
			// called as nts.set_route('a/b/c')
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
					nts.route_options = route[2];
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
				nts.route_options = a;
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
		// 4. First workspace in list
		let private_home = `home-${nts.user.name.toLowerCase()}`;
		let default_workspace = nts.router.slug(nts.boot.user.default_workspace?.name || "");

		let workspace =
			nts.workspaces[default_workspace] ||
			nts.workspaces[private_home] ||
			nts.workspaces["home"] ||
			Object.values(nts.workspaces)[0];

		if (workspace) {
			return (
				"/app/" +
				(workspace.public ? "" : "private/") +
				nts.router.slug(workspace.title)
			);
		}

		return "/app";
	},

	push_state(url) {
		// change the URL and call the router
		if (window.location.pathname !== url) {
			// push/replace state so the browser looks fine
			const method = nts.route_flags.replace_route ? "replaceState" : "pushState";
			history[method](null, null, url);

			// now process the route
			this.route();
		}
	},

	get_sub_path_string(route) {
		// return clean sub_path from hash or url
		// supports both v1 and v2 routing
		if (!route) {
			route = window.location.pathname;
			if (route.includes("app#")) {
				// to support v1
				route = window.location.hash;
			}
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
		// set query parameters as nts.route_options
		let query_string = window.location.search;

		if (!nts.route_options) {
			nts.route_options = {};
		}

		if (localStorage.getItem("route_options")) {
			nts.route_options = JSON.parse(localStorage.getItem("route_options"));
			localStorage.removeItem("route_options");
		}

		let params = new URLSearchParams(query_string);
		for (const [key, value] of params) {
			nts.route_options[key] = value;
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
nts.get_route = () => nts.router.current_route;
nts.get_route_str = () => nts.router.current_route.join("/");
nts.set_route = function () {
	return nts.router.set_route.apply(nts.router, arguments);
};

nts.get_prev_route = function () {
	if (nts.route_history && nts.route_history.length > 1) {
		return nts.route_history[nts.route_history.length - 2];
	} else {
		return [];
	}
};

nts.set_re_route = function () {
	var tmp = nts.router.get_sub_path();
	nts.set_route.apply(null, arguments);
	nts.re_route[tmp] = nts.router.get_sub_path();
};

nts.has_route_options = function () {
	return Boolean(Object.keys(nts.route_options || {}).length);
};

nts.utils.make_event_emitter(nts.router);
