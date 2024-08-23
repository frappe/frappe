let path = require("path");
let { apps_path, app_list } = require("./utils");

let app_paths = app_list.map((app) => path.resolve(apps_path, app));
let node_modules_path = app_paths.map((app_path) => path.resolve(app_path, "node_modules"));

module.exports = {
	includePaths: [...node_modules_path, ...app_paths],
	quietDeps: true,
	importer: function (url) {
		if (url.startsWith("~")) {
			// strip ~ so that it can resolve from node_modules
			url = url.slice(1);
		}
		if (url.endsWith(".css")) {
			// strip .css from end of path
			url = url.slice(0, -4);
		}
		// normal file, let it go
		return {
			file: url,
		};
	},
};
