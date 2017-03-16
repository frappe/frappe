const path = require('path');
const fs = require('fs');
const babel = require('babel-core');
const less = require('less');
const p = path.resolve;

// basic setup
const sites_path = p(__dirname, '..', '..', '..', 'sites');
const apps_path = p(__dirname, '..', '..', '..', 'apps'); // the apps folder
const apps_contents = fs.readFileSync(p(sites_path, 'apps.txt'), 'utf8');
const apps = apps_contents.split('\n');
const app_paths = apps.map(app => p(apps_path, app, app)) // base_path of each app
const assets_path = p(sites_path, 'assets');

// console.log(sites_path, app_paths);

build();

function build() {
	const build_map = make_build_map();
	pack(build_map);
}

function pack(build_map) {
	for (const output_path in build_map) {
		const inputs = build_map[output_path];
		const output_type = output_path.split('.').pop();

		let output_txt = '';
		for (const file of inputs) {

			if(!fs.existsSync(file)) {
				console.log('File not found: ', file);
				continue;
			}

			let file_content = fs.readFileSync(file, 'utf-8');

			if (file.endsWith('.html') && output_type === 'js') {
				file_content = html_to_js_template(file, file_content);
			}

			if (file.endsWith('.js') && !file.includes('/lib/') && output_type === 'js' && !file.endsWith('class.js')) {
				file_content = babelify(file_content, file);
			}

			output_txt += `\n/*\n *\t${file}\n */`;
			output_txt += '\n' + file_content + '\n';
		}

		const target = p(assets_path, output_path);

		try {
			fs.writeFileSync(target, output_txt);
			console.log(`Wrote ${output_path} - ${get_file_size(target)}`);
		} catch (e) {
			console.log('Error writing to file', output_path);
			console.log(e);
		}
	}
}

function babelify(content, path) {
	try {
		return babel.transform(content, {
			presets: ['es2015']
		}).code;
	} catch (e) {
		console.log('Cannot babelify', path);
		console.log(e);
		return content;
	}
}

function make_build_map() {
	const build_map = {};
	for (const app_path of app_paths) {
		const build_json_path = p(app_path, 'public', 'build.json');
		if (!fs.existsSync(build_json_path)) continue;

		let build_json = fs.readFileSync(build_json_path);
		try {
			build_json = JSON.parse(build_json);
		} catch (e) {
			console.log(e);
			continue;
		}

		for (const target in build_json) {
			const sources = build_json[target];

			const new_sources = [];
			for (const source of sources) {
				const s = p(app_path, source);
				new_sources.push(s);
			}

			if (new_sources.length)
				build_json[target] = new_sources;
			else
				delete build_json[target];
		}

		Object.assign(build_map, build_json);
	}
	return build_map;
}

function make_asset_dirs(make_copy = false) {
	

	for (const dir_path of [p(assets_path, 'js'), p(assets_path, 'css')]) {
		if (!fs.existsSync(dir_path)) {
			fs.mkdirSync(dir_path);
		}
	}

	// symlink app/public > assets/app
	for (const app_name of apps) {
		const app_base_path = get_app_base_path(app_name);

		let symlinks = []
		symlinks.push([p(app_base_path, 'public'), p(assets_path, app_name)])
		symlinks.push([p(app_base_path, 'docs'), p(assets_path, app_name + '_docs')])

		for (const symlink of symlinks) {
			const source = symlink[0];
			const target = symlink[1];

			if (!fs.existsSync(target) && fs.existsSync(source)) {
				if (make_copy)
					shutil.copytree(source, target)
				else
					os.symlink(source, target)
			}
		}
	}
}

function compile_less() {
	for (const app of apps) {

		const public_path = p(get_app_path(app), 'public');
		const less_path = p(public_path, 'less');

		if (!fs.existsSync(less_path)) continue;
		const files = fs.readdirSync(less_path);

		for (const file of files) {
			compile_less_file(file, less_path, public_path);
		}
	}
	// watch_less();
}

// compile_less();

function compile_less_file(file, less_path, public_path) {

	const file_content = fs.readFileSync(p(less_path, file), 'utf8');
	const output_file = file.split('.')[0] + '.css';

	less.render(file_content, {
		paths: [p(less_path)],
		outputDir: p(public_path, 'css'),
		filename: file,
		compress: true
	}, (e, res) => {
		if (!e) {
			fs.writeFileSync(p(public_path, 'css', output_file), res.css)
			console.log(output_file, ' compiled');
		} else {
			console.log(e, css)
		}
	})
}

function watch_less() {
	const less_paths = apps.map((app) => p(get_app_path(app), 'public', 'less'));
	// console.log(less_paths)
	for (const less_path of less_paths) {
		const public_path = p(less_path, '..');
		if (!fs.existsSync(less_path)) continue;
		fs.watch(p(less_path), (e, filename) => {
			console.log(filename, ' changed');
			compile_less_file(filename, less_path, public_path);
		});
	}
}
// bundle();

function get_app_base_path(app) {
	return p(apps_folder, app, app);
}

function html_to_js_template(path, content) {
	let key = path.split('/');
	key = key[key.length - 1];
	key = key.split('.')[0];

	content = scrub_html_template(content);
	return `frappe.templates['${key}'] = '${content}';\n`;
}

function scrub_html_template(content) {
	content = content.replace(/\s/g, ' ');
	content = content.replace(/(<!--.*?-->)/g, '');
	return content.replace("'", "\'");
}

function get_file_size(filepath) {
	const stats = fs.statSync(filepath);
	const size = stats.size;
	// convert it to humanly readable format.
	const i = Math.floor(Math.log(size) / Math.log(1024));
	return (size / Math.pow(1024, i)).toFixed(2) * 1 + ' ' + ['B', 'KB', 'MB', 'GB', 'TB'][i];
}