const fs = require("fs");
const path = require("path");
const { sites_path } = require("./utils");

module.exports = {
	name: "frappe-vue-style",
	setup(build) {
		build.initialOptions.write = false;
		build.onEnd((result) => {
			let files = get_files(result.metafile.outputs);
			let keys = Object.keys(files);
			for (let out of result.outputFiles) {
				let asset_path = "/" + path.relative(sites_path, out.path);
				let dir = path.dirname(out.path);
				if (out.path.endsWith(".js") && keys.includes(asset_path)) {
					let name = out.path.split(".bundle.")[0];
					name = path.basename(name);

					let index = result.outputFiles.findIndex((f) => {
						return f.path.endsWith(".css") && f.path.includes(`/${name}.bundle.`);
					});

					let css_data = JSON.stringify(result.outputFiles[index].text);
					let modified = `frappe.dom.set_style(${css_data});\n${out.text}`;
					out.contents = Buffer.from(modified);

					result.outputFiles.splice(index, 1);
					if (result.outputFiles[index - 1].path.endsWith(".css.map")) {
						result.outputFiles.splice(index - 1, 1);
					}
				}
				if (!fs.existsSync(dir)) {
					fs.mkdirSync(dir, { recursive: true });
				}
				fs.writeFile(out.path, out.contents, (err) => {
					err && console.error(err);
				});
			}
		});
	},
};

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
