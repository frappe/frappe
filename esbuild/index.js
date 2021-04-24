let path = require("path");
let fs = require("fs");
let glob = require("fast-glob");
let esbuild = require("esbuild");
let html_plugin = require("./esbuild-plugin-html");
let vue = require("esbuild-vue");
let postCssPlugin = require("esbuild-plugin-postcss2").default;
let ignore_assets = require("./ignore-assets");
let sass_options = require("./sass_options");
let {
	app_list,
	get_app_path,
	get_public_path,
	run_serially,
	bench_path,
	get_cli_arg
} = require("./utils");

const TOTAL_BUILD_TIME = "Total Build Time";
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
	console.time(TOTAL_BUILD_TIME);
	await run_build_for_apps(app_list);
	console.timeEnd(TOTAL_BUILD_TIME);
})();

function run_build_for_apps(apps) {
	return run_serially(apps.map(app => () => run_build_for_app(app)));
}

function run_build_for_app(app) {
	let public_path = get_public_path(app);
	let include_patterns = path.resolve(
		public_path,
		"**",
		"*.bundle.{js,ts,css,sass,scss,less,styl}"
	);
	let ignore_patterns = [
		path.resolve(public_path, "node_modules"),
		path.resolve(public_path, "dist")
	];

	return glob(include_patterns, { ignore: ignore_patterns }).then(files => {
		// console.log(`\nBuilding assets for ${app}...`);

		let dist_path = path.resolve(public_path, "dist");
		let file_map = {};
		for (let file of files) {
			let extension = path.extname(file);
			let output_name = path.basename(file, extension);
			if (
				[".css", ".scss", ".less", ".sass", ".styl"].includes(extension)
			) {
				output_name = path.join("css", output_name);
			} else if ([".js", ".ts"].includes(extension)) {
				output_name = path.join("js", output_name);
			}

			if (Object.keys(file_map).includes(output_name)) {
				console.warn(
					`Duplicate output file ${output_name} generated from ${file}`
				);
			}

			file_map[output_name] = file;
		}
		return build_files({
			files: file_map,
			outdir: dist_path,
			outbase: public_path
		});
	});
}

function build_files({ files, outdir, outbase }) {
	return esbuild
		.build({
			entryPoints: files,
			outdir,
			outbase,
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
								console.log("\n\nwatch build succeeded:");
								log_build_meta(result.metafile);
							}
						}
				  }
				: null
		})
		.then(result => {
			log_build_meta(result.metafile);
		})
		.catch(e => {
			console.error("Error during build");
		});
}

function log_build_meta(metafile) {
	for (let outfile in metafile.outputs) {
		if (outfile.endsWith(".map")) continue;
		let data = metafile.outputs[outfile];
		outfile = path.resolve(outfile);
		outfile = path.relative(path.resolve(bench_path, "apps"), outfile);
		console.log(outfile, data.bytes / 1000 + " Kb");
	}
}
