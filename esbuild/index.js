let path = require("path");
let glob = require("fast-glob");
let esbuild = require("esbuild");
let html_plugin = require("./esbuild-plugin-html");
let vue = require("esbuild-vue");
let postCssPlugin = require("esbuild-plugin-postcss2").default;
let ignore_assets = require("./ignore-assets");
let sass_options = require("./sass_options");
let { app_list, get_public_path, run_serially } = require("./utils");

const TOTAL_BUILD_TIME = "Total Build Time";

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
		path.resolve(public_path, "build")
	];

	return glob(include_patterns, { ignore: ignore_patterns }).then(files => {
		// console.log(`\nBuilding assets for ${app}...`);
		return build_files({
			files,
			outdir: path.resolve(public_path, "build"),
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
			minify: true,
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
			]

			// watch: {
			// 	onRebuild(error, result) {
			// 		if (error) console.error("watch build failed:", error);
			// 		else {
			// 			console.log("watch build succeeded:");
			// 			log_build_meta(result.metafile);
			// 		}
			// 	}
			// }
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
		console.log(outfile, data.bytes / 1000 + " Kb");
	}
}
