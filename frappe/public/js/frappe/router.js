// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// route urls to their virtual pages

// re-route map (for rename)
frappe.provide('frappe.views');
frappe.re_route = {"#login": ""};
frappe.route_titles = {};
frappe.route_flags = {};
frappe.route_history = [];
frappe.view_factory = {};
frappe.view_factories = [];
frappe.route_options = {};
frappe.route_hooks = {};

$(window).on('hashchange', function(e) {
	// v1 style routing, route is in hash
	if (window.location.hash && !frappe.router.is_app_route(e.currentTarget.pathname)) {
		let sub_path = frappe.router.get_sub_path(window.location.hash);
		frappe.router.push_url(sub_path);
		frappe.router.route();
		return false;
	}
});

window.addEventListener('popstate', (e) => {
	// forward-back button, just re-render based on current route
	frappe.router.route();
	e.preventDefault();
	return false;
});

// routing v2, capture all clicks so that the target is managed with push-state
$('body').on('click', 'a', function(e) {
	let override = (route, route_options) => {
		e.preventDefault();
		frappe.set_route(route, route_options);
		return false;
	};

	const href = e.currentTarget.getAttribute('href');

	// click handled, but not by href
	if (e.currentTarget.getAttribute('onclick') // has a handler
		|| (e.ctrlKey || e.metaKey) // open in a new tab
		|| href==='#') { // hash is home
		return;
	}

	if (href === '') {
		return override('/app');
	}

	if (href && href.startsWith('#')) {
		// target startswith "#", this is a v1 style route, so remake it.
		return override(e.currentTarget.hash);
	}

	if (frappe.router.is_app_route(e.currentTarget.pathname)) {
		// target has "/app, this is a v2 style route.
		const [route, route_options] = frappe.router.reverse_url(e.currentTarget.pathname)
		return override(route, route_options);
	}

});

