const path = require('path');
const webpack = require('webpack');

const { sites_path, bundle_map } = require('./utils');

// plugins
const UglifyJsPlugin = require('uglifyjs-webpack-plugin');
// const ExtractTextPlugin = require("extract-text-webpack-plugin");

// environment
const dev_mode = process.env.FRAPPE_ENV === 'development';

module.exports = function () {
	return {
		entry: bundle_map,

		output: {
			path: path.join(sites_path, 'dist'),
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
				// {
				// 	test: /\.less$/,
				// 	use: ExtractTextPlugin.extract({
				// 		use: [{
				// 			loader: "css-loader"
				// 		}, {
				// 			loader: "less-loader"
				// 		}]
				// 	})
				// }
			]
		},

		plugins: [
			!dev_mode && new UglifyJsPlugin(),

			new webpack.optimize.CommonsChunkPlugin({
				name: "common",
				filename: "common.bundle.js",
				minChunks: 2
			}),

			// new ExtractTextPlugin({
			// 	filename: "[name].css"
			// })

		].filter(Boolean),

		resolve: {
			modules: [
				'node_modules'
			]
		}
	};
};
