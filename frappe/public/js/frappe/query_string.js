frappe.provide('frappe.utils');

function get_url_arg(name) {
	return get_query_params()[name] || "";
}

function get_query_string(url) {
	if(url.includes("?")) {
		return url.slice(url.indexOf("?")+1);
	}else {
		return "";
	}
}

function get_query_params(query_string) {
	var query_params = {};
	if (!query_string) {
		query_string = location.search.substring(1);
	}

	var query_list = query_string.split("&");
	for (var i=0, l=query_list.length; i < l; i++ ){
		var pair = query_list[i].split(/=(.+)/);
		var key = pair[0];
		if (!key) {
			continue;
		}

		var value = pair[1];
		if (typeof value === "string") {
			value = value.replace(/\+/g, "%20");
			try {
				value = decodeURIComponent(value);
			} catch(e) {
				// if value contains %, it fails
			}
		}

		if (key in query_params) {
			if (typeof query_params[key] === "undefined") {
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

function make_query_string(obj, encode=true) {
	let query_params = [];
	for (let key in obj) {
		let value = obj[key];
		if (value === undefined || value === '' || value === null) {
			continue;
		}
		if (typeof value === 'object') {
			value = JSON.stringify(value);
		}

		if (encode) {
			key = encodeURIComponent(key);
			value = encodeURIComponent(value);
		}

		query_params.push(`${key}=${value}`);
	}
	return '?' + query_params.join('&');
}

Object.assign(frappe.utils, {
	get_url_arg,
	get_query_string,
	get_query_params,
	make_query_string
});