frappe.router = {
	current_route: null,
	current_view_factory: null,

	routes: {},
	factory_views: ['form', 'list', 'report', 'tree', 'print', 'dashboard'],
	list_views: ['list', 'kanban', 'report', 'calendar', 'tree', 'gantt', 'dashboard', 'image', 'inbox'],

	is_app_route(path) {
		// desk paths must begin with /app or doctype route
		if (path.substr(0, 1) === '/') path = path.substr(1);
		path = path.split('/');
		if (path[0]) {
			return path[0]==='app';
		}
	},

	setup() {
		// setup the route names by forming slugs of the given doctypes
		for (let doctype of frappe.boot.user.can_read) {
			this.routes[this.slug(doctype)] = {doctype: doctype};
		}
		if (frappe.boot.doctype_layouts) {
			for (let doctype_layout of frappe.boot.doctype_layouts) {
				this.routes[this.slug(doctype_layout.name)] = {doctype: doctype_layout.document_type, doctype_layout: doctype_layout.name };
			}
		}
	},

	route() {
		// resolve the route from the URL or hash
		// translate it so the objects are well defined
		// and render the page as required

		if (!frappe.app) return;

		let sub_path = this.get_sub_path();
		if (this.re_route(sub_path)) return;

		this.current_sub_path = sub_path;
		const reversed = this.reverse_url(this.current_url())
		this.current_route = reversed[0];
		frappe.route_options = reversed[1];
		Object.freeze(frappe.route_options);
		frappe.route_flags = {};
		frappe.route_history.push(this.current_route);
		frappe.ui.hide_open_dialog();
		this.render();
		this.set_title(sub_path);
		this.trigger('change');

		return new Promise((resolve) => {
			setTimeout(() => {
				frappe.after_ajax && frappe.after_ajax(() => {
					resolve();
				});
			});
		})
	},

	reverse_url(url) {
		const [path, search] = url.split("?")
		const sub_path = this.get_sub_path(path).split('/')
		const route = this.convert_to_standard_route(sub_path);
		const route_options = this.decode_route_options(search)
		return [route, route_options]
	},

	resolve_url(route, route_options) {
		route_options = route_options || {}
		route = this.convert_to_standard_route(route)

		// See if we are routing between same doctype
		if(this.current_route && this.current_route[1] !== undefined && this.current_route[1] === route[1]) {
			// See if this url moves from list to form
			if(this.current_route[0] === "List" && route[0] === "Form") {
				// Keep list state
				route_options["__list"] = frappe.route_options
			} else if(this.current_route[0] === "Form" && route[0] === "List") {
				// Append list state
				route_options = Object.keys(route_options).length === 0 ? frappe.route_options.__list || {} : route_options
			}
		}

		const path = this.convert_from_standard_route(route).map(encodeURIComponent).join('/')
		const search = this.encode_route_options(route_options)
		const url = search ? `${path}?${search}` : path;
		const private_home = frappe.workspaces[`home-${frappe.user.name.toLowerCase()}`];
		const default_page = private_home ? 'private/home' : frappe.workspaces['home'] ? 'home' : Object.keys(frappe.workspaces)[0];
		return '/app/' + (url || default_page);
	},

	encode_route_options(route_options) {
		return Object.entries(route_options || {}).map(
			([k,v]) => `${encodeURIComponent(k)}=${encodeURIComponent(JSON.stringify(v))}`
		).join('&')
	},

	decode_route_options(search) {
		const params = new URLSearchParams(search || "")
		return Array.from(params.entries()).reduce((acc, [k, v]) => {
			acc[k] = JSON.parse(v)
			return acc
		}, {})
	},

	get_doctype_route(route) {
		let doctype_route = this.routes[route[0]];
		// doctype route
		if (route[1]) {
			if (route[2] && route[1]==='view') {
				route = this.get_standard_route_for_list(route, doctype_route);
			} else {
				let docname = route[1];
				if (route.length > 2) {
					docname = route.slice(1).join('/');
				}
				route = ['Form', doctype_route.doctype, docname];
			}
		} else if (frappe.model.is_single(doctype_route.doctype)) {
			route = ['Form', doctype_route.doctype, doctype_route.doctype];
		} else {
			route = ['List', doctype_route.doctype, 'List'];
		}

		if (doctype_route.doctype_layout) {
			// set the layout
			this.doctype_layout = doctype_route.doctype_layout;
		}

		return route;
	},

	is_reserved_path(path) {
		route = this.convert_to_standard_route(this.get_sub_path(path).split('/'))
		return !!this.routes[route[0]];
	},

	get_standard_route_for_list(route, doctype_route) {
		let standard_route;
		if (route[2].toLowerCase()==='tree') {
			standard_route = ['Tree', doctype_route.doctype];
		} else {
			standard_route = ['List', doctype_route.doctype, frappe.utils.to_title_case(route[2])];
			// calendar / kanban / dashboard / folder
			if (route[3]) standard_route.push(...route.slice(3, route.length));
		}
		return standard_route;
	},

	render() {
		if (this.current_route[0]) {
			this.render_page();
		} else {
			// Show home
			frappe.views.pageview.show('');
		}
	},

	render_page() {
		// create the page generator (factory) object and call `show`
		// if there is no generator, render the `Page` object

		const route = this.current_route;
		const factory = frappe.utils.to_title_case(route[0]);

		if (this.current_view_factory !== null) {
			this.current_view_factory.teardown()
		}

		if (route[1] && frappe.views[factory + "Factory"]) {
			route[0] = factory;
			// has a view generator, generate!
			if (!frappe.view_factory[factory]) {
				frappe.view_factory[factory] = new frappe.views[factory + "Factory"]();
			}

			this.current_view_factory = frappe.view_factory[factory]
			this.current_view_factory.show();
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

	async push_route() {
		const [route, route_options] = this.parse_route_arguments(Array.from(arguments))
		if (this.push_url(this.resolve_url(route, {...route_options}))) {
			await this.route();
		}
	},

	async replace_route() {
		const [route, route_options] = this.parse_route_arguments(Array.from(arguments))
		if (this.replace_url(this.resolve_url(route, {...route_options}))) {
			await this.route();
		}
	},


	parse_route_arguments(route) {
		// example 1: ['a', 'b', 'c', route_options?];
		// example 2: [['a', 'b', 'c'], route_options?];
		// example 3: []'a/b/c', route_options?];
		// example 4: [['a', b, 'c, route_options]]

		let route_options = {}

		if (route.length > 1 && typeof route[route.length - 1] !== 'string') {
			route_options = route.pop()
		}

		if (route.length === 1) {
			if ($.isArray(route[0])) {
				// called as frappe.set_route(['a', 'b', 'c']);
				route = route[0];
			} else if (route[0].includes('/')) {
				// called as frappe.set_route('a/b/c')
				route = route[0].split('/').map(decodeURIComponent)
			}
		}

		if (route.length > 1 && typeof route[route.length - 1] !== 'string') {
			route_options = route.pop()
		}

		if (!frappe.utils.is_json_serializable(route_options)) {
			throw new Error("Invalid route options, must be a compatible json object")
		}

		while (route.length > 0 && ['', 'desk', 'app'].includes(route[0])) {
			route.shift();
		}

		return [route, route_options]
	},

	convert_to_standard_route(route) {
		// /app/settings = ["Workspaces", "Settings"]
		// /app/private/settings = ["Workspaces", "private", "Settings"]
		// /app/user = ["List", "User"]
		// /app/user/view/report = ["List", "User", "Report"]
		// /app/user/view/tree = ["Tree", "User"]
		// /app/user/user-001 = ["Form", "User", "user-001"]
		// /app/user/user-001 = ["Form", "User", "user-001"]
		// /app/event/view/calendar/default = ["List", "Event", "Calendar", "Default"]

		let private_workspace = route[1] && `${route[1]}-${frappe.user.name.toLowerCase()}`;

		if (frappe.workspaces[route[0]]) {
			// public workspace
			route = ['Workspaces', frappe.workspaces[route[0]].title];
		} else if (route[0] == 'private' && frappe.workspaces[private_workspace]) {
			// private workspace
			route = ['Workspaces', 'private', frappe.workspaces[private_workspace].title];
		} else if (this.routes[route[0]]) {
			// route
			route = this.get_doctype_route(route);
		}

		return route;
	},

	convert_from_standard_route(route) {
		// ["List", "Sales Order"] => /sales-order
		// ["Form", "Sales Order", "SO-0001"] => /sales-order/SO-0001
		// ["Tree", "Account"] = /account/view/tree

		const view = route[0] ? route[0].toLowerCase() : '';
		let new_route = route;

		if (view === 'list') {
			if (route[2] && route[2] !== 'list') {
				new_route = [this.slug(route[1]), 'view', route[2].toLowerCase()];

				// calendar / inbox / file folder
				if (route[3]) new_route.push(...route.slice(3, route.length));
			}
		} else if (view === 'form') {
			new_route = [this.slug(route[1])];
			if (route[2]) {
				// if not single
				new_route.push(route[2]);
			}
		} else if (view === 'tree') {
			new_route = [this.slug(route[1]), 'view', 'tree'];
		}
		return new_route
	},

	push_url(url) {
		if (this.current_url() === url) return false;
		history.pushState(null, null, url);
		return true
	},

	replace_url(url) {
		if (this.current_url() === url) return false;
		history.replaceState(null, null, url);
		return true
	},

	current_path: function() {
		return window.location.pathname
	},

	current_url: function() {
		return window.location.pathname + window.location.search
	},

	get_sub_path(path) {
		if (!path) {
			path = this.current_path()
		}

		if (path.substr(0, 1)=='/') path = path.substr(1); // for /app/sub
		if (path.startsWith('app/')) path = path.substr(4); // for desk/sub
		if (path == 'app') path = path.substr(4); // for /app
		if (path.substr(0, 1)=='/') path = path.substr(1);
		if (path.substr(0, 1)=='#') path = path.substr(1);
		if (path.substr(0, 1)=='!') path = path.substr(1);
		return path.split('/').map(decodeURIComponent).join('/');
	},

	slug(name) {
		return name.toLowerCase().replace(/ /g, '-');
	}
};

frappe.router.set_route = frappe.router.push_route.bind(frappe.router);

// global functions for backward compatibility
frappe.get_route = () => frappe.router.current_route;
frappe.get_route_str = () => frappe.router.current_route.join('/');
frappe.set_route = frappe.router.push_route.bind(frappe.router);

frappe.get_prev_route = function() {
	if (frappe.route_history && frappe.route_history.length > 1) {
		return frappe.route_history[frappe.route_history.length - 2];
	} else {
		return [];
	}
};

frappe.set_re_route = function() {
	var tmp = frappe.router.get_sub_path();
	frappe.set_route.apply(null, arguments);
	frappe.re_route[tmp] = frappe.router.get_sub_path();
};

frappe.has_route_options = function() {
	return Object.keys(frappe.route_options).length > 0;
};

frappe.get_route_options = function() {
	return {...frappe.route_options};
}

frappe.utils.make_event_emitter(frappe.router);
