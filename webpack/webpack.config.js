const path = require('path');
const webpack = require('webpack');

const { sites_path, bundle_map } = require('./utils');

// plugins
const UglifyJsPlugin = require('uglifyjs-webpack-plugin');
const ExtractTextPlugin = require("extract-text-webpack-plugin");
const extractCSS = new ExtractTextPlugin({
	filename: "[name].css"
});
// environment
const dev_mode = process.env.FRAPPE_ENV === 'development';

module.exports = function () {
	return {
		entry: bundle_map,

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
						use: [{
							loader: "css-loader"
						}, {
							loader: "less-loader"
						}]
					})
				}
			]
		},

		plugins: [
			!dev_mode && new UglifyJsPlugin(),

			new webpack.optimize.CommonsChunkPlugin({
				name: "common",
				filename: "common.bundle.js",
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
