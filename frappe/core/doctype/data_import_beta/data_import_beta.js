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

			frm
				.call({
					doc: frm.doc,
					method: 'get_preview_from_template',
					freeze: true,
					freeze_message: __('Preparing Preview...')
				})
				.then(r => {
					let preview_data = r.message;
					frm.events.show_import_preview(frm, preview_data);
				});
		} else {
			frm.get_field('import_preview').$wrapper.empty();
		}
		frm.toggle_display('section_import_preview', frm.doc.import_file);
	},

	show_import_preview(frm, preview_data) {
		frappe.require('/assets/js/data_import_tools.min.js', () => {
			new frappe.data_import.ImportPreview({
				wrapper: frm.get_field('import_preview').$wrapper,
				doctype: frm.doc.reference_doctype,
				preview_data,
				events: {
					remap_column(column_name, fieldname) {
						let import_json = JSON.parse(frm.doc.import_json || '{}');
						import_json.remap_column = import_json.remap_column || {};
						import_json.remap_column[column_name] = fieldname;
						// if the column is remapped, remove it from skip_import
						if (
							import_json.skip_import &&
							import_json.skip_import.includes(column_name)
						) {
							import_json.skip_import = import_json.skip_import.filter(
								d => d !== column_name
							);
						}
						frm.set_value('import_json', JSON.stringify(import_json));
						frm.trigger('import_file');
					},

					skip_import(column_name) {
						let import_json = JSON.parse(frm.doc.import_json || '{}');
						import_json.skip_import = import_json.skip_import || [];
						if (!import_json.skip_import.includes(column_name)) {
							import_json.skip_import.push(column_name);
						}
						// if column is being skipped, remove it from remap_column
						if (
							import_json.remap_column &&
							import_json.remap_column[column_name]
						) {
							delete import_json.remap_column[column_name];
						}
						frm.set_value('import_json', JSON.stringify(import_json));
						frm.trigger('import_file');
					}
				}
			});
		});
	}
});
