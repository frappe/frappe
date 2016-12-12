// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import', {
	refresh: function(frm) {
		//frm.get_field('preview_html').wrapper
		var preview_html = ["<h1>Manas Solanki</h1>"]
		set_field_options("file_preview", preview_html);
	}
});
