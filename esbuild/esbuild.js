const path = require("path");
const fs = require("fs");
const glob = require("fast-glob");
const esbuild = require("esbuild");
const vue = require("esbuild-plugin-vue3");
const yargs = require("yargs");
const cliui = require("cliui")();
const chalk = require("chalk");
const html_plugin = require("./frappe-html");
const vue_style_plugin = require("./frappe-vue-style");
const rtlcss = require("rtlcss");
const postCssPlugin = require("@frappe/esbuild-plugin-postcss2").default;
const ignore_assets = require("./ignore-assets");
const sass_options = require("./sass_options");
const build_cleanup_plugin = require("./build-cleanup");

const {
	app_list,
	assets_path,
	apps_path,
	sites_path,
	get_public_path,
	log,
	log_warn,
	log_error,
	bench_path,
	get_redis_subscriber,
} = require("./utils");

const argv = yargs
	.usage("Usage: node esbuild [options]")
	.option("apps", {
		type: "string",
		description: "Run build for specific apps",
	})
	.option("skip_frappe", {
		type: "boolean",
		description: "Skip building frappe assets",
	})
	.option("files", {
		type: "string",
		description: "Run build for specified bundles",
	})
	.option("watch", {
		type: "boolean",
		description: "Run in watch mode and rebuild on file changes",
	})
	.option("live-reload", {
		type: "boolean",
		description: `Automatically reload Desk when assets are rebuilt.
			Can only be used with the --watch flag.`,
	})
	.option("production", {
		type: "boolean",
		description: "Run build in production mode",
	})
	.option("run-build-command", {
		type: "boolean",
		description: "Run build command for apps",
	})
	.option("save-metafiles", {
		type: "boolean",
		description:
			"Saves esbuild metafiles for built assets. Useful for analyzing bundle size. More info: https://esbuild.github.io/api/#metafile",
	})
	.option("using-cached", {
		type: "boolean",
		description:
			"Skips build and uses cached build artifacts to update assets.json (used by Bench)",
	})
	.example("node esbuild --apps frappe,erpnext", "Run build only for frappe and erpnext")
	.example(
		"node esbuild --files frappe/website.bundle.js,frappe/desk.bundle.js",
		"Run build only for specified bundles"
	)
	.version(false).argv;

const APPS = (!argv.apps ? app_list : argv.apps.split(",")).filter(
	(app) => !(argv.skip_frappe && app == "frappe")
);
const FILES_TO_BUILD = argv.files ? argv.files.split(",") : [];
const WATCH_MODE = Boolean(argv.watch);
const PRODUCTION = Boolean(argv.production);
const RUN_BUILD_COMMAND = !WATCH_MODE && Boolean(argv["run-build-command"]);

const TOTAL_BUILD_TIME = `${chalk.black.bgGreen(" DONE ")} Total Build Time`;
const NODE_PATHS = [].concat(
	// node_modules of apps directly importable
	app_list.map((app) => path.resolve(apps_path, app, "node_modules")).filter(fs.existsSync),
	// import js file of any app if you provide the full path
	app_list.map((app) => path.resolve(apps_path, app)).filter(fs.existsSync)
);
const USING_CACHED = Boolean(argv["using-cached"]);

execute().catch((e) => {
	console.error(e);
	process.exit(1);
});

if (WATCH_MODE) {
	// listen for open files in editor event
	open_in_editor();
}

async function execute() {
	console.time(TOTAL_BUILD_TIME);
	if (USING_CACHED) {
		await update_assets_json_from_built_assets(APPS);
		await update_assets_json_in_cache();
		console.timeEnd(TOTAL_BUILD_TIME);
		process.exit(0);
	}

	let results;
	try {
		results = await build_assets_for_apps(APPS, FILES_TO_BUILD);
	} catch (e) {
		log_error("There were some problems during build");
		log();
		log(chalk.dim(e.stack));
		if (process.env.CI || PRODUCTION) {
			process.kill(process.pid);
		}
		return;
	}

	if (!WATCH_MODE) {
		log_built_assets(results);
		console.timeEnd(TOTAL_BUILD_TIME);
		log();
	} else {
		log("Watching for changes...");
	}
	for (const result of results) {
		await write_assets_json(result.metafile);
	}
	RUN_BUILD_COMMAND && run_build_command_for_apps(APPS);
	if (!WATCH_MODE) {
		process.exit(0);
	}
}

