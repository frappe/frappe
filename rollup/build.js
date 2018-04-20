const fs = require('fs');
const path = require('path');
const chalk = require('chalk');
const rollup = require('rollup');
const log = console.log; // eslint-disable-line

const {
	get_build_json,
	get_app_path,
	apps_list,
	run_serially,
	assets_path,
	sites_path
} = require('./rollup.utils');

const {
	get_options_for
} = require('./config');

show_production_message();
ensure_js_css_dirs();
build_libs();
build_assets_for_all_apps();

function build_assets_for_all_apps() {
	run_serially(
		apps_list.map(app => () => build_assets(app))
	);
}

function build_assets(app) {
	const options = get_options_for(app);
	if (!options.length) return Promise.resolve();
	log(chalk.yellow(`\nBuilding ${app} assets...\n`));

	const promises = options.map(({ inputOptions, outputOptions, output_file}) => {
		return build(inputOptions, outputOptions)
			.then(() => {
				log(`${chalk.green('✔')} Built ${output_file}`);
			});
	});

	const start = Date.now();
	return Promise.all(promises)
		.then(() => {
			const time = Date.now() - start;
			log(chalk.green(`✨  Done in ${time / 1000}s`));
		});
}

function build(inputOptions, outputOptions) {
	return rollup.rollup(inputOptions)
		.then(bundle => bundle.write(outputOptions))
		.catch(err => log(chalk.red(err)));
}

function build_libs() {
	// only concatenates lib files, not processed through rollup

	const touch = require('touch');
	const libs_path = 'js/libs.min.js';
	const input_files = get_build_json('frappe')[libs_path];

	const libs_content = input_files.map(file_name => {
		const full_path = path.resolve(get_app_path('frappe'), file_name);
		return `/* ${file_name} */\n` + fs.readFileSync(full_path);
	}).join('\n\n');

	const target_path = path.resolve(assets_path, libs_path);
	fs.writeFileSync(target_path, libs_content);
	log(`${chalk.green('✔')} Built ${libs_path}`);
	touch(path.join(sites_path, '.build'), { force: true });
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
}

function show_production_message() {
	const production = process.env.FRAPPE_ENV === 'production';
	log(chalk.yellow(`${production ? 'Production' : 'Development'} mode`));
}
