const path = require('path');
const utils = require('./rollup/rollup.utils');
const { PurgeCSS } = require('purgecss');

let css_files = process.argv[2].split(',');
let css_file_paths = css_files.map(p => path.resolve(utils.assets_path, p));
let html_content = process.argv[3];
html_content = html_content.replace(/\\n/g, '\n');

new PurgeCSS()
	.purge({
		content: [
			{
				raw: html_content,
				extension: 'html'
			}
		],
		css: css_file_paths,
		defaultExtractor: content => content.match(/[\w-/:]+(?<!:)/g) || []
	})
	.then(result => {
		console.log(result[0].css); // eslint-disable-line
	});
