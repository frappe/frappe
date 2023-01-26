const path = require("path");
const fs = require("fs");
const chalk = require("chalk");

const frappe_path = path.resolve(__dirname, "..");
const bench_path = path.resolve(frappe_path, "..", "..");
const sites_path = path.resolve(bench_path, "sites");
const apps_path = path.resolve(bench_path, "apps");
const assets_path = path.resolve(sites_path, "assets");
const app_list = get_apps_list();

const app_paths = app_list.reduce((out, app) => {
	out[app] = path.resolve(apps_path, app, app);
	return out;
}, {});
const public_paths = app_list.reduce((out, app) => {
	out[app] = path.resolve(app_paths[app], "public");
	return out;
}, {});
const public_js_paths = app_list.reduce((out, app) => {
	out[app] = path.resolve(app_paths[app], "public/js");
	return out;
}, {});

const bundle_map = app_list.reduce((out, app) => {
	const public_js_path = public_js_paths[app];
	if (fs.existsSync(public_js_path)) {
		const all_files = fs.readdirSync(public_js_path);
		const js_files = all_files.filter((file) => file.endsWith(".js"));

		for (let js_file of js_files) {
			const filename = path.basename(js_file).split(".")[0];
			out[path.join(app, "js", filename)] = path.resolve(public_js_path, js_file);
		}
	}

	return out;
}, {});

const get_public_path = (app) => public_paths[app];

const get_build_json_path = (app) => path.resolve(get_public_path(app), "build.json");

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

function run_serially(tasks) {
	let result = Promise.resolve();
	tasks.forEach((task) => {
		if (task) {
			result = result.then ? result.then(task) : Promise.resolve();
		}
	});
	return result;
}

const get_app_path = (app) => app_paths[app];

function get_apps_list() {
	return fs
		.readFileSync(path.resolve(sites_path, "apps.txt"), {
			encoding: "utf-8",
		})
		.split("\n")
		.filter(Boolean);
}

function get_cli_arg(name) {
	let args = process.argv.slice(2);
	let arg = `--${name}`;
	let index = args.indexOf(arg);

	let value = null;
	if (index != -1) {
		value = true;
	}
	if (value && args[index + 1]) {
		value = args[index + 1];
	}
	return value;
}

function log_error(message, badge = "ERROR") {
	badge = chalk.white.bgRed(` ${badge} `);
	console.error(`${badge} ${message}`); // eslint-disable-line no-console
}

function log_warn(message, badge = "WARN") {
	badge = chalk.black.bgYellowBright(` ${badge} `);
	console.warn(`${badge} ${message}`); // eslint-disable-line no-console
}

function log(...args) {
	console.log(...args); // eslint-disable-line no-console
}

function get_redis_subscriber(kind) {
	// get redis subscriber that aborts after 10 connection attempts
	let retry_strategy;
	let { get_redis_subscriber: get_redis, get_conf } = require("../node_utils");

	if (process.env.CI == 1 || get_conf().developer_mode == 0) {
		retry_strategy = () => {};
	} else {
		retry_strategy = function (options) {
			// abort after 5 x 3 connection attempts ~= 3 seconds
			if (options.attempt > 4) {
				return undefined;
			}
			return options.attempt * 100;
		};
	}
	return get_redis(kind, { retry_strategy });
}

module.exports = {
	app_list,
	bench_path,
	assets_path,
	sites_path,
	apps_path,
	bundle_map,
	get_public_path,
	get_build_json_path,
	get_build_json,
	get_app_path,
	delete_file,
	run_serially,
	get_cli_arg,
	log,
	log_warn,
	log_error,
	get_redis_subscriber,
};
