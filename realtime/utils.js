const request = require("superagent");
const { get_conf } = require("../node_utils");
const conf = get_conf();

function get_hostname(url) {
	if (!url) return undefined;
	if (url.indexOf("://") > -1) {
		url = url.split("/")[2];
	}
	return url.match(/:/g) ? url.slice(0, url.indexOf(":")) : url;
}

function get_url(socket, path) {
	if (!path) {
		path = "";
	}
	if (conf.webserver_host && conf.webserver_port) {
		let base = conf.webserver_host;
		if (base.indexOf("://") === -1) {
			base = `http://${base}`;
		}
		const url = new URL(base);
		if (!url.port) {
			url.port = conf.webserver_port;
		}
		return url.origin + path;
	}
	return socket.request.headers.origin + path;
}

// Authenticates a partial request created using superagent
function frappe_request(path, socket) {
	const partial_req = request
		.get(get_url(socket, path))
		.set("X-Frappe-Site-Name", socket.site_name);
	if (socket.authorization_header) {
		return partial_req.set("Authorization", socket.authorization_header);
	} else if (socket.sid) {
		return partial_req.set("Cookie", `sid=${socket.sid}`);
	}
}

module.exports = {
	get_hostname,
	get_url,
	frappe_request,
};