async function update_assets_json_from_built_assets(apps) {
	const assets = await get_assets_json_path_and_obj(false);
	const assets_rtl = await get_assets_json_path_and_obj(true);

	for (const app of apps) {
		await update_assets_obj(app, assets.obj, assets_rtl.obj);
	}

	for (const { obj, path } of [assets, assets_rtl]) {
		const data = JSON.stringify(obj, null, 4);
		await fs.promises.writeFile(path, data);
	}
}

async function update_assets_obj(app, assets, assets_rtl) {
	const app_path = path.join(apps_path, app, app);
	const dist_path = path.join(app_path, "public", "dist");
	const files = await glob("**/*.bundle.*.{js,css}", { cwd: dist_path });
	const assets_dist = path.join("assets", app, "dist");
	const prefix = path.join("/", assets_dist);

	// eg: "js/marketplace.bundle.6SCSPSGQ.js"
	for (const file of files) {
		const source_path = path.join(dist_path, file);
		const dest_path = path.join(sites_path, assets_dist, file);

		// Copy asset file from app/public to sites/assets
		if (!fs.existsSync(dest_path)) {
			const dest_dir = path.dirname(dest_path);
			fs.mkdirSync(dest_dir, { recursive: true });
			fs.copyFileSync(source_path, dest_path);
		}

		// eg: [ "marketplace", "bundle", "6SCSPSGQ", "js" ]
		const parts = path.basename(file).split(".");

		// eg: "marketplace.bundle.js"
		const key = [...parts.slice(0, -2), parts.at(-1)].join(".");

		// eg: "js/marketplace.bundle.6SCSPSGQ.js"
		const value = path.join(prefix, file);
		if (file.includes("-rtl")) {
			assets_rtl[`rtl_${key}`] = value;
		} else {
			assets[key] = value;
		}
	}
}

function build_assets_for_apps(apps, files) {
	let { include_patterns, ignore_patterns } = files.length
		? get_files_to_build(files)
		: get_all_files_to_build(apps);

	return glob(include_patterns, { ignore: ignore_patterns }).then((files) => {
		let output_path = assets_path;

		let file_map = {};
		let style_file_map = {};
		let rtl_style_file_map = {};
		for (let file of files) {
			let relative_app_path = path.relative(apps_path, file);
			let app = relative_app_path.split(path.sep)[0];

			let extension = path.extname(file);
			let output_name = path.basename(file, extension);
			if ([".css", ".scss", ".less", ".sass", ".styl"].includes(extension)) {
				output_name = path.join("css", output_name);
			} else if ([".js", ".ts"].includes(extension)) {
				output_name = path.join("js", output_name);
			}
			output_name = path.join(app, "dist", output_name);

			if (
				Object.keys(file_map).includes(output_name) ||
				Object.keys(style_file_map).includes(output_name)
			) {
				log_warn(`Duplicate output file ${output_name} generated from ${file}`);
			}
			if ([".css", ".scss", ".less", ".sass", ".styl"].includes(extension)) {
				style_file_map[output_name] = file;
				rtl_style_file_map[output_name.replace("/css/", "/css-rtl/")] = file;
			} else {
				file_map[output_name] = file;
			}
		}
		let build = build_files({
			files: file_map,
			outdir: output_path,
		});
		let style_build = build_style_files({
			files: style_file_map,
			outdir: output_path,
		});
		let rtl_style_build = build_style_files({
			files: rtl_style_file_map,
			outdir: output_path,
			rtl_style: true,
		});
		return Promise.all([build, style_build, rtl_style_build]);
	});
}

function get_all_files_to_build(apps) {
	let include_patterns = [];
	let ignore_patterns = [];

	for (let app of apps) {
		let public_path = get_public_path(app);
		include_patterns.push(
			path.resolve(public_path, "**", "*.bundle.{js,ts,css,sass,scss,less,styl,jsx}")
		);
		ignore_patterns.push(
			path.resolve(public_path, "node_modules"),
			path.resolve(public_path, "dist")
		);
	}

	return {
		include_patterns,
		ignore_patterns,
	};
}

function get_files_to_build(files) {
	// files: ['frappe/website.bundle.js', 'erpnext/main.bundle.js']
	let include_patterns = [];
	let ignore_patterns = [];

	for (let file of files) {
		let [app, bundle] = file.split("/");
		let public_path = get_public_path(app);
		include_patterns.push(path.resolve(public_path, "**", bundle));
		ignore_patterns.push(
			path.resolve(public_path, "node_modules"),
			path.resolve(public_path, "dist")
		);
	}

	return {
		include_patterns,
		ignore_patterns,
	};
}

