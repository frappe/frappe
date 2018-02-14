const path = require('path');
const fs = require('fs');

const {
	get_build_json_path,
	get_app_path,
	apps_list,
	assets_path
} = require('./rollup.utils');

// const less = require('rollup-plugin-less');
const multi_entry = require('rollup-plugin-multi-entry');
const commonjs = require('rollup-plugin-commonjs');
const node_resolve = require('rollup-plugin-node-resolve');
const buble = require('rollup-plugin-buble');
const frappe_html = require('./frappe-html-plugin');

const production = process.env.FRAPPE_ENV === 'production';

function get_build_json(app) {
	try {
		return require(get_build_json_path(app));
	} catch(e) {
		// build.json does not exist
		return null;
	}
}

function get_app_config(app) {
	const build_map = get_build_json(app);

	if (!build_map) return [];

	const config = Object.keys(build_map)
		.filter(output_file => output_file.endsWith('.js') && !output_file.endsWith('libs.min.js'))
		.map(output_file => {

			const input_files = build_map[output_file].map(
				input_path => path.resolve(get_app_path(app), input_path)
			);

			const plugins = [
				// enables array of inputs
				multi_entry(),
				// .html -> .js
				frappe_html(),
				// ES6 -> ES5
				buble({
					objectAssign: 'Object.assign',
					transforms: {
						dangerousForOf: true
					}
				}),
				commonjs(),
				node_resolve()
			];

			return {
				input: input_files,
				plugins: plugins,
				output: {
					file: path.resolve(assets_path, output_file),
					format: 'iife',
					name: 'Rollup',
					globals: {
						'sortablejs': 'window.Sortable',
						'clusterize.js': 'window.Clusterize'
					}
				},
				context: 'window',
				onwarn: (e) => {
					if (e.code === 'EVAL') return;
				},
				external: ['jquery']
			};
		});

	return config;
}

function build_libs() {
	const libs_path = 'js/libs.min.js';
	const input_files = get_build_json('frappe')[libs_path];

	const libs_content = input_files.map(file_name => {
		const full_path = path.resolve(get_app_path('frappe'), file_name);
		return `/* ${file_name} */\n` + fs.readFileSync(full_path);
	}).join('\n\n');

	const target_path = path.resolve(assets_path, libs_path);
	fs.writeFileSync(target_path, libs_content);
	console.log('Built libs.min.js');
}

function get_all_apps_config() {
	let configs = [];
	apps_list.forEach(app => {
		configs = configs.concat(get_app_config(app))
	});
	return configs;
}

build_libs();

module.exports = get_all_apps_config();