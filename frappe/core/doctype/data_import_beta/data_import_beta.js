// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import Beta', {
	setup(frm) {
		frappe.realtime.on('data_import_progress', data => {
			let percent = Math.floor((data.current * 100) / data.total);
			let message;
			if (data.success) {
				message = __('Importing {0} ({1} of {2})', [data.docname, data.current, data.total]);
			}
			if (data.skipping) {
				message = __('Skipping ({1} of {2})', [data.current, data.total]);
			}
			frm.dashboard.show_progress(__('Import Progress'), percent, message);

			// hide progress when complete
			if (data.current === data.total) {
				setTimeout(() => {
					frm.dashboard.hide();
					frm.refresh();
				}, 2000);
			}
		});
	},

	refresh(frm) {
		frm.page.hide_icon_group();
		frm.trigger('import_file');

		if (frm.doc.status === 'Pending') {
			if (!frm.is_new()) {
				frm.page.set_primary_action(__('Start Import'), () =>
					frm.events.start_import(frm)
				);
			} else {
				frm.page.set_primary_action(__('Save'), () => frm.save());
			}
		} else {
			frm.disable_save();
			frm.events.after_success(frm);
		}
	},

	after_success(frm) {
		let import_log = JSON.parse(frm.doc.import_log || '[]');
		let successful_records = import_log.filter(log => log.success);
		frm.dashboard.set_headline(__('Successfully imported {0} records', [successful_records.length]));
	},

	start_import(frm) {
		let csv_array = frm.import_preview.get_rows_as_csv_array();
		let template_options = JSON.parse(frm.doc.template_options || '{}');
		template_options.edited_rows = csv_array;
		frm.set_value('template_options', JSON.stringify(template_options));

		frm.save().then(() => {
			frm.trigger('import_file').then(() =>
				frm.call('start_import').then(r => {
					let { warnings, missing_link_values } = r.message || {};
					if (warnings) {
						frm.import_preview.render_warnings(warnings);
					} else if (missing_link_values) {
						frm.events.show_missing_link_values(frm, missing_link_values);
					} else {
						frm.refresh();
					}
				})
			);
		});
	},

	download_sample_file(frm) {
		frappe.require('/assets/js/data_import_tools.min.js', () => {
			new frappe.data_import.DataExporter(frm.doc.reference_doctype);
		});
	},

	import_file(frm) {
		frm.toggle_display('section_import_preview', frm.doc.import_file);
		if (!frm.doc.import_file) {
			frm.get_field('import_preview').$wrapper.empty();
			return;
		}

		// load import preview
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
	},

	show_import_preview(frm, preview_data) {
		let import_log = JSON.parse(frm.doc.import_log || '[]');

		if (frm.import_preview) {
			frm.import_preview.preview_data = preview_data;
			frm.import_preview.import_log = import_log;
			frm.import_preview.refresh();
			return;
		}

		frappe.require('/assets/js/data_import_tools.min.js', () => {
			frm.import_preview = new frappe.data_import.ImportPreview({
				wrapper: frm.get_field('import_preview').$wrapper,
				doctype: frm.doc.reference_doctype,
				preview_data,
				import_log,
				events: {
					remap_column(header_row_index, fieldname) {
						let template_options = JSON.parse(frm.doc.template_options || '{}');
						template_options.remap_column = template_options.remap_column || {};
						template_options.remap_column[header_row_index] = fieldname;
						// if the column is remapped, remove it from skip_import
						if (
							template_options.skip_import &&
							template_options.skip_import.includes(header_row_index)
						) {
							template_options.skip_import = template_options.skip_import.filter(
								d => d !== header_row_index
							);
						}
						frm.set_value('template_options', JSON.stringify(template_options));
						frm.save().then(() => {
							frm.trigger('import_file');
						});
					},

					skip_import(header_row_index) {
						let template_options = JSON.parse(frm.doc.template_options || '{}');
						template_options.skip_import = template_options.skip_import || [];
						if (!template_options.skip_import.includes(header_row_index)) {
							template_options.skip_import.push(header_row_index);
						}
						// if column is being skipped, remove it from remap_column
						if (
							template_options.remap_column &&
							template_options.remap_column[header_row_index]
						) {
							delete template_options.remap_column[header_row_index];
						}
						frm.set_value('template_options', JSON.stringify(template_options));
						frm.save().then(() => {
							frm.trigger('import_file');
						});
					}
				}
			});
		});
	},

	show_import_log(frm) {
		frm.toggle_display('import_log', false);
		if (!frm.doc.import_log) {
			frm.get_field('import_log_preview').$wrapper.empty();
			return;
		}
		let import_log = JSON.parse(frm.doc.import_log);
		let rows = import_log
			.map(log => {
				if (log.inserted) {
					return `<tr>
						<td>${log.name}</td>
						<td>${log.inserted ? 'Inserted' : ''}</td>
					</tr>`;
				}
				return `<tr>
					<td>Failed</td>
					<td><pre>${log.exception}</pre></td>
				</tr>`;
			})
			.join('');
		frm.get_field('import_log_preview').$wrapper.html(`
			<table class="table table-bordered">
				<tr>
					<th width="30%">${__('Document Name')}</th>
					<th width="70%">${__('Status')}</th>
				</tr>
				${rows}
			</table>
		`);
	},

	show_missing_link_values(frm, missing_link_values) {
		let can_be_created_automatically = missing_link_values.every(
			d => d.has_one_mandatory_field
		);

		let html = missing_link_values
			.map(d => {
				let doctype = d.doctype;
				let values = d.missing_values;
				return `
					<h5>${doctype}</h5>
					<ul>${values.map(v => `<li>${v}</li>`).join('')}</ul>
				`;
			})
			.join('');

		if (can_be_created_automatically) {
			let message = __('There are some linked records which needs to be created before we can import your file. Do you want to create the following missing records automatically?');
			frappe.confirm(message + html, () => {
				frm
					.call('create_missing_link_values', {
						missing_link_values
					})
					.then(r => {
						let records = r.message;
						frappe.msgprint(
							__('Created {0} records successfully.', [records.length])
						);
					});
			});
		} else {
			frappe.msgprint(
				__('The following records needs to be created before we can import your file.') + html
			);
		}
	}
});