function build_files({ files, outdir }) {
	let build_plugins = [vue(), html_plugin, build_cleanup_plugin, vue_style_plugin];
	return esbuild.build(get_build_options(files, outdir, build_plugins));
}

function build_style_files({ files, outdir, rtl_style = false }) {
	let plugins = [];
	if (rtl_style) {
		plugins.push(rtlcss);
	}

	let build_plugins = [
		ignore_assets,
		build_cleanup_plugin,
		postCssPlugin({
			plugins: plugins,
			sassOptions: sass_options,
		}),
	];

	plugins.push(require("autoprefixer"));
	return esbuild.build(get_build_options(files, outdir, build_plugins));
}

function get_build_options(files, outdir, plugins) {
	return {
		entryPoints: files,
		entryNames: "[dir]/[name].[hash]",
		target: ["es2017"],
		outdir,
		sourcemap: true,
		bundle: true,
		metafile: true,
		minify: PRODUCTION,
		nodePaths: NODE_PATHS,
		define: {
			"process.env.NODE_ENV": JSON.stringify(PRODUCTION ? "production" : "development"),
			__VUE_OPTIONS_API__: JSON.stringify(true),
			__VUE_PROD_DEVTOOLS__: JSON.stringify(false),
		},
		plugins: plugins,
		watch: get_watch_config(),
	};
}

function get_watch_config() {
	if (WATCH_MODE) {
		return {
			async onRebuild(error, result) {
				if (error) {
					log_error("There was an error during rebuilding changes.");
					log();
					log(chalk.dim(error.stack));
					notify_redis({ error });
				} else {
					let { new_assets_json, prev_assets_json } = await write_assets_json(
						result.metafile
					);

					let changed_files;
					if (prev_assets_json) {
						changed_files = get_rebuilt_assets(prev_assets_json, new_assets_json);

						let timestamp = new Date().toLocaleTimeString();
						let message = `${timestamp}: Compiled ${changed_files.length} files...`;
						log(chalk.yellow(message));
						for (let filepath of changed_files) {
							let filename = path.basename(filepath);
							log("    " + filename);
						}
						log();
					}
					notify_redis({ success: true, changed_files });
				}
			},
		};
	}
	return null;
}

function log_built_assets(results) {
	let outputs = {};
	for (const result of results) {
		outputs = Object.assign(outputs, result.metafile.outputs);
	}
	let column_widths = [60, 20];
	cliui.div(
		{
			text: chalk.cyan.bold("File"),
			width: column_widths[0],
		},
		{
			text: chalk.cyan.bold("Size"),
			width: column_widths[1],
		}
	);
	cliui.div("");

	let output_by_dist_path = {};
	for (let outfile in outputs) {
		if (outfile.endsWith(".map")) continue;
		let data = outputs[outfile];
		outfile = path.resolve(outfile);
		outfile = path.relative(assets_path, outfile);
		let filename = path.basename(outfile);
		let dist_path = outfile.replace(filename, "");
		output_by_dist_path[dist_path] = output_by_dist_path[dist_path] || [];
		output_by_dist_path[dist_path].push({
			name: filename,
			size: (data.bytes / 1000).toFixed(2) + " Kb",
		});
	}

	for (let dist_path in output_by_dist_path) {
		let files = output_by_dist_path[dist_path];
		cliui.div({
			text: dist_path,
			width: column_widths[0],
		});

		for (let i in files) {
			let file = files[i];
			let branch = "";
			if (i < files.length - 1) {
				branch = "├─ ";
			} else {
				branch = "└─ ";
			}
			let color = file.name.endsWith(".js") ? "green" : "blue";
			cliui.div(
				{
					text: branch + chalk[color]("" + file.name),
					width: column_widths[0],
				},
				{
					text: file.size,
					width: column_widths[1],
				}
			);
		}
		cliui.div("");
	}
	log(cliui.toString());
}

// to store previous build's assets.json for comparison
let prev_assets_json;
let curr_assets_json;

