const path = require('path');
const chalk = require('chalk');
const log = console.log; // eslint-disable-line

const multi_entry = require('rollup-plugin-multi-entry');
const commonjs = require('rollup-plugin-commonjs');
const node_resolve = require('rollup-plugin-node-resolve');
const less = require('rollup-plugin-less');
const buble = require('rollup-plugin-buble');
const uglify = require('rollup-plugin-uglify');
const frappe_html = require('./frappe-html-plugin');

const production = process.env.FRAPPE_ENV === 'production';

const {
	assets_path,
	bench_path,
	get_public_path,
	get_app_path,
	delete_file,
} = require('./rollup.utils');

function get_rollup_options(output_file, input_files) {
	if (output_file.endsWith('.js')) {
		return get_rollup_options_for_js(output_file, input_files);
	} else if(output_file.endsWith('.css')) {
		return get_rollup_options_for_css(output_file, input_files);
	}
}

function get_rollup_options_for_js(output_file, input_files) {
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
			include: [path.resolve(bench_path, '**/*.less'), path.resolve(bench_path, '**/*.css')],
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

module.exports = {
	get_rollup_options
};
