let path = require("path");
let fs = require("fs");
let glob = require("fast-glob");
let esbuild = require("esbuild");
let vue = require("esbuild-vue");
let yargs = require("yargs");
let cliui = require("cliui")();
let chalk = require("chalk");
let html_plugin = require("./frappe-html");
let postCssPlugin = require("esbuild-plugin-postcss2").default;
let ignore_assets = require("./ignore-assets");
let sass_options = require("./sass_options");
let {
	app_list,
	assets_path,
	apps_path,
	sites_path,
	get_app_path,
	get_public_path,
	log,
	log_warn,
	log_error,
	bench_path
} = require("./utils");
let { get_redis_subscriber } = require("../node_utils");

let argv = yargs
	.usage("Usage: node esbuild [options]")
	.option("apps", {
		type: "string",
		description: "Run build for specific apps"
	})
	.option("skip_frappe", {
		type: "boolean",
		description: "Skip building frappe assets"
	})
	.option("watch", {
		type: "boolean",
		description: "Run in watch mode and rebuild on file changes"
	})
	.option("production", {
		type: "boolean",
		description: "Run build in production mode"
	})
	.example(
		"node esbuild --apps frappe,erpnext",
		"Run build only for frappe and erpnext"
	)
	.version(false).argv;

const APPS = (!argv.apps ? app_list : argv.apps.split(",")).filter(
	app => !(argv.skip_frappe && app == "frappe")
);
const WATCH_MODE = Boolean(argv.watch);
const PRODUCTION = Boolean(argv.production);
const TOTAL_BUILD_TIME = `${chalk.black.bgGreen(" DONE ")} Total Build Time`;
const NODE_PATHS = [].concat(
	// node_modules of apps directly importable
	app_list
		.map(app => path.resolve(get_app_path(app), "../node_modules"))
		.filter(fs.existsSync),
	// import js file of any app if you provide the full path
	app_list
		.map(app => path.resolve(get_app_path(app), ".."))
		.filter(fs.existsSync)
);

execute().catch(e => console.error(e));

async function execute() {
	console.time(TOTAL_BUILD_TIME);
	await clean_dist_folders(APPS);

	let result;
	try {
		result = await build_assets_for_apps(APPS);
	} catch (e) {
		log_error("There were some problems during build");
		log();
		log(chalk.dim(e.stack));
	}

	if (!WATCH_MODE) {
		log_built_assets(result.metafile);
		console.timeEnd(TOTAL_BUILD_TIME);
		log();
	} else {
		log("Watching for changes...");
	}
	return await write_meta_file(result.metafile);
}

function build_assets_for_apps(apps) {
	let { include_patterns, ignore_patterns } = get_files_to_build(apps);

	return glob(include_patterns, { ignore: ignore_patterns }).then(files => {
		let output_path = assets_path;

		let file_map = {};
		for (let file of files) {
			let relative_app_path = path.relative(apps_path, file);
			let app = relative_app_path.split(path.sep)[0];

			let extension = path.extname(file);
			let output_name = path.basename(file, extension);
			if (
				[".css", ".scss", ".less", ".sass", ".styl"].includes(extension)
			) {
				output_name = path.join("css", output_name);
			} else if ([".js", ".ts"].includes(extension)) {
				output_name = path.join("js", output_name);
			}
			output_name = path.join(app, "dist", output_name);

			if (Object.keys(file_map).includes(output_name)) {
				log_warn(
					`Duplicate output file ${output_name} generated from ${file}`
				);
			}

			file_map[output_name] = file;
		}

		return build_files({
			files: file_map,
			outdir: output_path
		});
	});
}

function get_files_to_build(apps) {
	let include_patterns = [];
	let ignore_patterns = [];

	for (let app of apps) {
		let public_path = get_public_path(app);
		include_patterns.push(
			path.resolve(
				public_path,
				"**",
				"*.bundle.{js,ts,css,sass,scss,less,styl}"
			)
		);
		ignore_patterns.push(
			path.resolve(public_path, "node_modules"),
			path.resolve(public_path, "dist")
		);
	}

	return {
		include_patterns,
		ignore_patterns
	};
}

