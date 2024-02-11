const { get_conf } = require("../node_utils");
const conf = get_conf();
const request = require("superagent");

function get_url(socket, path) {
	if (!path) {
		path = "";
	}
	let url = socket.request.headers.origin;
	if (conf.developer_mode) {
		let [protocol, host, port] = url.split(":");
		if (port != conf.webserver_port) {
			port = conf.webserver_port;
		}
		url = `${protocol}:${host}:${port}`;
	}
	return url + path;
}

// Authenticates a partial request created using superagent
function frappe_request(path, socket) {
	const partial_req = request.get(get_url(socket, path));
	if (socket.sid) {
		return partial_req.query({ sid: socket.sid });
	} else if (socket.authorization_header) {
		return partial_req.set("Authorization", socket.authorization_header);
	}
}

module.exports = {
	get_url,
	frappe_request,
};
