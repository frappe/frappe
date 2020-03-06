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

frappe.route = function() {

	// Application is not yet initiated
	if (!frappe.app) return;

	if(frappe.re_route[window.location.hash] !== undefined) {
		// after saving a doc, for example,
		// "New DocType 1" and the renamed "TestDocType", both exist in history
		// now if we try to go back,
		// it doesn't allow us to go back to the one prior to "New DocType 1"
		// Hence if this check is true, instead of changing location hash,
		// we just do a back to go to the doc previous to the "New DocType 1"
		var re_route_val = frappe.get_route_str(frappe.re_route[window.location.hash]);
		var cur_route_val = frappe.get_route_str(frappe._cur_route);
		if (decodeURIComponent(re_route_val) === decodeURIComponent(cur_route_val)) {
			window.history.back();
			return;
		} else {
			window.location.hash = frappe.re_route[window.location.hash];
		}
	}

	frappe._cur_route = window.location.hash;

	var route = frappe.get_route();
	if (route === false) {
		return;
	}

	frappe.route_history.push(route);

	if(route[0]) {
		const title_cased_route = frappe.utils.to_title_case(route[0]);

		if (title_cased_route === 'Desktop') {
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
		// Show desk
		frappe.views.pageview.show('');
	}


	if(frappe.route_titles[window.location.hash]) {
		frappe.utils.set_title(frappe.route_titles[window.location.hash]);
	} else {
		setTimeout(function() {
			frappe.route_titles[frappe.get_route_str()] = frappe._original_title || document.title;
		}, 1000);
	}

	if(window.mixpanel) {
		window.mixpanel.track(route.slice(0, 2).join(' '));
	}
}

frappe.get_route = function(route) {
	// for app
	route = frappe.get_raw_route_str(route).split('/');
	route = $.map(route, frappe._decode_str);
	var parts = null;
	var doc_name = route[route.length - 1];
	// if the last part contains ? then check if it is valid query string
	if(doc_name.indexOf("?") < doc_name.indexOf("=")){
		parts = doc_name.split("?");
		route[route.length - 1] = parts[0];
	} else {
		parts = doc_name;
	}
	if (parts.length > 1) {
		var query_params = frappe.utils.get_query_params(parts[1]);
		frappe.route_options = $.extend(frappe.route_options || {}, query_params);
	}

	// backward compatibility
	if (route && route[0]==='Module') {
		frappe.set_route('modules', route[1]);
		return false;
	}

	return route;
}

frappe.get_prev_route = function() {
	if(frappe.route_history && frappe.route_history.length > 1) {
		return frappe.route_history[frappe.route_history.length - 2];
	} else {
		return [];
	}
}

frappe._decode_str = function(r) {
	try {
		return decodeURIComponent(r);
	} catch(e) {
		if (e instanceof URIError) {
			return r;
		} else {
			throw e;
		}
	}
}

frappe.get_raw_route_str = function(route) {
	if(!route)
		route = window.location.hash;

	if(route.substr(0,1)=='#') route = route.substr(1);
	if(route.substr(0,1)=='!') route = route.substr(1);

	return route;
}

frappe.get_route_str = function(route) {
	var rawRoute = frappe.get_raw_route_str(route);
	route = $.map(rawRoute.split('/'), frappe._decode_str).join('/');

	return route;
}

frappe.set_route = function() {
	return new Promise(resolve => {
		var params = arguments;
		if(params.length===1 && $.isArray(params[0])) {
			params = params[0];
		}
		var route = $.map(params, function(a) {
			if($.isPlainObject(a)) {
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

		window.location.hash = route;

		// Set favicon (app.js)
		frappe.provide('frappe.app');
		frappe.app.set_favicon && frappe.app.set_favicon();
		setTimeout(() => {
			frappe.after_ajax && frappe.after_ajax(() => {
				resolve();
			});
		}, 100);
	});
}

frappe.set_re_route = function() {
	var tmp = window.location.hash;
	frappe.set_route.apply(null, arguments);
	frappe.re_route[tmp] = window.location.hash;
};

frappe.has_route_options = function() {
	return Boolean(Object.keys(frappe.route_options || {}).length);
}

frappe._cur_route = null;

$(window).on('hashchange', function() {
	// save the title
	frappe.route_titles[frappe._cur_route] = frappe._original_title || document.title;

	if(window.location.hash==frappe._cur_route)
		return;

	// hide open dialog
	if(window.cur_dialog) {
		if (!cur_dialog.minimizable) {
			cur_dialog.hide();
		} else if (!cur_dialog.is_minimized) {
			cur_dialog.toggle_minimize();
		}
	}

	frappe.route();

	frappe.route.trigger('change');
});

frappe.utils.make_event_emitter(frappe.route);
