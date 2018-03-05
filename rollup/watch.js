const path = require('path');
const chalk = require('chalk');
const rollup = require('rollup');
const log = console.log; // eslint-disable-line
const {
	apps_list,
	get_app_path,
	get_build_json
} = require('./rollup.utils');

const {
	get_rollup_options
} = require('./config');

watch_assets();

function watch_assets() {
	let watchOptions = [];
	apps_list.map(app => {
		watchOptions.push(...get_watch_options(app));
	});
	log(chalk.green(`\nRollup Watcher Started`));
	let watcher = rollup.watch(watchOptions);

	watcher.on('event', event => {
		switch(event.code) {
			case 'START':
				log(chalk.yellow(`\nWatching...`));
				break;

			case 'BUNDLE_START':
				log('Rebuilding', path.basename(event.output[0]));
				break;

			default:
				break;
		}
	});
}

function get_watch_options(app) {
	const build_json = get_build_json(app);
	if (!build_json) return [];

	const watchOptions = Object.keys(build_json)
		.map(output_file => {
			const input_files = build_json[output_file]
				.map(input_file => path.resolve(get_app_path(app), input_file));
			const { inputOptions, outputOptions } = get_rollup_options(output_file, input_files);

			return Object.assign({}, inputOptions, {
				output: outputOptions
			});
		}).filter(Boolean);

	return watchOptions;
}
