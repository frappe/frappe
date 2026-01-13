const request = require("superagent");
const { get_conf } = require("../node_utils");
const conf = get_conf();

function get_url(socket, path) {
	if (!path) {
		path = "";
	}

	// DEVELOPER MODE: Use localhost to avoid reverse proxy TLS issues
	if (conf.developer_mode) {
		const webserver_port = conf.webserver_port || 8000;
		return `http://127.0.0.1:${webserver_port}${path}`;
	}

	// PRODUCTION MODE: Original logic unchanged
	return socket.request.headers.origin + path;
}

// Authenticates a partial request created using superagent
function frappe_request(path, socket) {
	const partial_req = request.get(get_url(socket, path));
	if (socket.authorization_header) {
		return partial_req.set("Authorization", socket.authorization_header);
	} else if (socket.sid) {
		return partial_req.query({ sid: socket.sid });
	}
}

module.exports = {
	get_url,
	frappe_request,
};
