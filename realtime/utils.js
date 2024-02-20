const request = require("superagent");

function get_url(socket, path) {
	if (!path) {
		path = "";
	}
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
}

module.exports = {
	get_url,
	frappe_request,
};
