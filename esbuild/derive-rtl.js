const path = require("path");
const fs = require("fs");
const crypto = require("crypto");
const postcss = require("postcss");
const rtlcss = require("rtlcss");
const { clean_dist_files } = require("./build-cleanup");

// esbuild names hashed outputs with an uppercase base32 alphabet; mimic it so
// derived RTL files look like every other dist asset.
const HASH_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

function content_hash(contents) {
	const digest = crypto.createHash("sha256").update(contents).digest();
	let hash = "";
	for (let i = 0; i < 8; i++) {
		hash += HASH_ALPHABET[digest[i] % HASH_ALPHABET.length];
	}
	return hash;
}

function is_ltr_css_output([output, info]) {
	return Boolean(info.entryPoint) && output.endsWith(".css") && output.includes("/dist/css/");
}

// RTL stylesheets are derived by running rtlcss over the compiled LTR CSS
// instead of compiling every .bundle.scss a second time. Returns a
// result-shaped object ({ metafile }) consumable by write_assets_json and
// log_built_assets, or null when the metafile has no stylesheet outputs
// (e.g. a JS build's rebuild in watch mode).
async function derive_rtl_styles(metafile) {
	const css_outputs = Object.entries(metafile.outputs).filter(is_ltr_css_output);
	if (!css_outputs.length) return null;

	const outputs = {};
	await Promise.all(
		css_outputs.map(async ([output, info]) => {
			const { rtl_path, bytes, map_bytes } = await derive_rtl_file(output);
			outputs[rtl_path] = { entryPoint: info.entryPoint, bytes };
			if (map_bytes != null) {
				outputs[`${rtl_path}.map`] = { bytes: map_bytes };
			}
		})
	);
	// These files don't flow through an esbuild build, so the build_cleanup
	// plugin never sees them; delete stale hashed copies here.
	clean_dist_files(Object.keys(outputs));
	return { metafile: { outputs } };
}

async function derive_rtl_file(ltr_path) {
	// Strip the LTR sourceMappingURL annotation: the map is passed explicitly
	// via `prev` below, and postcss keeps the comment when `annotation: false`,
	// which would leave the RTL file pointing at the LTR map.
	const css = (await fs.promises.readFile(ltr_path, "utf-8")).replace(
		/\/\*# sourceMappingURL=\S+ \*\/\n?$/,
		""
	);
	let prev_map;
	try {
		prev_map = await fs.promises.readFile(`${ltr_path}.map`, "utf-8");
	} catch {
		// no LTR source map; emit the RTL css without one
	}

	const rtl_dir = path.join(path.dirname(path.dirname(ltr_path)), "css-rtl");
	// "desk.bundle.HASH.css" -> "desk.bundle"
	const base = path.basename(ltr_path).split(".").slice(0, -2).join(".");

	const result = await postcss([rtlcss]).process(css, {
		from: ltr_path,
		to: path.join(rtl_dir, `${base}.css`),
		map: prev_map ? { prev: prev_map, annotation: false } : false,
	});

	// The RTL file needs its own content hash for cache busting (its contents
	// differ from the LTR file). Hash before appending the sourceMappingURL
	// annotation, like esbuild does.
	const rtl_name = `${base}.${content_hash(result.css)}.css`;
	const rtl_path = path.join(rtl_dir, rtl_name);

	await fs.promises.mkdir(rtl_dir, { recursive: true });

	let css_out = result.css;
	let map_out;
	if (result.map) {
		const map = result.map.toJSON();
		map.file = rtl_name;
		map_out = JSON.stringify(map);
		css_out += `\n/*# sourceMappingURL=${rtl_name}.map */\n`;
	}

	const writes = [fs.promises.writeFile(rtl_path, css_out)];
	if (map_out) {
		writes.push(fs.promises.writeFile(`${rtl_path}.map`, map_out));
	}
	await Promise.all(writes);

	return {
		rtl_path,
		bytes: Buffer.byteLength(css_out),
		map_bytes: map_out ? Buffer.byteLength(map_out) : null,
	};
}

module.exports = { derive_rtl_styles };
