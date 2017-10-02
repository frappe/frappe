/*eslint-disable no-console */
const path = require('path');
const fs = require('fs');
const babel = require('babel-core');
const less = require('less');
const chokidar = require('chokidar');
const path_join = path.resolve;

// for file watcher
const app = require('express')();
const http = require('http').Server(app);
const io = require('socket.io')(http);
const touch = require("touch");

// basic setup
const sites_path = path_join(__dirname, '..', '..', '..', 'sites');
const apps_path = path_join(__dirname, '..', '..', '..', 'apps'); // the apps folder
const apps_contents = fs.readFileSync(path_join(sites_path, 'apps.txt'), 'utf8');
const apps = apps_contents.split('\n');
const app_paths = apps.map(app => path_join(apps_path, app, app)) // base_path of each app
const assets_path = path_join(sites_path, 'assets');
let build_map = make_build_map();
const file_watcher_port = get_conf().file_watcher_port;

// command line args
const action = process.argv[2] || '--build';

if (['--build', '--watch'].indexOf(action) === -1) {
	console.log('Invalid argument: ', action);
	process.exit();
}

if (action === '--build') {
	const minify = process.argv[3] === '--minify' ? true : false;
	build(minify);
}

if (action === '--watch') {
	watch();
}

function build(minify) {
	for (const output_path in build_map) {
		pack(output_path, build_map[output_path], minify);
	}
	touch(path_join(sites_path, '.build'), {force:true});
}

let socket_connection = false;

function watch() {
	http.listen(file_watcher_port, function () {
		console.log('file watching on *:', file_watcher_port);
	});

	compile_less().then(() => {
		build();
		watch_less(function (filename) {
			if(socket_connection) {
				io.emit('reload_css', filename);
			}
		});
		watch_js(function (filename) {
			if(socket_connection) {
				io.emit('reload_js', filename);
			}
		});
		watch_build_json();
	});

	io.on('connection', function (socket) {
		socket_connection = true;

		socket.on('disconnect', function() {
			socket_connection = false;
		})
	});
}

function pack(output_path, inputs, minify) {
	const output_type = output_path.split('.').pop();

	let output_txt = '';
	for (const file of inputs) {

		if (!fs.existsSync(file)) {
			console.log('File not found: ', file);
			continue;
		}

		let file_content = fs.readFileSync(file, 'utf-8');

		if (file.endsWith('.html') && output_type === 'js') {
			file_content = html_to_js_template(file, file_content);
		}

		if(file.endsWith('class.js')) {
			file_content = minify_js(file_content, file);
		}

		if (file.endsWith('.js') && !file.includes('/lib/') && output_type === 'js' && !file.endsWith('class.js')) {
			file_content = babelify(file_content, file, minify);
		}

		if(!minify) {
			output_txt += `\n/*\n *\t${file}\n */\n`
		}
		output_txt += file_content;

		output_txt = output_txt.replace(/['"]use strict['"];/, '');
	}

	const target = path_join(assets_path, output_path);

	try {
		fs.writeFileSync(target, output_txt);
		console.log(`Wrote ${output_path} - ${get_file_size(target)}`);
		return target;
	} catch (e) {
		console.log('Error writing to file', output_path);
		console.log(e);
	}
}

function babelify(content, path, minify) {
	let presets = ['env'];
	// Minification doesn't work when loading Frappe Desk
	// Avoid for now, trace the error and come back.
	try {
		return babel.transform(content, {
			presets: presets,
			comments: false
		}).code;
	} catch (e) {
		console.log('Cannot babelify', path);
		console.log(e);
		return content;
	}
}

function minify_js(content, path) {
	try {
		return babel.transform(content, {
			comments: false
		}).code;
	} catch (e) {
		console.log('Cannot minify', path);
		console.log(e);
		return content;
	}
}

function make_build_map() {
	const build_map = {};
	for (const app_path of app_paths) {
		const build_json_path = path_join(app_path, 'public', 'build.json');
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
				const s = path_join(app_path, source);
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

function compile_less() {
	return new Promise(function (resolve) {
		const promises = [];
		for (const app_path of app_paths) {
			const public_path = path_join(app_path, 'public');
			const less_path = path_join(public_path, 'less');
			if (!fs.existsSync(less_path)) continue;

			const files = fs.readdirSync(less_path);
			for (const file of files) {
				if(file.includes('variables.less')) continue;
				promises.push(compile_less_file(file, less_path, public_path))
			}
		}

		Promise.all(promises).then(() => {
			console.log('Less files compiled');
			resolve();
		});
	});
}

function compile_less_file(file, less_path, public_path) {
	const file_content = fs.readFileSync(path_join(less_path, file), 'utf8');
	const output_file = file.split('.')[0] + '.css';
	console.log('compiling', file);

	return less.render(file_content, {
		paths: [less_path],
		filename: file,
		sourceMap: false
	}).then(output => {
		const out_css = path_join(public_path, 'css', output_file);
		fs.writeFileSync(out_css, output.css);
		return out_css;
	}).catch(e => {
		console.log('Error compiling ', file);
		console.log(e);
	});
}

function watch_less(ondirty) {
	const less_paths = app_paths.map(path => path_join(path, 'public', 'less'));

	const to_watch = filter_valid_paths(less_paths);
	chokidar.watch(to_watch).on('change', (filename) => {
		console.log(filename, 'dirty');
		var last_index = filename.lastIndexOf('/');
		const less_path = filename.slice(0, last_index);
		const public_path = path_join(less_path, '..');
		filename = filename.split('/').pop();

		compile_less_file(filename, less_path, public_path)
			.then(css_file_path => {
				// build the target css file for which this css file is input
				for (const target in build_map) {
					const sources = build_map[target];
					if (sources.includes(css_file_path)) {
						pack(target, sources);
						ondirty && ondirty(target);
						break;
					}
				}
			});
		touch(path_join(sites_path, '.build'), {force:true});
	});
}

function watch_js(ondirty) {
	const js_paths = app_paths.map(path => path_join(path, 'public', 'js'));

	const to_watch = filter_valid_paths(js_paths);
	chokidar.watch(to_watch).on('change', (filename, stats) => {
		console.log(filename, 'dirty');
		// build the target js file for which this js/html file is input
		for (const target in build_map) {
			const sources = build_map[target];
			if (sources.includes(filename)) {
				pack(target, sources);
				ondirty && ondirty(target);
				// break;
			}
		}
		touch(path_join(sites_path, '.build'), {force:true});
	});
}

function watch_build_json() {
	const build_json_paths = app_paths.map(path => path_join(path, 'public', 'build.json'));
	const to_watch = filter_valid_paths(build_json_paths);
	chokidar.watch(to_watch).on('change', (filename) => {
		console.log(filename, 'updated');
		build_map = make_build_map();
	});
}

function filter_valid_paths(paths) {
	return paths.filter(path => fs.existsSync(path));
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

function get_conf() {
	// defaults
	var conf = {
		file_watcher_port: 6787
	};

	var read_config = function(path) {
		if (!fs.existsSync(path)) return;
		var bench_config = JSON.parse(fs.readFileSync(path));
		for (var key in bench_config) {
			if (bench_config[key]) {
				conf[key] = bench_config[key];
			}
		}
	}

	read_config(path_join(sites_path, 'common_site_config.json'));
	return conf;
}