async function write_assets_json(metafile) {
	let rtl = false;
	prev_assets_json = curr_assets_json;
	let out = {};
	for (let output in metafile.outputs) {
		let info = metafile.outputs[output];
		let asset_path = "/" + path.relative(sites_path, output);
		if (info.entryPoint) {
			let key = path.basename(info.entryPoint);
			if (key.endsWith(".css") && asset_path.includes("/css-rtl/")) {
				rtl = true;
				key = `rtl_${key}`;
			}
			out[key] = asset_path;
		}
	}

	let { obj: assets_json, path: assets_json_path } = await get_assets_json_path_and_obj(rtl);
	// update with new values
	let new_assets_json = Object.assign({}, assets_json, out);
	curr_assets_json = new_assets_json;

	await fs.promises.writeFile(assets_json_path, JSON.stringify(new_assets_json, null, 4));
	await update_assets_json_in_cache();
	if (argv["save-metafiles"]) {
		// use current timestamp in readable formate as a suffix for filename
		let current_timestamp = new Date().getTime();
		const metafile_name = `meta-${current_timestamp}.json`;
		await fs.promises.writeFile(`${metafile_name}`, JSON.stringify(metafile));
		log(`Saved metafile as ${metafile_name}`);
	}
	return {
		new_assets_json,
		prev_assets_json,
	};
}

async function update_assets_json_in_cache() {
	// Redis won't be present during docker image build
	if (process.env.FRAPPE_DOCKER_BUILD) {
		return;
	}

	// update assets_json cache in redis, so that it can be read directly by python
	let client = get_redis_subscriber("redis_cache");
	// handle error event to avoid printing stack traces
	try {
		await client.connect();
	} catch (e) {
		log_warn("Cannot connect to redis_cache to update assets_json");
	}
	client.del("assets_json", (err) => {
		client.unref();
	});
}

async function get_assets_json_path_and_obj(is_rtl) {
	const file_name = is_rtl ? "assets-rtl.json" : "assets.json";
	const assets_json_path = path.resolve(assets_path, file_name);
	let assets_json;
	try {
		assets_json = await fs.promises.readFile(assets_json_path, "utf-8");
	} catch (error) {
		assets_json = "{}";
	}
	assets_json = JSON.parse(assets_json);
	return { obj: assets_json, path: assets_json_path };
}

function run_build_command_for_apps(apps) {
	let cwd = process.cwd();
	let { execSync } = require("child_process");

	for (let app of apps) {
		if (app === "frappe") continue;

		let root_app_path = path.resolve(apps_path, app);
		let package_json = path.resolve(root_app_path, "package.json");
		let node_modules = path.resolve(root_app_path, "node_modules");

		if (!fs.existsSync(package_json)) {
			continue;
		}

		let { scripts } = require(package_json);
		if (!scripts?.build) {
			continue;
		}

		process.chdir(root_app_path);
		if (!fs.existsSync(node_modules)) {
			log(
				`\nInstalling dependencies for ${chalk.bold(app)} (because node_modules not found)`
			);
			execSync("yarn install --frozen-lockfile", { encoding: "utf8", stdio: "inherit" });
		}

		log("\nRunning build command for", chalk.bold(app));
		execSync("yarn build", { encoding: "utf8", stdio: "inherit" });
	}

	process.chdir(cwd);
}

async function notify_redis({ error, success, changed_files }) {
	// notify redis which in turns tells socketio to publish this to browser
	let subscriber = get_redis_subscriber("redis_queue");
	try {
		await subscriber.connect();
	} catch (e) {
		log_warn("Cannot connect to redis_queue for browser events");
	}

	let payload = null;
	if (error) {
		let formatted = await esbuild.formatMessages(error.errors, {
			kind: "error",
			terminalWidth: 100,
		});
		let stack = error.stack.replace(new RegExp(bench_path, "g"), "");
		payload = {
			error,
			formatted,
			stack,
		};
	}
	if (success) {
		payload = {
			success: true,
			changed_files,
			live_reload: argv["live-reload"],
		};
	}

	await subscriber.publish(
		"events",
		JSON.stringify({
			event: "build_event",
			message: payload,
		})
	);
}

async function open_in_editor() {
	let subscriber = get_redis_subscriber("redis_queue");
	try {
		await subscriber.connect();
	} catch (e) {
		log_warn("Cannot connect to redis_queue for open_in_editor events");
	}
	subscriber.subscribe("open_in_editor", (file) => {
		file = JSON.parse(file);
		let file_path = path.resolve(file.file);
		log("Opening file in editor:", file_path);
		let launch = require("launch-editor");
		launch(`${file_path}:${file.line}:${file.column}`);
	});
}

function get_rebuilt_assets(prev_assets, new_assets) {
	let added_files = [];
	let old_files = Object.values(prev_assets);
	let new_files = Object.values(new_assets);

	for (let filepath of new_files) {
		if (!old_files.includes(filepath)) {
			added_files.push(filepath);
		}
	}
	return added_files;
}
