function get_url_arg(name) {
	return get_query_params()[name] || "";
}

function get_query_params(query_string) {
	var query_params = {};
	if (!query_string) {
		query_string = location.search.substring(1);
	}

	var query_list = query_string.split("&");
	for (var i=0, l=query_list.length; i < l; i++ ){
		var pair = query_list[i].split("=");
		var key = pair[0];
		if (!key) {
			continue;
		}

		var value = pair[1];
		if (typeof value === "string") {
			value = value.replace(/\+/g, "%20");
			value = decodeURIComponent(value);
		}

		if (key in query_params) {
			if (typeof query_params[key] === undefined) {
				query_params[key] = [];
			} else if (typeof query_params[key] === "string") {
				query_params[key] = [query_params[key]];
			}
			query_params[key].push(value);
		} else {
			query_params[key] = value;
		}
	}
	return query_params;
}

function make_query_string(obj) {
	var query_params = [];
	$.each(obj, function(k, v) { query_params.push(encodeURIComponent(k) + "=" + encodeURIComponent(v)); });
	return "?" + query_params.join("&");
}
