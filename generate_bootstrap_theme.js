const sass = require('node-sass');
const fs = require('fs');
const path = require('path');
const { get_public_path } = require('./rollup/rollup.utils');

const node_modules_path = path.resolve(get_public_path('frappe'), 'node_modules');
const scss_path = path.resolve(get_public_path('frappe'), 'scss');
const website_theme_path = path.resolve(get_public_path('frappe'), 'website_theme');
const custom_theme_name = process.argv[2];

let scss_content = process.argv[3];
scss_content = scss_content.replace(/\\n/g, '\n');

sass.render({
	data: scss_content,
	includePaths: [
		node_modules_path,
		scss_path
	],
	importer: function(url) {
		if (url.startsWith('~')) {
			// strip ~ so that it can resolve from node_modules
			return {
				file: url.slice(1)
			};
		}
		// normal file, let it go
		return {
			file: url
		};
	}
}, function(err, result) {
	if (err) {
		console.error(err.formatted); // eslint-disable-line
		return;
	}

	fs.writeFile(path.resolve(website_theme_path, custom_theme_name), result.css, function(err) {
		if (!err) {
			console.log(custom_theme_name); // eslint-disable-line
		}
	});
});