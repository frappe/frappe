const cookie = require("cookie");
const request = require("superagent");
const { get_hostname, get_url } = require("../utils");

const { get_conf } = require("../../node_utils");
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

	let cookies = cookie.parse(socket.request.headers.cookie);

	if (!cookies.sid) {
		next(new Error("No sid transmitted."));
		return;
	}

	request
		.get(get_url(socket, "/api/method/frappe.realtime.get_user_info"))
		.type("form")
		.query({
			sid: cookies.sid,
		})
		.then((res) => {
			socket.user = res.body.message.user;
			socket.user_type = res.body.message.user_type;
			socket.sid = cookies.sid;
			socket.subscribed_documents = [];
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
		// from currentsite.txt since host is localhost
		socket.site_name = conf.default_site;
	} else if (socket.request.headers.origin) {
		socket.site_name = get_hostname(socket.request.headers.origin);
	} else {
		socket.site_name = get_hostname(socket.request.headers.host);
	}
	return socket.site_name;
}

module.exports = authenticate_with_frappe;
