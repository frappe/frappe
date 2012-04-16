// route urls to their virtual pages

// re-route map (for rename)
wn.re_route = {
	
}
wn.route = function() {
	if(wn.re_route[window.location.hash]) {
		window.location.hash = wn.re_route[window.location.hash];
	}

	wn._cur_route = window.location.hash;

	route = wn.get_route();	
	
	switch (route[0]) {
		case "List":
			wn.views.doclistview.show(route[1]);
			break;
		case "Form":
			if(route.length>3) {
				route[2] = route.splice(2).join('/');
			}
			wn.views.formview.show(route[1], route[2]);
			break;
		case "Report":
			wn.views.reportview.show(route[1], route[2]);
			break;
		default:
			wn.views.pageview.show(route[0]);
	}
}

wn.get_route = function(route) {
	if(!route)
		route = window.location.hash;

	if(route.substr(0,1)=='#') route = route.substr(1);
	if(route.substr(0,1)=='!') route = route.substr(1);	

	return $.map(route.split('/'), function(r) { return decodeURIComponent(r); });	
}

wn.set_route = function() {
	route = $.map(arguments, function(a) { return encodeURIComponent(a) }).join('/');
	window.location.hash = route;
	
	// Set favicon (app.js)
	wn.app.set_favicon();
}

wn._cur_route = null;

$(window).bind('hashchange', function() {
	if(location.hash==wn._cur_route)
		return;	
	wn.route();
	
	// analytics code
	if(wn.boot.analytics_code) {
		try {
			eval(wn.boot.analytics_code);
		} catch (e) {
			console.log(e);
		}
	}
});
