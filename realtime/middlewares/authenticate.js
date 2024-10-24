const cookie = require("cookie");
const { get_conf } = require("../../node_utils");
const { get_url } = require("../utils");
const conf = get_conf();

function authenticate_with_frappe(socket, next) {
	let namespace = socket.nsp.name;
	namespace = namespace.slice(1, namespace.length); // remove leading `/`

	if (namespace != get_site_name(socket)) {
		next(new Error("Invalid namespace"));
	}

	if (get_hostname(socket.request.headers.host) != get_hostname(socket.request.headers.origin)) {
		next(new Error("Invalid origin"));
		return;
	}

	if (!socket.request.headers.cookie) {
		next(new Error("No cookie transmitted."));
		return;
	}

	let cookies = cookie.parse(socket.request.headers.cookie || "");
	let authorization_header = socket.request.headers.authorization;

	if (!cookies.sid && !authorization_header) {
		next(new Error("No authentication method used. Use cookie or authorization header."));
		return;
	}
	socket.sid = cookies.sid;
	socket.authorization_header = authorization_header;

	socket.frappe_request = (path, args = {}, opts = {}) => {
		let query_args = new URLSearchParams(args);
		if (query_args.toString()) {
			path = path + "?" + query_args.toString();
		}

		let headers = {};
		if (socket.authorization_header) {
			headers["Authorization"] = socket.authorization_header;
		} else if (socket.sid) {
			headers["Cookie"] = `sid=${socket.sid}`;
		}

		return fetch(get_url(socket, path), {
			...opts,
			headers,
		});
	};

	socket
		.frappe_request("/api/method/frappe.realtime.get_user_info")
		.then((res) => res.json())
		.then(({ message }) => {
			socket.user = message.user;
			socket.user_type = message.user_type;
			socket.installed_apps = message.installed_apps;
			next();
		})
		.catch((e) => {
			next(new Error(`Unauthorized: ${e}`));
		});
}

function get_site_name(socket) {
	if (socket.site_name) {
		return socket.site_name;
	} else if (socket.request.headers["x-frappe-site-name"]) {
		socket.site_name = get_hostname(socket.request.headers["x-frappe-site-name"]);
	} else if (
		conf.default_site &&
		["localhost", "127.0.0.1"].indexOf(get_hostname(socket.request.headers.host)) !== -1
	) {
		socket.site_name = conf.default_site;
	} else if (socket.request.headers.origin) {
		socket.site_name = get_hostname(socket.request.headers.origin);
	} else {
		socket.site_name = get_hostname(socket.request.headers.host);
	}
	return socket.site_name;
}

function get_hostname(url) {
	if (!url) return undefined;
	if (url.indexOf("://") > -1) {
		url = url.split("/")[2];
	}
	return url.match(/:/g) ? url.slice(0, url.indexOf(":")) : url;
}

module.exports = authenticate_with_frappe;
