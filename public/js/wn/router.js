// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// route urls to their virtual pages

// re-route map (for rename)
wn.re_route = {};
wn.route_titles = {};
wn.route_history = [];
wn.view_factory = {};
wn.view_factories = [];

wn.route = function() {
	if(wn.re_route[window.location.hash]) {
		// after saving a doc, for example,
		// "New DocType 1" and the renamed "TestDocType", both exist in history
		// now if we try to go back,
		// it doesn't allow us to go back to the one prior to "New DocType 1"
		// Hence if this check is true, instead of changing location hash, 
		// we just do a back to go to the doc previous to the "New DocType 1"
		var re_route_val = wn.get_route_str(wn.re_route[window.location.hash]);
		var cur_route_val = wn.get_route_str(wn._cur_route);
		if (decodeURIComponent(re_route_val) === decodeURIComponent(cur_route_val)) {
			window.history.back();
			return;
		} else {
			window.location.hash = wn.re_route[window.location.hash];
		}
	}

	wn._cur_route = window.location.hash;

	route = wn.get_route();
	wn.route_history.push(route);
	
	if(route[0] && wn.views[route[0] + "Factory"]) {
		// has a view generator, generate!
		if(!wn.view_factory[route[0]])
			wn.view_factory[route[0]] = new wn.views[route[0] + "Factory"]();
			
		wn.view_factory[route[0]].show();
	} else {
		// show page
		wn.views.pageview.show(route[0]);
	}

	if(wn.route_titles[window.location.hash]) {
		document.title = wn.route_titles[window.location.hash];
	}
}

wn.get_route = function(route) {	
	// for app
	return wn.get_route_str(route).split('/')
}

wn.get_route_str = function(route) {
	if(!route)
		route = window.location.hash;

	if(route.substr(0,1)=='#') route = route.substr(1);
	if(route.substr(0,1)=='!') route = route.substr(1);
	
	route = $.map(route.split('/'), 
		function(r) { return decodeURIComponent(r); }).join('/');

	return route;
}

wn.set_route = function() {
	route = $.map(arguments, function(a) { 
		if($.isPlainObject(a)) {
			wn.route_options = a;
			return null;
		} else {
			return a ? encodeURIComponent(a) : null; 
		}
	}).join('/');
	
	window.location.hash = route;
	
	// Set favicon (app.js)
	wn.app.set_favicon();
}

wn._cur_route = null;

$(window).on('hashchange', function() {
	// save the title
	wn.route_titles[wn._cur_route] = document.title;

	if(window.location.hash==wn._cur_route)
		return;
		
	// hide open dialog
	if(cur_dialog && cur_dialog.hide_on_page_refresh) 
		cur_dialog.hide();
		
	wn.route();
});