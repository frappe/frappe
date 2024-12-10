<<<<<<< HEAD
const request = require("superagent");
=======
const { get_conf } = require("../node_utils");
const conf = get_conf();
>>>>>>> beab110ce9 (fix: clarify error message for child tables)

function get_url(socket, path) {
	if (!path) {
		path = "";
	}
<<<<<<< HEAD
	return socket.request.headers.origin + path;
}

// Authenticates a partial request created using superagent
function frappe_request(path, socket) {
	const partial_req = request.get(get_url(socket, path));
	if (socket.sid) {
		return partial_req.query({ sid: socket.sid });
	} else if (socket.authorization_header) {
		return partial_req.set("Authorization", socket.authorization_header);
	}
=======
	let url = socket.request.headers.origin;
	if (conf.developer_mode) {
		let [protocol, host, port] = url.split(":");
		port = conf.webserver_port;
		url = `${protocol}:${host}:${port}`;
	}
	return url + path;
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
}

module.exports = {
	get_url,
<<<<<<< HEAD
	frappe_request,
=======
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
};
