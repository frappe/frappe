const path = require('path');
const fs = require('fs');
const touch = require('touch');

const {
	get_build_json_path,
	get_app_path,
	apps_list,
	assets_path,
	get_public_path,
	bench_path,
	sites_path
} = require('./rollup.utils');

const less = require('rollup-plugin-less');
const multi_entry = require('rollup-plugin-multi-entry');
const commonjs = require('rollup-plugin-commonjs');
const node_resolve = require('rollup-plugin-node-resolve');
const buble = require('rollup-plugin-buble');
const uglify = require('rollup-plugin-uglify');
const frappe_html = require('./frappe-html-plugin');

const production = process.env.FRAPPE_ENV === 'production';

ensure_js_css_dirs();
build_libs();

function get_app_config(app) {
	const build_map = get_build_json(app);
	if (!build_map) return [];

	const js_config = Object.keys(build_map)
		.filter(output_file =>
			output_file.endsWith('.js') &&
			// libs is built separately (to be deprecated)
			!output_file.endsWith('libs.min.js')
		)
		.map(output_file => {

			const input_files = build_map[output_file].map(
				// make paths absolute
				input_path => path.resolve(get_app_path(app), input_path)
			);

			return get_js_config(output_file, input_files);
		});

	const less_config = Object.keys(build_map)
		.filter(output_file =>
			output_file.endsWith('.css')
		)
		.map(output_file => {

			const input_files = build_map[output_file].map(
				input_path => path.resolve(get_app_path(app), input_path)
			);

			return get_css_config(output_file, input_files);
		});

	return [].concat(js_config, less_config);
}

function get_js_config(output_file, input_files) {

	const css_output_file = path.resolve(assets_path, 'css', path.basename(output_file).split('.js')[0] + '.css');

	const plugins = [
		// enables array of inputs
		multi_entry(),
		// .html -> .js
		frappe_html(),
		// less -> css
		less({
			output: css_output_file,
			option: {
				// so that other .less files can import variables.less from frappe directly
				paths: [path.resolve(get_public_path('frappe'), 'less'), path.resolve(get_app_path('frappe'), '..')],
				compress: production
			},
			// include: [path.resolve(bench_path, '**/*.less'), path.resolve(bench_path, '**/*.css')],
			exclude: []
		}),
		// ES6 -> ES5
		buble({
			objectAssign: 'Object.assign',
			transforms: {
				dangerousForOf: true
			},
			exclude: [path.resolve(bench_path, '**/*.css'), path.resolve(bench_path, '**/*.less')]
		}),
		commonjs(),
		node_resolve(),
		production && uglify()
	];

	return {
		input: input_files,
		plugins: plugins,
		output: {
			file: path.resolve(assets_path, output_file),
			format: 'iife',
			name: 'Rollup',
			// globals: {
			// 	'sortablejs': 'window.Sortable',
			// 	'clusterize.js': 'window.Clusterize'
			// },
			sourcemap: true
		},
		context: 'window',
		external: ['jquery']
	};
}

function get_css_config(output_file, input_files) {
	const output_path = path.resolve(assets_path, output_file);

	// clear css file to avoid appending problem
	delete_file(output_path);

	const plugins = [
		// enables array of inputs
		multi_entry(),
		// less -> css
		less({
			output: output_path,
			option: {
				// so that other .less files can import variables.less from frappe directly
				paths: [path.resolve(get_public_path('frappe'), 'less')],
				compress: production
			},
			include: [path.resolve(bench_path, '**/*.less'), path.resolve(bench_path, '**/*.css')]
		})
	];

	return {
		input: input_files,
		plugins: plugins,
		output: {
			// this file is always empty, remove it later?
			file: path.resolve(assets_path, `css/rollup.manifest.css`),
			format: 'cjs',
		}
	};
}

function ensure_js_css_dirs() {
	const paths = [
		path.resolve(assets_path, 'js'),
		path.resolve(assets_path, 'css')
	];
	paths.forEach(path => {
		if (!fs.existsSync(path)) {
			fs.mkdirSync(path);
		}
	});

	// clear files in css folder
	const css_path = path.resolve(assets_path, 'css');
	const files = fs.readdirSync(css_path);

	files.forEach(file => {
		delete_file(path.resolve(css_path, file));
	});
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
	console.log('✨  Built libs.min.js'); // eslint-disable-line
	touch(path.join(sites_path, '.build'), { force: true });
}

function get_all_apps_config() {
	let configs = [];
	apps_list.forEach(app => {
		configs = configs.concat(get_app_config(app));
	});
	return configs;
}

function get_build_json(app) {
	try {
		return require(get_build_json_path(app));
	} catch (e) {
		// build.json does not exist
		return null;
	}
}

function delete_file(path) {
	if (fs.existsSync(path)) {
		fs.unlinkSync(path);
	}
}

module.exports = get_all_apps_config();