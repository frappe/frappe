// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import Beta', {
	setup(frm) {
		frappe.realtime.on('data_import_refresh', () => {
			frappe.model.clear_doc('Data Import Beta', frm.doc.name);
			frappe.model.with_doc('Data Import Beta', frm.doc.name).then(() => {
				frm.refresh();
			});
		});
		frappe.realtime.on('data_import_progress', data => {
			let percent = Math.floor((data.current * 100) / data.total);
			let eta_message =
				data.eta < 60
					? __('ETA {0} seconds', [Math.floor(data.eta)])
					: __('ETA {0} minutes', [Math.floor(data.eta / 60)]);
			let message;
			if (data.success) {
				let message_args = [data.docname, data.current, data.total];
				message =
					frm.doc.import_type === 'Insert New Records'
						? __('Importing {0} ({1} of {2})', message_args)
						: __('Updating {0} ({1} of {2})', message_args);
			}
			if (data.skipping) {
				message = __('Skipping ({1} of {2})', [data.current, data.total]);
			}
			frm.dashboard.show_progress(__('Import Progress'), percent, message);
			frm.page.set_indicator(eta_message, 'orange');

			// hide progress when complete
			if (data.current === data.total) {
				setTimeout(() => {
					frm.dashboard.hide();
					frm.refresh();
				}, 2000);
			}
		});

		frm.set_query('reference_doctype', () => {
			return {
				filters: {
					allow_import: 1
				}
			};
		});

		frm.get_field('import_file').df.options = {
			restrictions: {
				allowed_file_types: ['.csv', '.xls', '.xlsx']
			}
		};
	},

	refresh(frm) {
		frm.page.hide_icon_group();
		frm.trigger('import_file');
		frm.trigger('show_import_log');
		frm.trigger('show_import_warnings');
		frm.trigger('toggle_submit_after_import');

		if (frm.doc.import_log && frm.doc.import_log !== '[]') {
			// set form as readonly
			frm.fields.forEach(f => (f.df.read_only = 1));
			frm.disable_save();
		}

		if (frm.doc.status === 'Success') {
			frm.events.show_success_message(frm);
		} else {
			if (!frm.is_new() && frm.doc.import_file) {
				let label = frm.doc.status === 'Pending' ? __('Start Import') : __('Retry');
				frm.page.set_primary_action(label, () => frm.events.start_import(frm));
			} else {
				frm.page.set_primary_action(__('Save'), () => frm.save());
			}
		}
		frm.page.set_indicator(
			__(frm.doc.status),
			frm.doc.status === 'Success' ? 'green' : 'grey'
		);
	},

	show_success_message(frm) {
		let import_log = JSON.parse(frm.doc.import_log || '[]');
		let successful_records = import_log.filter(log => log.success);
		let link = `<a href="#List/${frm.doc.reference_doctype}">
			${__('{0} List', [frm.doc.reference_doctype])}
		</a>`;
		let message_args = [successful_records.length, link];
		let message;
		if (frm.doc.import_type === 'Insert New Records') {
			message =
				successful_records.length > 1
					? __('Successfully imported {0} records. Go to {1}', message_args)
					: __('Successfully imported {0} record. Go to {1}', message_args);
		} else {
			message =
				successful_records.length > 1
					? __('Successfully updated {0} records. Go to {1}', message_args)
					: __('Successfully updated {0} record. Go to {1}', message_args);
		}
		frm.dashboard.set_headline(message);
	},

	start_import(frm) {
		let csv_array = frm.import_preview.get_rows_as_csv_array();
		let template_options = JSON.parse(frm.doc.template_options || '{}');
		template_options.edited_rows = csv_array;
		frm.set_value('template_options', JSON.stringify(template_options));
		frm.save().then(() => frm.call('start_import'));
	},

	download_sample_file(frm) {
		frappe.require('/assets/js/data_import_tools.min.js', () => {
			new frappe.data_import.DataExporter(frm.doc.reference_doctype);
		});
	},

	reference_doctype(frm) {
		frm.trigger('toggle_submit_after_import');
	},

	toggle_submit_after_import(frm) {
		frm.toggle_display('submit_after_import', false);
		let doctype = frm.doc.reference_doctype;
		if (doctype) {
			frappe.model.with_doctype(doctype, () => {
				let meta = frappe.get_meta(doctype);
				frm.toggle_display('submit_after_import', meta.is_submittable);
			});
		}
	},

	import_file(frm) {
		frm.toggle_display('section_import_preview', frm.doc.import_file);
		if (!frm.doc.import_file) {
			frm.get_field('import_preview').$wrapper.empty();
			return;
		}

		// load import preview
		frm.get_field('import_preview').$wrapper.empty();
		$('<span class="text-muted">')
			.html(__('Loading import file...'))
			.appendTo(frm.get_field('import_preview').$wrapper);

		frm
			.call({
				doc: frm.doc,
				method: 'get_preview_from_template',
				error_handlers: {
					TimestampMismatchError() {
						// ignore this error
					}
				}
			})
			.then(r => {
				let preview_data = r.message;
				frm.events.show_import_preview(frm, preview_data);
				frm.events.show_import_warnings(frm, preview_data);
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
				frm,
				events: {
					remap_column(changed_map) {
						let template_options = JSON.parse(frm.doc.template_options || '{}');
						template_options.remap_column = template_options.remap_column || {};
						Object.assign(template_options.remap_column, changed_map);

						// if the column is remapped, remove it from skip_import
						if (template_options.skip_import) {
							template_options.skip_import = template_options.skip_import.filter(
								d => !Object.keys(template_options.remap_column).includes(cstr(d))
							);
						}
						frm.set_value('template_options', JSON.stringify(template_options));
						frm.save().then(() => frm.trigger('import_file'));
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
					},

					export_errored_rows() {
						open_url_post('/api/method/frappe.core.doctype.data_import_beta.data_import_beta.download_errored_template', {
							data_import_name: frm.doc.name
						});
					},

					show_warnings() {
						frm.scroll_to_field('import_warnings');
					}
				}
			});
		});
	},

	show_import_warnings(frm, preview_data) {
		frm.toggle_display('import_warnings_section',
			preview_data.warnings && preview_data.warnings.length);
		if (!preview_data) {
			frm.get_field('import_warnings').$wrapper.html('');
			return;
		}
		let warnings = JSON.parse(frm.doc.template_warnings || '[]');
		warnings = warnings.concat(preview_data.warnings || []);

		// group warnings by row
		let warnings_by_row = {};
		let other_warnings = [];
		for (let warning of warnings) {
			if (warning.row) {
				warnings_by_row[warning.row] = warnings_by_row[warning.row] || [];
				warnings_by_row[warning.row].push(warning);
			} else {
				other_warnings.push(warning);
			}
		}

		let html = '';
		html += Object.keys(warnings_by_row).map(row_number => {
			let message = warnings_by_row[row_number]
				.map(w => {
					if (w.field) {
						return `<li>${w.field.label}: ${w.message}</li>`;
					}
					return w.message;
				})
				.join('');
			return `
				<div class="alert border" data-row="${row_number}">
					<div class="uppercase">${__('Row {0}', [row_number])}</div>
					<div class="body"><ul>${message}</ul></div>
				</div>
			`;
		}).join('');

		html += other_warnings
			.map(warning => {
				let header = '';
				if (warning.col) {
					header = __('Column {0}', [warning.col]);
				}
				return `
					<div class="alert border" data-col="${warning.col}">
						<div class="uppercase">${header}</div>
						<div class="body">${warning.message}</div>
					</div>
				`;
			})
			.join('');
		frm.get_field('import_warnings').$wrapper.html(`
			<div class="row">
				<div class="col-sm-6 warnings text-muted">${html}</div>
			</div>
		`);
	},

	show_import_log(frm) {
		let import_log = JSON.parse(frm.doc.import_log || '[]');
		let logs = import_log;
		frm.toggle_display('import_log', false);
		frm.toggle_display('import_log_section', logs.length > 0);

		if (logs.length === 0) {
			frm.get_field('import_log_preview').$wrapper.empty();
			return;
		}

		let rows = logs
			.map(log => {
				let html;
				if (log.success) {
					html = __('Successfully imported {0}', [
						`<span class="underline">${frappe.utils.get_form_link(
							frm.doc.doctype,
							log.docname,
							true
						)}<span>`
					]);
				} else {
					let messages = log.messages
						.map(JSON.parse)
						.map(m => {
							let title = m.title ? `<strong>${m.title}</strong>` : '';
							let message = m.message ? `<p>${m.message}</p>` : '';
							return title + message;
						})
						.join('');
					let id = frappe.dom.get_unique_id();
					html = `${messages}
						<button class="btn btn-default btn-xs" type="button" data-toggle="collapse" data-target="#${id}" aria-expanded="false" aria-controls="${id}">
							${__('Show Traceback')}
						</button>
						<div class="collapse margin-top" id="${id}">
							<div class="well">
								<pre>${log.exception}</pre>
							</div>
						</div>`;
				}
				return `<tr>
					<td>${log.row_indexes.join(', ')}</td>
					<td>${html}</td>
				</tr>`;
			})
			.join('');

		frm.get_field('import_log_preview').$wrapper.html(`
			<table class="table table-bordered">
				<tr class="text-muted">
					<th width="30%">${__('Row Number')}</th>
					<th width="70%">${__('Message')}</th>
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
