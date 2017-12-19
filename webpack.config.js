var path = require('path');
var webpack = require('webpack');
const source = path.resolve('apps/frappe/frappe/public/js')
const UglifyJsPlugin = require('uglifyjs-webpack-plugin');

const dev_mode = true;

const plugins = [
    !dev_mode && new UglifyJsPlugin(),
    new webpack.IgnorePlugin(/^codemirror$/),

    new webpack.optimize.CommonsChunkPlugin({
        name: "common",
        filename: "common.bundle.js",
        minChunks: 2
    })

].filter(Boolean);

// const entries = [
//     "frappe-web.min.js",
//     "control.min.js",
//     "dialog.min.js",
//     "libs.min.js",
//     "desk.min.js",
//     "form.min.js",
//     "list.min.js",
//     "report.min.js",
//     "web_form.min.js",
//     "print_format_v3.min.js",
// ].reduce((entry, filename) => {
//     entry[filename] = path.join(source, filename)
//     return entry;
// }, {});
const entries = [
    "desk", "dialog", "controls"
].reduce((entry, filename) => {
    entry[filename] = path.join(source, filename) + '.js';
    return entry;
}, { });

const dest = path.join('sites', 'assets');

module.exports = {
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
                exclude: /(node_modules)/,
                loader: 'babel-loader'
            }
        ],
        rules: [{
            test: /\.html$/,
            loader: path.join(source, 'webpack', 'loaders', 'frappe-html-loader.js')
        }]
    },
    plugins,
    resolve: {
        modules: [
            'node_modules',
            path.resolve('apps/frappe/frappe')
        ]
    }
}