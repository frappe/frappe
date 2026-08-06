const fs = require("fs");
const { sass, sass_options } = require("./esbuild/sass_compiler");

const output_path = process.argv[2];
const scss_content = process.argv[3].replace(/\\n/g, "\n");

// The caller (website_theme.py) treats anything on stderr as a compile
// failure, so errors go to console.error and success prints only the path.
sass.compileStringAsync(scss_content, {
	style: "compressed",
	...sass_options,
	sourceMap: false,
})
	.then((result) => fs.promises.writeFile(output_path, result.css))
	.then(() => console.log(output_path))
	.catch((err) => {
		console.error(err.message || err);
		process.exitCode = 1;
	});
