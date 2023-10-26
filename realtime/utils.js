const { get_conf } = require("../node_utils");
const conf = get_conf();

function get_url(socket, path) {
	if (!path) {
		path = "";
	}
	let url = socket.request.headers.origin;
	if (conf.developer_mode) {
		let [protocal, host, port] = url.split(':');
		if (port != conf.webserver_port) {
			port = conf.webserver_port;
		}
		url = `${protocal}:${host}:${port}`;
	}
	return url + path;
}

module.exports = {
	get_url,
};
