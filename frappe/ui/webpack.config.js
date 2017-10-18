const path = require('path');

module.exports = {
	entry: './index.js',
	output: {
		filename: 'frappe.ui.js',
		path: path.resolve(__dirname, 'dist')
	}
};
