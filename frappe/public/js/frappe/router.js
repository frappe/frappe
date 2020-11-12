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
frappe.route_options = null;
frappe.route_hooks = {};

$(window).on('hashchange', function() {
	// v1 style routing, route is in hash
	if (window.location.hash) {
		let sub_path = frappe.router.get_sub_path(window.location.hash);
		window.location.hash = '';
		frappe.router.push_state(sub_path);
	}
});

window.addEventListener('popstate', (event) => {
	// forward-back button, just re-render based on current route
	frappe.route();
});

// routing v2, capture all clicks so that the target is managed with push-state
$('body').on('click', 'a', function(e) {
	let override = (e, route) => {
		e.preventDefault();
		frappe.router.push_state(frappe.router.get_sub_path(route));
		return false;
	};

	// click handled, but not by href
	if (e.currentTarget.getAttribute('onclick')) return;

	const href = e.currentTarget.getAttribute('href');

	if (href==='#' || href==='') {
		return override(e, '/app');
	}

	// target has "#" ,this is a v1 style route, so remake it.
	if (e.currentTarget.hash) {
		return override(e, e.currentTarget.hash);
	}

	// target has "/app, this is a v2 style route.
	if (e.currentTarget.pathname &&
		(e.currentTarget.pathname.startsWith('/app') || e.currentTarget.pathname.startsWith('app'))) {
		return override(e, e.currentTarget.pathname);
	}
});

