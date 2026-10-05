const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { sites_path } = require("./utils");

module.exports = {
	name: "frappe-vue-style",
	setup(build) {
		build.initialOptions.write = false;
		build.onEnd(async (result) => {
			let files = get_files(result.metafile.outputs);
			let keys = Object.keys(files);
			// process everything before writing anything: the rename below also
			// touches the sibling .map, which may sit earlier in outputFiles
			for (let out of [...result.outputFiles]) {
				let asset_path = "/" + path.relative(sites_path, out.path);
				if (out.path.endsWith(".js") && keys.includes(asset_path)) {
					let name = out.path.split(".bundle.")[0];
					name = path.basename(name);

					let index = result.outputFiles.findIndex((f) => {
						return f.path.endsWith(".css") && f.path.includes(`/${name}.bundle.`);
					});

					let css_data = JSON.stringify(result.outputFiles[index].text);
					let modified = `frappe.dom.set_style(${css_data});\n${out.text}`;
					out.contents = Buffer.from(modified);

					// esbuild hashed the filename from the js alone; the css
					// inlined above changes the content, so re-hash the name —
					// otherwise css-only edits ship under an unchanged
					// (browser-cached) url
					let new_path = out.path.replace(/\.\w+\.js$/, `.${content_hash(modified)}.js`);
					if (new_path !== out.path) {
						let map = result.outputFiles.find((f) => f.path === out.path + ".map");
						if (map) {
							out.contents = Buffer.from(
								modified.replace(
									`sourceMappingURL=${path.basename(out.path)}.map`,
									`sourceMappingURL=${path.basename(new_path)}.map`
								)
							);
							rename_metafile_output(result.metafile, map.path, new_path + ".map");
							map.path = new_path + ".map";
						}
						rename_metafile_output(result.metafile, out.path, new_path);
						out.path = new_path;
					}

					// the css is inlined and its files never written — drop them
					// from the metafile too, or assets.json records a phantom
					// entry and cleanup derives delete patterns from it that
					// match (and remove) the just-written js
					let css_path = result.outputFiles[index].path;
					delete_metafile_output(result.metafile, css_path);
					result.outputFiles.splice(index, 1);
					let map_index = result.outputFiles.findIndex(
						(f) => f.path === css_path + ".map"
					);
					if (map_index !== -1) {
						delete_metafile_output(result.metafile, css_path + ".map");
						result.outputFiles.splice(map_index, 1);
					}
				}
			}
			// awaited: onEnd resolves before the next plugin (cleanup) globs the
			// dir, and before the build's process.exit can drop pending writes
			await Promise.all(
				result.outputFiles.map((out) => {
					fs.mkdirSync(path.dirname(out.path), { recursive: true });
					return fs.promises.writeFile(out.path, out.contents);
				})
			);
		});
	},
};

// 8 chars from the same base32 alphabet esbuild uses for [hash]
function content_hash(text) {
	const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
	const digest = crypto.createHash("sha256").update(text).digest();
	return [...digest.subarray(0, 8)].map((byte) => alphabet[byte % 32]).join("");
}

// metafile keys are cwd-relative; assets.json and build-cleanup read them,
// so the rename has to land there too
function rename_metafile_output(metafile, old_path, new_path) {
	for (let key of Object.keys(metafile.outputs)) {
		if (path.resolve(key) === old_path) {
			let new_key = key.slice(0, -path.basename(old_path).length) + path.basename(new_path);
			metafile.outputs[new_key] = metafile.outputs[key];
			delete metafile.outputs[key];
			return;
		}
	}
}

function delete_metafile_output(metafile, abs_path) {
	for (let key of Object.keys(metafile.outputs)) {
		if (path.resolve(key) === abs_path) {
			delete metafile.outputs[key];
			return;
		}
	}
}

function get_files(files) {
	let result = {};
	for (let file in files) {
		let info = files[file];
		let asset_path = "/" + path.relative(sites_path, file);
		if (info && info.entryPoint && Object.keys(info.inputs).length !== 0) {
			for (let input in info.inputs) {
				if (input.includes(".vue?type=style")) {
					let bundle_css = path.basename(info.entryPoint).replace(".js", ".css");
					result[asset_path] = bundle_css;
					break;
				}
			}
		}
	}
	return result;
}
