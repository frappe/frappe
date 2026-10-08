const sass = require("sass");
const fs = require("fs");
const path = require("path");
const sass_options = require("./esbuild/sass_options");
let output_path = process.argv[2];
let scss_content = process.argv[3];
scss_content = scss_content.replace(/\\n/g, "\n");

const css_import = /@import\s*(?:url\(\s*)?["']([^"']+)["']\s*\)?\s*;/g;

// where sass found the import, e.g. "frappe/public/css/..." under apps/frappe
function resolve_import(url) {
	for (const base of sass_options.includePaths) {
		const file = path.resolve(base, url);
		if (file.startsWith(base + path.sep) && fs.existsSync(file)) return file;
	}
}

// Sass leaves an @import of a .css file (Espresso's tokens and components, the Inter font)
// as a plain CSS import. The desk build's esbuild inlines those; a theme is served from
// /files, where the browser can't resolve them. So inline the ones that live in an app,
// and keep remote ones (web fonts) ahead of everything, where CSS requires @import to be.
function inline_css_imports(css, seen = new Set()) {
	const remote = [];
	const body = css.replace(css_import, (statement, url) => {
		if (/^([a-z]+:)?\/\//i.test(url)) {
			remote.push(statement);
			return "";
		}
		const file = resolve_import(url);
		if (!file) return statement;
		if (seen.has(file)) return "";
		seen.add(file);
		const inlined = inline_css_imports(fs.readFileSync(file, "utf8"), seen);
		remote.push(...inlined.remote);
		return inlined.body;
	});
	return { remote, body };
}

sass.render(
	{
		data: scss_content,
		outputStyle: "compressed",
		...sass_options,
	},
	function (err, result) {
		if (err) {
			console.error(err.formatted);
			return;
		}

		// compressed output marks non-ASCII content with a BOM, which has to stay first
		let css = result.css.toString();
		const bom = css.startsWith("﻿") ? "﻿" : "";
		const { remote, body } = inline_css_imports(css.slice(bom.length));
		css = bom + remote.join("") + body;

		fs.writeFile(output_path, css, function (err) {
			if (!err) {
				console.log(output_path);
			} else {
				console.error(err);
			}
		});
	}
);
