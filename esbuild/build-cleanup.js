const path = require("path");
const fs = require("fs");
const glob = require("fast-glob");

// esbuild validates plugin objects strictly, so the plugin and the helper
// (used by derive-rtl.js for outputs that bypass esbuild) are separate exports.
const plugin = {
	name: "build_cleanup",
	setup(build) {
		build.onEnd((result) => {
			if (result.errors.length) return;
			clean_dist_files(Object.keys(result.metafile.outputs));
		});
	},
};

module.exports = { plugin, clean_dist_files };

function clean_dist_files(new_files) {
	new_files.forEach((file) => {
		if (file.endsWith(".map")) return;

		const pattern = file.split(".").slice(0, -2).join(".") + "*";
		glob.sync(pattern).forEach((file_to_delete) => {
			if (file_to_delete.startsWith(file)) return;

			fs.unlink(path.resolve(file_to_delete), (err) => {
				if (!err) return;

				console.error(`Error deleting ${file.split(path.sep).pop()}`);
			});
		});
	});
}
