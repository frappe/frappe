let { get_options_for_scss } = require("./utils");

module.exports = {
	...get_options_for_scss(),
	importer: function(url) {
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
			file: url
		};
	}
};
