const { get_conf } = require("../node_utils");
const conf = get_conf();

function get_url(socket, path) {
	if (!path) path = "";

	// In dev, always talk to the local bench webserver over HTTP.
	// This avoids Node TLS trust issues with Caddy's internal CA.
	if (conf.developer_mode) {
		return `http://127.0.0.1:${conf.webserver_port}` + path;
	}

	// Non-dev fallback: use Origin first, then forwarded headers, then Host.
	const request_headers  = socket.request.headers;
	let base = request_headers.origin;

	if (!base) {
		const proto = request_headers["x-forwarded-proto"] || "http";
		const host = request_headers["x-forwarded-host"] || request_headers.host;
		if (host) base = `${proto}://${host}`;
	}

	return (base || "") + path;
}

module.exports = { get_url };
