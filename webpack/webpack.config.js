const path = require('path');
const webpack = require('webpack');
const UglifyJsPlugin = require('uglifyjs-webpack-plugin');

const frappe_path = path.resolve(__dirname, '..', 'frappe');
const source = path.join(frappe_path, 'public/js');

const dev_mode = process.env.ENV === 'development';

const plugins = [
	!dev_mode && new UglifyJsPlugin(),
	new webpack.IgnorePlugin(/^codemirror$/),

	new webpack.optimize.CommonsChunkPlugin({
		name: "common",
		filename: "common.bundle.js",
		minChunks: 2
	})

].filter(Boolean);

let entries = [
	"desk", "dialog", "controls"
].reduce((entry, filename) => {
	entry[filename] = path.join(source, filename) + '.js';
	return entry;
}, { });

const babel_excludes = [
	/(node_modules)/,
	/class\.js/,
	/microtemplate\.js/
];

module.exports = function (options) {
	// console.log(options);

	// if ( options.context.entry )
	// 	entries = options.context.entry;

	return {
		entry: entries,
		output: {
			path: path.join(source, 'dist'),
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
				}
			]
		},
		plugins,
		resolve: {
			modules: [
				'node_modules',
				path.resolve(__dirname)
			]
		}
	};
};
