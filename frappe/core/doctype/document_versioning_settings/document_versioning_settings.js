// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Document Versioning Settings', {
	onload: function(frm) {
		var page = frappe.ui.make_app_page({
			title: 'Document Versioning Settings',
			parent: frm.wrapper,
			single_column: true
		});
		cur_frm.add_custom_button("Save");
		frappe.get_doctype_list(page);
	},
	validate: function(frm){
		var modules = frappe.get_modules();
		frm.doc.stored_modules = JSON.stringify(modules);
	}
});

frappe.get_modules = function(){
		var modules = {}
		$(".select-module").each(function(foo, bar ) {
			modules[bar.id] = bar.checked;
		})
		return modules;
}

frappe.get_doctype_list = function(page) {
	frappe.call({
		method: 'frappe.core.doctype.document_versioning_settings.document_versioning_settings.get_modules',
		args: {
		},
		callback: function(r) {
			var elements = page.wrapper.find(".layout-main-section")
			$(elements[0]).replaceWith(r.message);
		}
	});
}
