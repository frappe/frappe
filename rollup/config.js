const path = require('path');
const fs = require('fs');
const chalk = require('chalk');
const log = console.log; // eslint-disable-line

const multi_entry = require('rollup-plugin-multi-entry');
const commonjs = require('rollup-plugin-commonjs');
const node_resolve = require('rollup-plugin-node-resolve');
const postcss = require('rollup-plugin-postcss');
const buble = require('rollup-plugin-buble');
const uglify = require('rollup-plugin-uglify');
const vue = require('rollup-plugin-vue');
const frappe_html = require('./frappe-html-plugin');

const production = process.env.FRAPPE_ENV === 'production';

const {
	apps_list,
	assets_path,
	bench_path,
	get_public_path,
	get_app_path,
	get_build_json
} = require('./rollup.utils');

function get_rollup_options(output_file, input_files) {
	if (output_file.endsWith('.js')) {
		return get_rollup_options_for_js(output_file, input_files);
	} else if(output_file.endsWith('.css')) {
		return get_rollup_options_for_css(output_file, input_files);
	}
}

function get_rollup_options_for_js(output_file, input_files) {

	const node_resolve_paths = [].concat(
		// node_modules of apps directly importable
		apps_list.map(app => path.resolve(get_app_path(app), '../node_modules')).filter(fs.existsSync),
		// import js file of any app if you provide the full path
		apps_list.map(app => path.resolve(get_app_path(app), '..')).filter(fs.existsSync)
	);

	const plugins = [
		// enables array of inputs
		multi_entry(),
		// .html -> .js
		frappe_html(),
		// ignore css imports
		ignore_css(),
		// .vue -> .js
		vue.default(),
		// ES6 -> ES5
		buble({
			objectAssign: 'Object.assign',
			transforms: {
				dangerousForOf: true
			},
			exclude: [path.resolve(bench_path, '**/*.css'), path.resolve(bench_path, '**/*.less')]
		}),
		commonjs(),
		node_resolve({
			customResolveOptions: {
				paths: node_resolve_paths
			}
		}),
		production && uglify()
	];

	return {
		inputOptions: {
			input: input_files,
			plugins: plugins,
			context: 'window',
			external: ['jquery'],
			onwarn({ code, message, loc, frame }) {
				// skip warnings
				if (['EVAL', 'SOURCEMAP_BROKEN', 'NAMESPACE_CONFLICT'].includes(code)) return;

				if (loc) {
					log(`${loc.file} (${loc.line}:${loc.column}) ${message}`);
					if (frame) log(frame);
				} else {
					log(chalk.yellow.underline(code), ':', message);
				}
			}
		},
		outputOptions: {
			file: path.resolve(assets_path, output_file),
			format: 'iife',
			name: 'Rollup',
			globals: {
				'jquery': 'window.jQuery'
			},
			sourcemap: true
		}
	};
}

function get_rollup_options_for_css(output_file, input_files) {
	const output_path = path.resolve(assets_path, output_file);
	const minimize_css = output_path.startsWith('css/') && production;

	const plugins = [
		// enables array of inputs
		multi_entry(),
		// less -> css
		postcss({
			extract: output_path,
			use: [['less', {
				// import other less/css files starting from these folders
				paths: [
					path.resolve(get_public_path('frappe'), 'less')
				]
			}], 'sass'],
			include: [
				path.resolve(bench_path, '**/*.less'),
				path.resolve(bench_path, '**/*.scss'),
				path.resolve(bench_path, '**/*.css')
			],
			minimize: minimize_css
		})
	];

	return {
		inputOptions: {
			input: input_files,
			plugins: plugins,
			onwarn(warning) {
				// skip warnings
				if (['EMPTY_BUNDLE'].includes(warning.code)) return;

				// console.warn everything else
				log(chalk.yellow.underline(warning.code), ':', warning.message);
			}
		},
		outputOptions: {
			// this file is always empty, remove it later?
			file: path.resolve(assets_path, `css/rollup.manifest.css`),
			format: 'cjs'
		}
	};
}

function get_options_for(app) {
	const build_json = get_build_json(app);
	if (!build_json) return [];

	return Object.keys(build_json)
		.map(output_file => {
			if (output_file.startsWith('concat:')) return null;

			const input_files = build_json[output_file]
				.map(input_file => {
					let prefix = get_app_path(app);
					if (input_file.startsWith('node_modules/')) {
						prefix = path.resolve(get_app_path(app), '..');
					}
					return path.resolve(prefix, input_file);
				});
			return Object.assign(
				get_rollup_options(output_file, input_files), {
					output_file
				});
		})
		.filter(Boolean);
}

function ignore_css() {
	return {
		name: 'ignore-css',
		transform(code, id) {
			if (!['.css', '.scss', '.sass', '.less'].some(ext => id.endsWith(ext))) {
				return null;
			}

			return `
				// ignored ${id}
			`;
		}
	};
};

module.exports = {
	get_options_for
};
