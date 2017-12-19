// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import', {
	onload: function(frm) {
		frm.set_query("reference_doctype", function() {
			return {
				"filters": {
					"issingle": 0,
					"istable": 0,
					"name": ['in', frappe.boot.user.can_import]
				}
			};
		});

		frappe.realtime.on("data_import_progress", function(data) {
			if (data.data_import === frm.doc.name) {
				if (data.reload && data.reload === true) {
					frm.reload_doc();
				}
				if (data.progress) {
					let progress_bar = $(frm.dashboard.progress_area).find(".progress-bar");
					if (progress_bar) {
						$(progress_bar).removeClass("progress-bar-danger").addClass("progress-bar-success progress-bar-striped");
						$(progress_bar).css("width", data.progress+"%");
					}
				}
			}
		});
	},

	refresh: function(frm) {
		frm.disable_save();
		frm.dashboard.clear_headline();
		if (frm.doc.reference_doctype && !frm.doc.import_file) {
			frm.dashboard.add_comment(__('Please attach a file to import'));
		} else {
			if (frm.doc.import_status) {
				frm.dashboard.add_comment(frm.doc.import_status);

				if (frm.doc.import_status==="In Progress") {
					frm.dashboard.add_progress("Data Import Progress", "0");
					frm.set_read_only();
					frm.refresh_fields();
				}
			}
		}

		if (frm.doc.reference_doctype) {
			frappe.model.with_doctype(frm.doc.reference_doctype);
		}

		frm.add_custom_button(__("Help"), function() {
			frappe.help.show_video("6wiriRKPhmg");
		});

		if(frm.doc.reference_doctype && frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Download template"), function() {
				frappe.data_import.download_dialog(frm).show();
			});
		}

		if (frm.doc.reference_doctype && frm.doc.import_file && frm.doc.total_rows  && frm.doc.docstatus === 0) {
			frm.page.set_primary_action(__("Start Import"), function() {
				frappe.call({
					method: "frappe.core.doctype.data_import.data_import.import_data",
					args: {
						data_import: frm.doc.name
					}
				});
			}).addClass('btn btn-primary');
		}

		if (frm.doc.log_details) {
			frm.events.create_log_table(frm);
		} else {
			$(frm.fields_dict.import_log.wrapper).empty();
		}
	},

	reference_doctype: function(frm) {
		if (frm.doc.reference_doctype) {
			frm.save();
		}
	},

	// import_file: function(frm) {
	// 	frm.save();
	// },

	overwrite: function(frm) {
		if (frm.doc.overwrite === 0) {
			frm.doc.only_update = 0;
		}
		frm.save();
	},

	only_update: function(frm) {
		frm.save();
	},

	submit_after_import: function(frm) {
		frm.save();
	},

	skip_errors: function(frm) {
		frm.save();
	},

	ignore_encoding_errors: function(frm) {
		frm.save();
	},

	no_email: function(frm) {
		frm.save();
	},

	show_only_errors: function(frm) {
		frm.events.create_log_table(frm);
	},

	create_log_table: function(frm) {
		let msg = JSON.parse(frm.doc.log_details);
		var $log_wrapper = $(frm.fields_dict.import_log.wrapper).empty();
		$(frappe.render_template("log_details", {data: msg.messages, show_only_errors: frm.doc.show_only_errors,
			import_status: frm.doc.import_status})).appendTo($log_wrapper);
	}
});

frappe.provide('frappe.data_import');
frappe.data_import.download_dialog = function(frm) {
	var dialog;
	const filter_fields = df => frappe.model.is_value_type(df) && !df.hidden;
	const get_fields = dt => frappe.meta.get_docfields(dt).filter(filter_fields);

	const get_doctypes = parentdt => {
		return [parentdt].concat(
			frappe.meta.get_table_fields(parentdt).map(df => df.options)
		);
	};

	const get_doctype_checkbox_fields = () => {
		return dialog.fields.filter(df => df.fieldname.endsWith('_fields'))
			.map(df => dialog.fields_dict[df.fieldname]);
	}

	const doctype_fields = get_fields(frm.doc.reference_doctype)
		.map(df => ({
			label: df.label,
			value: df.fieldname,
			checked: 1
		}));

	let fields = [
		{
			"label": __("Select Columns"),
			"fieldname": "select_columns",
			"fieldtype": "Select",
			"options": "All\nMandatory\nManually",
			"reqd": 1,
			"onchange": function() {
				const fields = get_doctype_checkbox_fields();
				fields.map(f => f.toggle(this.value === 'Manually'));
			}
		},
		{
			"label": __("File Type"),
			"fieldname": "file_type",
			"fieldtype": "Select",
			"options": "Excel\nCSV",
			"default": "Excel"
		},
		{
			"label": __("Download with Data"),
			"fieldname": "with_data",
			"fieldtype": "Check"
		},
		{
			"label": frm.doc.reference_doctype,
			"fieldname": "doctype_fields",
			"fieldtype": "MultiCheck",
			"options": doctype_fields,
			"columns": 2,
			"hidden": 1
		}
	];

	const child_table_fields = frappe.meta.get_table_fields(frm.doc.reference_doctype)
		.map(df => {
			return {
				"label": df.options,
				"fieldname": df.fieldname + '_fields',
				"fieldtype": "MultiCheck",
				"options": frappe.meta.get_docfields(df.options)
					.filter(filter_fields)
					.map(df => ({
						label: df.label,
						value: df.fieldname,
						checked: 1
					})),
				"columns": 2,
				"hidden": 1
			};
		});

	fields = fields.concat(child_table_fields);

	dialog = new frappe.ui.Dialog({
		title: __('Download Template'),
		fields: fields,
		primary_action: function(values) {
			var data = values;
			if (frm.doc.reference_doctype) {
				var export_params = () => {
					let columns = {};
					if (values.select_columns === 'All') {
						columns = get_doctypes(frm.doc.reference_doctype).reduce((columns, doctype) => {
							columns[doctype] = get_fields(doctype).map(df => df.fieldname);
							return columns;
						}, {});
					} else if (values.select_columns === 'Mandatory') {
						// only reqd child tables
						const doctypes = [frm.doc.reference_doctype].concat(
							frappe.meta.get_table_fields(frm.doc.reference_doctype)
								.filter(df => df.reqd).map(df => df.options)
						);

						columns = doctypes.reduce((columns, doctype) => {
							columns[doctype] = get_fields(doctype).filter(df => df.reqd).map(df => df.fieldname);
							return columns;
						}, {});
					} else if (values.select_columns === 'Manually') {
						columns = get_doctype_checkbox_fields().reduce((columns, field) => {
							const options = field.get_checked_options();
							columns[field.df.label] = options;
							return columns;
						}, {});
					}

					return {
						doctype: frm.doc.reference_doctype,
						parent_doctype: frm.doc.reference_doctype,
						select_columns: JSON.stringify(columns),
						with_data: data.with_data ? 'Yes' : 'No',
						all_doctypes: 'Yes',
						from_data_import: 'Yes',
						excel_format: data.file_type === 'Excel' ? 'Yes' : 'No'
					};
				};
				let get_template_url = '/api/method/frappe.core.doctype.data_import.exporter.get_template';
				open_url_post(get_template_url, export_params());
			} else {
				frappe.msgprint(__("Please select the Document Type."));
			}
			dialog.hide();
		},
		primary_action_label: __('Download')
	});

	return dialog;
};
