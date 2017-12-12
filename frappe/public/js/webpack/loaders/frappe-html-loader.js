var path = require('path');

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

module.exports = function (source)
{
	var filepath = path.basename(this.resourcePath).split('.');
	filepath.splice(-1);

	var key = filepath.join(".");
	

	var content = scrub_html_template(source);
	return `frappe.templates['${key}'] = '${content}';\n`;
};