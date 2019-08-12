// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import Beta', {
	refresh(frm) {
		frm.trigger('import_file');
		frm.trigger('reference_doctype');
	},

	reference_doctype(frm) {
		//
	},

	download_sample_file(frm) {
		frappe.require('/assets/js/data_import_tools.min.js', () => {
			new frappe.data_import.DataExporter(frm.doc.reference_doctype);
		});
	},

	import_file(frm) {
		if (frm.doc.import_file) {
			$('<span class="text-muted">')
				.html(__('Loading import file...'))
				.appendTo(frm.get_field('import_preview').$wrapper);

			frm.call('get_preview_from_template').then(r => {
				let preview_data = r.message;

				frappe.require('/assets/js/data_import_tools.min.js', () => {
					new frappe.data_import.ImportPreview(
						frm.get_field('import_preview').$wrapper,
						frm.doc.reference_doctype,
						preview_data
					);
				});
			});
		} else {
			frm.get_field('import_preview').$wrapper.empty();
		}
		frm.toggle_display('section_import_preview', frm.doc.import_file);
	}
});
