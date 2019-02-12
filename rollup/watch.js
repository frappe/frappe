const path = require('path');
const chalk = require('chalk');
const rollup = require('rollup');
const log = console.log; // eslint-disable-line
const {
	apps_list
} = require('./rollup.utils');

const {
	get_options_for
} = require('./config');

const { get_redis_subscriber } = require('../node_utils');
const subscriber = get_redis_subscriber();

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
			case 'START': {
				log(chalk.yellow(`\nWatching...`));
				break;
			}

			case 'BUNDLE_START': {
				const output = event.output[0];
				if (output.endsWith('.js', '.vue')) {
					log('Rebuilding', path.basename(event.output[0]));
				}
				break;
			}

			case 'ERROR': {
				log_error(event.error);
				break;
			}

			case 'FATAL': {
				log_error(event.error);
				break;
			}

			default: break;
		}
	});
}

function get_watch_options(app) {
	const options = get_options_for(app);

	return options.map(({ inputOptions, outputOptions, output_file}) => {
		return Object.assign({}, inputOptions, {
			output: outputOptions,
			plugins: [log_css_change({output: output_file})].concat(inputOptions.plugins)
		});
	});
}

function log_css_change({output}) {
	return {
		name: 'log-css-change',
		ongenerate() {
			if (!output.endsWith('.css')) return null;
			log('Rebuilding', path.basename(output));
			return null;
		}
	};
}

function log_error(error) {
	log(chalk.yellow('Error in: ' +  error.id));
	log(chalk.red(error.toString()));

	if (error.frame) {
		log(chalk.red(error.frame));
	}

	// notify redis which in turns tells socketio to publish this to browser
	const payload = {
		event: 'build_error',
		message: `
Error in: ${error.id}
${error.toString()}

${error.frame ? error.frame : ''}
		`
	};

	subscriber.publish('events', JSON.stringify(payload));
}
