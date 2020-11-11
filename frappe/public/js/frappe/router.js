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
frappe._cur_route = null;

$(window).on('hashchange', function() {
	if (window.location.hash) {
		let sub_path = frappe.get_sub_path(window.location.hash);
		window.location.hash = '';
		frappe.push_state(sub_path);
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
		frappe.push_state(frappe.get_sub_path(route));
		return false;
	};

	// target has "#" ,this is a v1 style route, so remake it.
	if (e.currentTarget.hash) {
		return override(e, e.currentTarget.hash);
	}

	// target has "/desk, this is a v2 style route.
	if (e.currentTarget.pathname &&
		(e.currentTarget.pathname.startsWith('/desk') || e.currentTarget.pathname.startsWith('desk'))) {
		return override(e, e.currentTarget.pathname);
	}
});

frappe.route = function() {

	// Application is not yet initiated
	if (!frappe.app) return;

	let sub_path = frappe.get_sub_path();

	if (frappe.re_route[sub_path] !== undefined) {
		// after saving a doc, for example,
		// "New DocType 1" and the renamed "TestDocType", both exist in history
		// now if we try to go back,
		// it doesn't allow us to go back to the one prior to "New DocType 1"
		// Hence if this check is true, instead of changing location hash,
		// we just do a back to go to the doc previous to the "New DocType 1"
		var re_route_val = frappe.get_sub_path(frappe.re_route[sub_path]);
		if (decodeURIComponent(re_route_val) === decodeURIComponent(sub_path)) {
			window.history.back();
			return;
		} else {
			frappe.set_route(re_route_val);
			return;
		}
	}

	frappe._cur_route = sub_path;

	let route = frappe.get_route();

	frappe.route_history.push(route);

	// set title
	frappe.route_titles[sub_path] = frappe._original_title || document.title;

	// hide open dialog
	frappe.ui.hide_open_dialog();

	if (route[0]) {
		const title_cased_route = frappe.utils.to_title_case(route[0]);
		if (title_cased_route === 'Workspace') {
			frappe.views.pageview.show('');
		}

		if (route[1] && frappe.views[title_cased_route + "Factory"]) {
			// has a view generator, generate!
			if(!frappe.view_factory[title_cased_route]) {
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
	} else {
		// Show home
		frappe.views.pageview.show('');
	}


	if (frappe.route_titles[sub_path]) {
		frappe.utils.set_title(frappe.route_titles[sub_path]);
	} else {
		setTimeout(function() {
			frappe.route_titles[frappe.get_route_str()] = frappe._original_title || document.title;
		}, 1000);
	}

	frappe.route.trigger('change');

};

frappe.get_route = function(route) {
	// for app
	route = frappe.get_sub_path_string(route).split('/');
	route = $.map(route, frappe._decode_str);
	var parts = null;
	var doc_name = route[route.length - 1];
	// if the last part contains ? then check if it is valid query string
	if (doc_name.indexOf("?") < doc_name.indexOf("=")) {
		parts = doc_name.split("?");
		route[route.length - 1] = parts[0];
	} else {
		parts = doc_name;
	}
	if (parts.length > 1) {
		var query_params = frappe.utils.get_query_params(parts[1]);
		frappe.route_options = $.extend(frappe.route_options || {}, query_params);
	}

	return route;
}

frappe.get_prev_route = function() {
	if (frappe.route_history && frappe.route_history.length > 1) {
		return frappe.route_history[frappe.route_history.length - 2];
	} else {
		return [];
	}
}

frappe._decode_str = function(r) {
	try {
		return decodeURIComponent(r);
	} catch (e) {
		if (e instanceof URIError) {
			return r;
		} else {
			throw e;
		}
	}
}

frappe.get_sub_path_string = function(route) {
	// return clean sub_path from hash or url
	// supports both v1 and v2 routing

	if (!route) {
		route = window.location.hash;
	}
	if (!route) {
		route = window.location.pathname;
	}

	if (route.substr(0, 1)=='/') route = route.substr(1); // for /desk/sub
	if (route.startsWith('desk')) route = route.substr(4); // for desk/sub
	if (route.substr(0, 1)=='/') route = route.substr(1);
	if (route.substr(0, 1)=='#') route = route.substr(1);
	if (route.substr(0, 1)=='!') route = route.substr(1);

	return route;
};

frappe.get_sub_path = frappe.get_route_str = function(route) {
	var sub_path = frappe.get_sub_path_string(route);
	route = $.map(sub_path.split('/'), frappe._decode_str).join('/');

	return route;
};

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
			frappe.push_state(route);
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

frappe.push_state = function (route) {
	let url = `/desk/${route}`;
	if (window.location.pathname !== url) {
		// cleanup any remenants of v1 routing
		window.location.hash = '';

		// push state so the browser looks fine
		history.pushState(null, null, url);

		// now process the route
		frappe.route();
	}
};

frappe.set_re_route = function() {
	var tmp = frappe.get_sub_path();
	frappe.set_route.apply(null, arguments);
	frappe.re_route[tmp] = frappe.get_sub_path();
};

frappe.has_route_options = function() {
	return Boolean(Object.keys(frappe.route_options || {}).length);
};

frappe.utils.make_event_emitter(frappe.route);
