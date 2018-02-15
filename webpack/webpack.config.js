const path = require('path');
const webpack = require('webpack');

const {
	sites_path,
	bundle_map,
	get_public_path
} = require('./utils');

// plugins
const UglifyJsPlugin = require('uglifyjs-webpack-plugin');
const ExtractTextPlugin = require("extract-text-webpack-plugin");
const extractCSS = new ExtractTextPlugin({
	filename: (getPath) => {
		let file_name = getPath('[name].css');
		return file_name.replace('js', 'css');
	}
});
// environment
const in_production = process.env.FRAPPE_ENV === 'production';

module.exports = function () {
	const desk_chunks = Object.keys(bundle_map).filter(file_path =>
		file_path.startsWith('frappe/js')
		&& !file_path.includes('frappe-web')
	);
	const global_chunks = Object.keys(bundle_map).filter(file_path =>
		file_path.includes('frappe/js/frappe-web')
		|| file_path.includes('frappe/js/desk')
	);

	return {
		entry: Object.assign(bundle_map, {
			"frappe/js/vendor": [
				'script-loader!jquery',
				'script-loader!moment',
				// 'script-loader!moment-timezone',
				'script-loader!summernote',
				'script-loader!sortablejs',
			]
		}),

		devtool: !in_production ? 'eval-source-map' : undefined,

		output: {
			path: path.join(sites_path, 'assets/bundles'),
			filename: '[name].bundle.js',
			chunkFilename: '[name].bundle.js'
		},

		module: {
			rules: [
				{
					test: /\.js$/,
					exclude: [
						/(node_modules)/,
						/class\.js/,
						/microtemplate\.js/
					],
					loader: 'babel-loader',
				},
				{
					test: /\.html$/,
					loader: path.resolve(__dirname, 'loaders', 'frappe-html-loader.js')
				},
				{
					test: /\.css$/,
					use: extractCSS.extract({
						use: [{
							loader: "css-loader"
						}]
					})
				},
				{
					test: /\.less$/,
					use: extractCSS.extract({
						use: [
							{
								loader: "css-loader"
							},
							{
								loader: "less-loader", options: {
									paths: [path.join(get_public_path('frappe'), 'less')]
								}
							}
						]
					})
				},
				{
					test: /\.(woff|woff2|eot|ttf|otf)$/,
					use: {
						loader: 'file-loader', options: {
							publicPath: '/assets/bundles/',
							outputPath: 'fonts/'
						}
					}
				},
				{
					test: /\.(svg|png|jpg|gif)$/,
					use: {
						loader: 'file-loader', options: {
							publicPath: '/assets/bundles/',
							outputPath: 'images/'
						}
					}
				}
			]
		},

		plugins: [
			// uglify in production
			in_production ? new UglifyJsPlugin() : null,

			// contains webpack bootstrap code
			new webpack.optimize.CommonsChunkPlugin({
				name: "frappe/js/manifest",
				minChunks: Infinity
			}),

			new webpack.optimize.CommonsChunkPlugin({
				name: "frappe/js/desk-commons",
				chunks: desk_chunks,
				minChunks: 2
			}),

			new webpack.optimize.CommonsChunkPlugin({
				name: "frappe/js/global-commons",
				chunks: global_chunks,
				minChunks: 2
			}),

			extractCSS

		].filter(Boolean),

		resolve: {
			modules: [
				'node_modules'
			]
		}
	};
};