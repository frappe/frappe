const sass = require("sass");
const fs = require("fs");
const sass_options = require("./esbuild/sass_options");
let output_path = process.argv[2];
let scss_content = process.argv[3];
scss_content = scss_content.replace(/\\n/g, "\n");

sass.render(
	{
		data: scss_content,
		outputStyle: "compressed",
		...sass_options,
	},
	function (err, result) {
		if (err) {
			console.error(err.formatted); // eslint-disable-line
			return;
		}

		fs.writeFile(output_path, result.css, function (err) {
			if (!err) {
				console.log(output_path); // eslint-disable-line
			} else {
				console.error(err); // eslint-disable-line
			}
		});
	}
);
