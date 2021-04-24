let path = require("path");
let fs = require("fs");
let glob = require("fast-glob");
let esbuild = require("esbuild");
let vue = require("esbuild-vue");
let cliui = require("cliui")();
let chalk = require("chalk");
let html_plugin = require("./esbuild-plugin-html");
let postCssPlugin = require("esbuild-plugin-postcss2").default;
let ignore_assets = require("./ignore-assets");
let sass_options = require("./sass_options");
let {
	app_list,
	assets_path,
	apps_path,
	get_app_path,
	get_public_path,
	get_cli_arg
} = require("./utils");

const TOTAL_BUILD_TIME = `${chalk.black.bgGreen(" DONE ")} Total Build Time`;
const WATCH_MODE = get_cli_arg("watch");
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

(async function() {
	let apps = app_list;
	let apps_arg = get_cli_arg("apps");
	if (apps_arg) {
		apps = apps_arg.split(",");
	}

	console.time(TOTAL_BUILD_TIME);
	build_assets_for_apps(apps)
		.then(() => {
			console.timeEnd(TOTAL_BUILD_TIME);
			console.log();
			if (WATCH_MODE) {
				console.log('Watching for changes...')
			}
		})
		.catch(() => {
			let error = chalk.white.bgRed(" ERROR ");
			console.error(`${error} There were some problems during build`);
		});
})();

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
				console.warn(
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
	return esbuild
		.build({
			entryPoints: files,
			outdir,
			sourcemap: true,
			bundle: true,
			metafile: true,
			// minify: true,
			nodePaths: NODE_PATHS,
			define: {
				"process.env.NODE_ENV": "'development'"
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
							if (error)
								console.error("watch build failed:", error);
							else {
								console.log(`${new Date().toLocaleTimeString()}: Compiled changes...`)
								// log_build_meta(result.metafile);
							}
						}
				  }
				: null
		})
		.then(result => {
			log_build_meta(result.metafile);
		});
}

function log_build_meta(metafile) {
	let column_widths = [40, 20];
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
