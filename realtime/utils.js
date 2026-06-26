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
	// Hit the web process over loopback to bypass any proxy/CDN (e.g. Cloudflare);
	// the site travels in the X-Frappe-Site-Name header, so this still routes right.
	if (conf.webserver_port) {
		return `http://127.0.0.1:${conf.webserver_port}${path}`;
	}
	let url = socket.request.headers.origin;
	if (conf.developer_mode) {
		let [protocol, host, port] = url.split(":");
		port = conf.webserver_port;
		url = `${protocol}:${host}:${port}`;
	}
	return url + path;
}

module.exports = {
	get_hostname,
	get_url,
};
