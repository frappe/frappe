const fs = require('fs');

const path = require('path');
const webpack = require('webpack');
const UglifyJsPlugin = require('uglifyjs-webpack-plugin');

const ExtractTextPlugin = require("extract-text-webpack-plugin");
const extractLess = new ExtractTextPlugin({
	filename: "[name].css"
});

const frappe_path = process.cwd();
const bench_path = path.resolve(frappe_path, '..', '..');
const sites_path = path.resolve(bench_path, 'sites');
const apps_list = fs.readFileSync(path.resolve(bench_path, 'sites', 'apps.txt'), { encoding: 'utf-8' }).split('\n');

const app_paths = apps_list.reduce((out, app) => {
	out[app] = path.resolve(bench_path, 'apps', app, app)
	return out;
}, {});
const public_paths = apps_list.reduce((out, app) => {
	out[app] = path.resolve(app_paths[app], 'public');
	return out;
}, {});
const public_js_paths = apps_list.reduce((out, app) => {
	out[app] = path.resolve(app_paths[app], 'public/js');
	return out;
}, {});

const entries = apps_list.reduce((out, app) => {
	const public_js_path = public_js_paths[app];
	const all_files = fs.readdirSync(public_js_path);
	const js_files = all_files.filter(file => file.endsWith('.js'));

	for (let js_file of js_files) {
		const filename = path.basename(js_file).split('.')[0];
		out[path.join(app, filename)] = path.resolve(public_js_path, js_file);
	}

	return out;
}, {});

const dev_mode = process.env.FRAPPE_ENV === 'development';

const plugins = [
	!dev_mode && new UglifyJsPlugin(),

	new webpack.optimize.CommonsChunkPlugin({
		name: "common",
		filename: "common.bundle.js",
		minChunks: 2
	}),
	extractLess

].filter(Boolean);

const babel_excludes = [
	/(node_modules)/,
	/class\.js/,
	/microtemplate\.js/
];

module.exports = function (options) {
	return {
		entry: entries,
		output: {
			path: path.join(sites_path, 'dist'),
			filename: '[name].bundle.js',
			chunkFilename: '[name].bundle.js'
		},
		module: {
			rules: [
				{
					test: /\.js$/,
					exclude: babel_excludes,
					loader: 'babel-loader',
				},
				{
					test: /\.html$/,
					loader: path.resolve(__dirname, 'loaders', 'frappe-html-loader.js')
				},
				{
					test: /\.less$/,
					use: extractLess.extract({
						use: [{
							loader: "css-loader"
						}, {
							loader: "less-loader"
						}]
					})
				}
			]
		},
		plugins,
		resolve: {
			modules: [
				'node_modules'
			]
		}
	};
};
