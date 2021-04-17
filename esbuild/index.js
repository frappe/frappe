let glob = require("fast-glob");
let esbuild = require("esbuild");
let html_plugin = require("./esbuild-plugin-html");
let vue = require("esbuild-vue");
let postCssPlugin = require("esbuild-plugin-postcss2").default;
let ignore_assets = require("./ignore-assets");
let { get_options_for_scss } = require("../rollup/rollup.utils");

console.time("Build time");

glob(["frappe/public/js/**/*.bundle.js"]).then(entry_files => {
	esbuild
		.build({
			entryPoints: entry_files,
			outdir: "frappe/public/build",
			outbase: "frappe/public",
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
					sassOptions: {
						...get_options_for_scss(),
						importer: function(url) {
							if (url.startsWith("~")) {
								// strip ~ so that it can resolve from node_modules
								url = url.slice(1);
							}
							if (url.endsWith(".css")) {
								// strip .css from end of path
								url = url.slice(0, -4);
							}
							// normal file, let it go
							return {
								file: url
							};
						}
					}
				})
			],

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

			if (result.warnings.length) {
				console.warn(result.warnings);
			}
		})
		.catch(e => console.error("error"))
		.finally(() => {
			console.timeEnd("Build time");
		});
});

function log_build_meta(metafile) {
	for (let outfile in metafile.outputs) {
		if (outfile.endsWith('.map')) continue;
		let data = metafile.outputs[outfile];
		console.log(outfile, data.bytes / 1000 + " Kb");
	}
}
