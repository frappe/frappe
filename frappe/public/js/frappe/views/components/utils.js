function generate_route(item) {
	if(item.type==="doctype") {
		item.doctype = item.name;
	}
	let route = '';
	if(!item.route) {
		if(item.link) {
			route=strip(item.link, "#");
		} else if(item.type==="doctype") {
			if(frappe.model.is_single(item.doctype)) {
				route = 'Form/' + item.doctype;
			} else {
				if (item.filters) {
					frappe.route_options=item.filters;
				}
				route="List/" + item.doctype;
			}
		} else if(item.type==="report" && item.is_query_report) {
			route="query-report/" + item.name;
		} else if(item.type==="report") {
			route="List/" + item.doctype + "/Report/" + item.name;
		} else if(item.type==="page") {
			route=item.name;
		}

		route = '#' + route;
	} else {
		route = item.route;
	}

	if(item.route_options) {
		route += "?" + $.map(item.route_options, function(value, key) {
			return encodeURIComponent(key) + "=" + encodeURIComponent(value); }).join('&');
	}

	// if(item.type==="page" || item.type==="help" || item.type==="report" ||
	// (item.doctype && frappe.model.can_read(item.doctype))) {
	//     item.shown = true;
	// }
	return route;
}

export {
	generate_route
};