function build_files({ files, outdir }) {
	return esbuild.build({
		entryPoints: files,
		entryNames: "[dir]/[name].[hash]",
		outdir,
		sourcemap: true,
		bundle: true,
		metafile: true,
		minify: PRODUCTION,
		nodePaths: NODE_PATHS,
		define: {
			"process.env.NODE_ENV": JSON.stringify(
				PRODUCTION ? "production" : "development"
			)
		},
		plugins: [
			html_plugin,
			ignore_assets,
			vue(),
			postCssPlugin({
				plugins: [require("autoprefixer")],
				sassOptions: sass_options
			})
		],

		watch: WATCH_MODE
			? {
					onRebuild(error, result) {
						if (error) {
							log_error(
								"There was an error during rebuilding changes."
							);
							log();
							log(chalk.dim(error.stack));
							notify_redis({ error });
						} else {
							console.log(
								`${new Date().toLocaleTimeString()}: Compiled changes...`
							);
							write_meta_file(result.metafile);
							notify_redis({ success: true });
						}
					}
			  }
			: null
	});
}

async function clean_dist_folders(apps) {
	for (let app of apps) {
		let public_path = get_public_path(app);
		await fs.promises.rmdir(path.resolve(public_path, "dist", "js"), {
			recursive: true
		});
		await fs.promises.rmdir(path.resolve(public_path, "dist", "css"), {
			recursive: true
		});
	}
}

function log_built_assets(metafile) {
	let column_widths = [60, 20];
	cliui.div(
		{
			text: chalk.cyan.bold("File"),
			width: column_widths[0]
		},
		{
			text: chalk.cyan.bold("Size"),
			width: column_widths[1]
		}
	);
	cliui.div("");

	let output_by_dist_path = {};
	for (let outfile in metafile.outputs) {
		if (outfile.endsWith(".map")) continue;
		let data = metafile.outputs[outfile];
		outfile = path.resolve(outfile);
		outfile = path.relative(assets_path, outfile);
		let filename = path.basename(outfile);
		let dist_path = outfile.replace(filename, "");
		output_by_dist_path[dist_path] = output_by_dist_path[dist_path] || [];
		output_by_dist_path[dist_path].push({
			name: filename,
			size: (data.bytes / 1000).toFixed(2) + " Kb"
		});
	}

	for (let dist_path in output_by_dist_path) {
		let files = output_by_dist_path[dist_path];
		cliui.div({
			text: dist_path,
			width: column_widths[0]
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
					width: column_widths[0]
				},
				{
					text: file.size,
					width: column_widths[1]
				}
			);
		}
		cliui.div("");
	}
	console.log(cliui.toString());
}

function write_meta_file(metafile) {
	let out = {};
	for (let output in metafile.outputs) {
		let info = metafile.outputs[output];
		let asset_path = "/" + path.relative(sites_path, output);
		if (info.entryPoint) {
			out[path.basename(info.entryPoint)] = asset_path;
		}
	}

	return fs.promises
		.writeFile(
			path.resolve(assets_path, "frappe", "dist", "assets.json"),
			JSON.stringify(out, null, 4)
		)
		.then(() => {
			let client = get_redis_subscriber("redis_cache");
			// update assets_json cache in redis, so that it can be read directly by python
			client.get("assets_json", (err, data) => {
				if (err) return;
				// get existing json
				let assets_json = JSON.parse(data || "{}");
				// overwrite new values
				assets_json = Object.assign({}, assets_json, out);

				client.set("assets_json", JSON.stringify(assets_json), err => {
					if (err) {
						log_warn("Could not update assets_json in redis_cache");
					}
					client.unref();
				});
			});
		});
}

async function notify_redis({ error, success }) {
	let subscriber = get_redis_subscriber("redis_socketio");
	// notify redis which in turns tells socketio to publish this to browser

	let payload = null;
	if (error) {
		let formatted = await esbuild.formatMessages(error.errors, {
			kind: "error",
			terminalWidth: 100
		});
		let stack = error.stack.replace(new RegExp(bench_path, "g"), "");
		payload = {
			error,
			formatted,
			stack
		};
	}
	if (success) {
		payload = {
			success: true
		};
	}

	subscriber.publish(
		"events",
		JSON.stringify({
			event: "build_event",
			message: payload
		})
	);
}

function open_in_editor() {
	let subscriber = get_redis_subscriber("redis_socketio");
	subscriber.on("message", (event, file) => {
		if (event === "open_in_editor") {
			file = JSON.parse(file);
			let file_path = path.resolve(file.file);
			console.log("Opening file in editor:", file_path);
			let launch = require("launch-editor");
			launch(`${file_path}:${file.line}:${file.column}`);
		}
	});
	subscriber.subscribe("open_in_editor");
}

if (WATCH_MODE) {
	open_in_editor();
}
