const http = require("http");
const https = require("https");
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
	if (conf.server_ip) {
		return `http://${conf.server_ip}${path}`;
	}
	let url = socket.request.headers.origin;
	if (conf.developer_mode) {
		let [protocol, host, port] = url.split(":");
		port = conf.webserver_port;
		url = `${protocol}:${host}:${port}`;
	}
	return url + path;
}

function make_request(url, headers, host, opts = {}) {
	return new Promise((resolve, reject) => {
		const parsed = new URL(url);
		const lib = parsed.protocol === "https:" ? https : http;
		const options = {
			hostname: parsed.hostname,
			port: parsed.port || (parsed.protocol === "https:" ? 443 : 80),
			path: parsed.pathname + parsed.search,
			method: opts.method || "GET",
			headers: {
				...headers,
				Host: host,
			},
		};

		const req = lib.request(options, (res) => {
			let data = "";
			res.on("data", (chunk) => {
				data += chunk;
			});
			res.on("end", () => {
				resolve({
					json: () => Promise.resolve(JSON.parse(data)),
					text: () => Promise.resolve(data),
					status: res.statusCode,
					ok: res.statusCode >= 200 && res.statusCode < 300,
				});
			});
		});

		req.on("error", reject);

		if (opts.body) {
			req.write(opts.body);
		}
		req.end();
	});
}

module.exports = {
	get_hostname,
	get_url,
	make_request,
};
