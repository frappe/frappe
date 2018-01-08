const path = require('path');
const fs = require('fs');
const frappe_path = process.cwd();
const bench_path = path.resolve(frappe_path, '..', '..');
const sites_path = path.resolve(bench_path, 'sites');
const apps_list = fs.readFileSync(path.resolve(bench_path, 'sites', 'apps.txt'), { encoding: 'utf-8' }).split('\n').filter(Boolean);

const app_paths = apps_list.reduce((out, app) => {
	out[app] = path.resolve(bench_path, 'apps', app, app)
	return out;
}, {});
// const public_paths = apps_list.reduce((out, app) => {
// 	out[app] = path.resolve(app_paths[app], 'public');
// 	return out;
// }, {});
const public_js_paths = apps_list.reduce((out, app) => {
	out[app] = path.resolve(app_paths[app], 'public/js');
	return out;
}, {});

const bundle_map = apps_list.reduce((out, app) => {
	const public_js_path = public_js_paths[app];
	const all_files = fs.readdirSync(public_js_path);
	const js_files = all_files.filter(file => file.endsWith('.js'));

	for (let js_file of js_files) {
		const filename = path.basename(js_file).split('.')[0];
		out[path.join(app, filename)] = path.resolve(public_js_path, js_file);
	}

	return out;
}, {});

module.exports = {
	sites_path,
	bundle_map
};
