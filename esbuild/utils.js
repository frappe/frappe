const fg = require("fast-glob");
const path = require("path");
const fs = require("fs");
const chalk = require("chalk");
let bench_path;
if (process.env.FRAPPE_BENCH_ROOT) {
	bench_path = process.env.FRAPPE_BENCH_ROOT;
} else {
	const frappe_path = path.resolve(__dirname, "..");
	bench_path = path.resolve(frappe_path, "..", "..");
}

const apps_path = path.resolve(bench_path, "apps");
const sites_path = path.resolve(bench_path, "sites");
const assets_path = path.resolve(sites_path, "assets");
const app_list = get_apps_list();

const public_paths = app_list.reduce((out, app) => {
	out[app] = path.resolve(apps_path, app, app, "public");
	return out;
}, {});
const public_js_paths = app_list.reduce((out, app) => {
	out[app] = path.resolve(apps_path, app, app, "public/js");
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

function get_apps_list() {
	try {
		/**
		 * When building assets while installing the apps, apps.txt may
		 * not have the app being installed ∴ reading the apps directory
		 * is more fool-proof method to fetch the apps.
		 */
		return get_cloned_apps();
	} catch {
		// no-op
	}

	return fs
		.readFileSync(path.resolve(sites_path, "apps.txt"), {
			encoding: "utf-8",
		})
		.split("\n")
		.filter(Boolean);
}

function get_cloned_apps() {
	/**
	 * Returns frappe apps in the bench/apps folder
	 */
	const apps = [];
	for (const app of fs.readdirSync(apps_path)) {
		const app_path = path.resolve(apps_path, app);
		if (is_frappe_app(app, app_path)) apps.push(app);
	}

	return apps;
}

function is_frappe_app(app_name, app_path) {
	/**
	 * Same as the is_frappe_app check in frappe/bench
	 */

	const files_in_app = ["hooks.py", "modules.txt", "patches.txt"];

	for (const file of files_in_app) {
		// Heuristic check
		const file_path = path.resolve(app_path, app_name, file);
		if (fs.existsSync(file_path)) continue;

		// Absolute check (takes more time, hence the above one)
		const pattern = `${app_path}/**/${file}`;
		if (fg.sync(pattern).length == 0) return false;
	}

	return true;
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
	console.error(`${badge} ${message}`);
}

function log_warn(message, badge = "WARN") {
	badge = chalk.black.bgYellowBright(` ${badge} `);
	console.warn(`${badge} ${message}`);
}

function log(...args) {
	console.log(...args);
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
	delete_file,
	run_serially,
	get_cli_arg,
	log,
	log_warn,
	log_error,
	get_redis_subscriber,
	get_cloned_apps,
};