frappe.router = {
	current_route: null,
	doctype_names: {},
	route() {
		// resolve the route from the URL or hash
		// translate it so the objects are well defined
		// and render the page as required

		if (!frappe.app) return;

		let sub_path = frappe.router.get_sub_path();
		if (frappe.router.re_route(sub_path)) return;

		frappe.router.translate_doctype_name().then(() => {
			let route = frappe.router.current_route;

			frappe.router.set_history(route, sub_path);

			if (route[0]) {
				frappe.router.render_page(route);
			} else {
				// Show home
				frappe.views.pageview.show('');
			}

			frappe.router.set_title();
			frappe.route.trigger('change');
		});
	},

	translate_doctype_name() {
		return new Promise((resolve) => {
			let route = frappe.router.parse();
			let factory = route[0].toLowerCase();
			let done = () => {
				route[1] = frappe.router.doctype_names[route[1]];
				frappe.router.current_route = route;
				resolve();
			};

			if (['form', 'list', 'report', 'tree'].includes(factory)) {
				// translate the doctype to its original name
				if (frappe.router.doctype_names[route[1]]) {
					done();
				} else {
					frappe.xcall('frappe.desk.utils.get_doctype_name', {name: route[1]}).then((data) => {
						frappe.router.doctype_names[route[1]] = data;
						done();
					});
				}
			} else {
				done();
			}
		});
	},

	set_history(route, sub_path) {
		frappe.route_history.push(route);
		frappe.route_titles[sub_path] = frappe._original_title || document.title;
		frappe.ui.hide_open_dialog();
	},

	render_page(route) {
		// create the page generator (factory) object and call `show`
		// if there is no generator, render the `Page` object

		// first the router needs to know if its a "page", "doctype", "workspace"

		const title_cased_route = frappe.utils.to_title_case(route[0]);
		if (title_cased_route === 'Workspace') {
			frappe.views.pageview.show('');
			return;
		}

		if (route[1] && frappe.views[title_cased_route + "Factory"]) {
			// has a view generator, generate!
			if (!frappe.view_factory[title_cased_route]) {
				frappe.view_factory[title_cased_route] = new frappe.views[title_cased_route + "Factory"]();
			}

			frappe.view_factory[title_cased_route].show();
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
			// "New DocType 1" and the renamed "TestDocType", both exist in history
			// now if we try to go back,
			// it doesn't allow us to go back to the one prior to "New DocType 1"
			// Hence if this check is true, instead of changing location hash,
			// we just do a back to go to the doc previous to the "New DocType 1"
			var re_route_val = frappe.router.get_sub_path(frappe.re_route[sub_path]);
			if (decodeURIComponent(re_route_val) === decodeURIComponent(sub_path)) {
				window.history.back();
				return true;
			} else {
				frappe.set_route(re_route_val);
				return true;
			}
		}
	},

	set_title(sub_path) {
		if (frappe.route_titles[sub_path]) {
			frappe.utils.set_title(frappe.route_titles[sub_path]);
		} else {
			setTimeout(function() {
				frappe.route_titles[frappe.get_route_str()] = frappe._original_title || document.title;
			}, 1000);
		}
	},

	push_state(route) {
		// change the URL and call the router
		let url = route;
		if (!route.startsWith('/app/')) {
			url = `/app/${route}`;
		}
		if (window.location.pathname !== url) {
			// cleanup any remenants of v1 routing
			window.location.hash = '';

			// push state so the browser looks fine
			history.pushState(null, null, url);

			// now process the route
			frappe.router.route();
		}
	},

	parse(route) {
		route = frappe.router.get_sub_path_string(route).split('/');
		route = $.map(route, frappe.router.decode_component);

		frappe.router.set_route_options(route);

		return route;
	},

	get_sub_path_string(route) {
		// return clean sub_path from hash or url
		// supports both v1 and v2 routing
		if (!route) {
			route = window.location.hash || window.location.pathname;
		}

		return frappe.router.strip_prefix(route);
	},

	strip_prefix(route) {
		if (route.substr(0, 1)=='/') route = route.substr(1); // for /app/sub
		if (route.startsWith('app')) route = route.substr(4); // for desk/sub
		if (route.substr(0, 1)=='/') route = route.substr(1);
		if (route.substr(0, 1)=='#') route = route.substr(1);
		if (route.substr(0, 1)=='!') route = route.substr(1);
		return route;
	},

	get_sub_path(route) {
		var sub_path = frappe.router.get_sub_path_string(route);
		route = $.map(sub_path.split('/'), frappe.router.decode_component).join('/');

		return route;
	},

	set_route_options(route) {
		// set query parameters as frappe.route_options
		var last_part = route[route.length - 1];
		if (last_part.indexOf("?") < last_part.indexOf("=")) {
			// has ? followed by =
			let parts = last_part.split("?");

			// route should not contain string after ?
			route[route.length - 1] = parts[0];

			let query_params = frappe.utils.get_query_params(parts[1]);
			frappe.route_options = $.extend(frappe.route_options || {}, query_params);

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
		return name.toLowerCase().replace(/ /g, '-');
	}
};

frappe.route = frappe.router.route;
frappe.get_route = () => frappe.router.current_route;
frappe.get_route_str = () => frappe.router.current_route.join('/');

frappe.get_prev_route = function() {
	if (frappe.route_history && frappe.route_history.length > 1) {
		return frappe.route_history[frappe.route_history.length - 2];
	} else {
		return [];
	}
}


frappe.set_route = function() {
	return new Promise(resolve => {
		var params = arguments;
		if (params.length===1 && $.isArray(params[0])) {
			params = params[0];
		}
		var route = $.map(params, function(a) {
			if ($.isPlainObject(a)) {
				frappe.route_options = a;
				return null;
			} else {
				a = String(a);
				if (a && a.match(/[%'"]/)) {
					// if special chars, then encode
					a = encodeURIComponent(a);
				}
				return a;
			}
		}).join('/');

		// Perform a redirect when redirect is set in route_options
		if (frappe.route_options && frappe.route_options.redirect) {
			const url = new URL(window.location);
			url.hash = route;
			window.location.replace(url);
		} else {
			//
			// window.location.hash = route;

			// routing v2
			frappe.router.push_state(route);
		}

		// Set favicon (app.js)
		frappe.provide('frappe.app');
		frappe.app.set_favicon && frappe.app.set_favicon();

		setTimeout(() => {
			frappe.after_ajax && frappe.after_ajax(() => {
				resolve();
			});
		}, 100);
	});
};

frappe.set_re_route = function() {
	var tmp = frappe.router.get_sub_path();
	frappe.set_route.apply(null, arguments);
	frappe.re_route[tmp] = frappe.router.get_sub_path();
};

frappe.has_route_options = function() {
	return Boolean(Object.keys(frappe.route_options || {}).length);
};

frappe.utils.make_event_emitter(frappe.route);
