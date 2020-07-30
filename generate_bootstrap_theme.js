const sass = require('node-sass');
const fs = require('fs');
const path = require('path');
const { apps_list, get_app_path, get_public_path, get_options_for_scss } = require('./rollup/rollup.utils');

const output_path = process.argv[2];

let scss_content = process.argv[3];
scss_content = scss_content.replace(/\\n/g, '\n');

sass.render({
	data: scss_content,
	outputStyle: 'compressed',
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
	},
	...get_options_for_scss()
}, function(err, result) {
	if (err) {
		console.error(err.formatted); // eslint-disable-line
		return;
	}

	fs.writeFile(output_path, result.css, function(err) {
		if (!err) {
			console.log(output_path); // eslint-disable-line
		}
	});
});