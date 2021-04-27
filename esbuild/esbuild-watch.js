let esbuild = require("esbuild");
let htmlPlugin = require("./frappe-html");
let vue = require("esbuild-vue");
let http = require("http");
let httpProxy = require("http-proxy");
let path = require("path");

const { get_public_path, apps_list } = require("../rollup/rollup.utils");

let proxy = httpProxy.createProxyServer({});

proxy.on("error", function(e) {
	console.error(e);
});

let server = http.createServer((req, res) => {
	if (req.url.includes("/public/")) {
		buildAsset(req.url).then(result => {
			if (!result) {
				proxy_request();
				return;
			}
			res.setHeader("Content-Header", "application/javascript");
			res.writeHead(200);
			res.end(result);
		});
	} else {
		proxy_request();
	}

	function proxy_request() {
		proxy.web(req, res, { target: "http://localhost:8000" });
	}
});

server.listen(8080);

server.on("listening", () => {
	console.log("dev server started at http:localhost:8080");
});

function buildAsset(url) {
	if (url.startsWith("/")) {
		url = url.substr(1);
	}
	let app;
	let parts = url.split(path.sep);
	if (apps_list.includes(parts[0])) {
		app = parts[0];
	}
	if (!app) return;

	let filepath = path.resolve(get_public_path(app), url.split("public/")[1]);
	console.log("building " + url);

	return esbuild
		.build({
			entryPoints: [filepath],
			write: false,
			bundle: true,
			plugins: [htmlPlugin, vue()],
			define: {
				"process.env.NODE_ENV": "'development'"
			}
		})
		.then(result => {
			return result.outputFiles[0].text;
		});
}
