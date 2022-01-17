// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import Legacy', {
	onload: function(frm) {
		if (frm.doc.__islocal) {
			frm.set_value("action", "");
		}

		frappe.call({
			method: "frappe.core.doctype.data_import_legacy.data_import_legacy.get_importable_doctypes",
			callback: function (r) {
				let importable_doctypes = r.message;
				frm.set_query("reference_doctype", function () {
					return {
						"filters": {
							"issingle": 0,
							"istable": 0,
							"name": ['in', importable_doctypes]
						}
					};
				});
			}
		}),

		// should never check public
		frm.fields_dict["import_file"].df.is_private = 1;

		frappe.realtime.on("data_import_progress", function(data) {
			if (data.data_import === frm.doc.name) {
				if (data.reload && data.reload === true) {
					frm.reload_doc();
				}
				if (data.progress) {
					let progress_bar = $(frm.dashboard.progress_area.body).find(".progress-bar");
					if (progress_bar) {
						$(progress_bar).removeClass("progress-bar-danger").addClass("progress-bar-success progress-bar-striped");
						$(progress_bar).css("width", data.progress + "%");
					}
				}
			}
		});
	},

	reference_doctype: function(frm){
		if (frm.doc.reference_doctype) {
			frappe.model.with_doctype(frm.doc.reference_doctype);
		}
	},

	refresh: function(frm) {
		frm.disable_save();
		frm.dashboard.clear_headline();
		if (frm.doc.reference_doctype && !frm.doc.import_file) {
			frm.page.set_indicator(__('Attach file'), 'orange');
		} else {
			if (frm.doc.import_status) {
				const listview_settings = frappe.listview_settings['Data Import Legacy'];
				const indicator = listview_settings.get_indicator(frm.doc);

				frm.page.set_indicator(indicator[0], indicator[1]);

				if (frm.doc.import_status === "In Progress") {
					frm.dashboard.add_progress("Data Import Progress", "0");
					frm.set_read_only();
					frm.refresh_fields();
				}
			}
		}

		if (frm.doc.reference_doctype) {
			frappe.model.with_doctype(frm.doc.reference_doctype);
		}

		if(frm.doc.action == "Insert new records" || frm.doc.action == "Update records") {
			frm.set_df_property("action", "read_only", 1);
		}

		frm.add_custom_button(__("Help"), function() {
			frappe.help.show_video("6wiriRKPhmg");
		});

		if (frm.doc.reference_doctype && frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Download template"), function() {
				frappe.data_import.download_dialog(frm).show();
			});
		}
		if (frm.doc.log_details) {
			frm.events.create_log_table(frm);
		} else {
			$(frm.fields_dict.import_log.wrapper).empty();
		}

		const data_import_link = "<a href='/app/data-import'>Data Import</a>";
		frm.dashboard.add_comment(__("This data importer utility is deprecated and will be removed, use {} instead.", [data_import_link]), "yellow", true);
	},

	action: function(frm) {
		if(!frm.doc.action) return;
		if(!frm.doc.reference_doctype) {
			frappe.msgprint(__("Please select document type first."));
			frm.set_value("action", "");
			return;
		}

		if(frm.doc.action == "Insert new records") {
			frm.doc.insert_new = 1;
		} else if (frm.doc.action == "Update records"){
			frm.doc.overwrite = 1;
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
		$(frappe.render_template("log_details", {
			data: msg.messages,
			import_status: frm.doc.import_status,
			show_only_errors: frm.doc.show_only_errors,
		})).appendTo($log_wrapper);
	}
});

frappe.provide('frappe.data_import');
frappe.data_import.download_dialog = function(frm) {
	var dialog;
	const filter_fields = df => frappe.model.is_value_type(df) && !df.hidden;
	const get_fields = dt => frappe.meta.get_docfields(dt).filter(filter_fields);

	const get_doctype_checkbox_fields = () => {
		return dialog.fields.filter(df => df.fieldname.endsWith('_fields'))
			.map(df => dialog.fields_dict[df.fieldname]);
	};

	const doctype_fields = get_fields(frm.doc.reference_doctype)
		.map(df => {
			let reqd = (df.reqd || df.fieldname == 'naming_series') ? 1 : 0;
			return {
				label: df.label,
				reqd: reqd,
				danger: reqd,
				value: df.fieldname,
				checked: 1
			};
		});

	let fields = [
		{
			"label": __("Select Columns"),
			"fieldname": "select_columns",
			"fieldtype": "Select",
			"options": "All\nMandatory\nManually",
			"reqd": 1,
			"onchange": function() {
				const fields = get_doctype_checkbox_fields();
				fields.map(f => f.toggle(true));
				if(this.value == 'Mandatory' || this.value == 'Manually') {
					checkbox_toggle(true);
					fields.map(multicheck_field => {
						multicheck_field.options.map(option => {
							if(!option.reqd) return;
							$(multicheck_field.$wrapper).find(`:checkbox[data-unit="${option.value}"]`)
								.prop('checked', false)
								.trigger('click');
						});
					});
				} else if(this.value == 'All'){
					$(dialog.body).find(`[data-fieldtype="MultiCheck"] :checkbox`)
						.prop('disabled', true);
				}
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
			"fieldtype": "Check",
			"hidden": !frm.doc.overwrite,
			"default": 1
		},
		{
			"label": __("Select All"),
			"fieldname": "select_all",
			"fieldtype": "Button",
			"depends_on": "eval:doc.select_columns=='Manually'",
			click: function() {
				checkbox_toggle();
			}
		},
		{
			"label": __("Unselect All"),
			"fieldname": "unselect_all",
			"fieldtype": "Button",
			"depends_on": "eval:doc.select_columns=='Manually'",
			click: function() {
				checkbox_toggle(true);
			}
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
						reqd: df.reqd ? 1 : 0,
						value: df.fieldname,
						checked: 1,
						danger: df.reqd
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
					if(values.select_columns) {
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
						with_data: frm.doc.overwrite && data.with_data,
						all_doctypes: true,
						file_type: data.file_type,
						template: true
					};
				};
				let get_template_url = '/api/method/frappe.core.doctype.data_export.exporter.export_data';
				open_url_post(get_template_url, export_params());
			} else {
				frappe.msgprint(__("Please select the Document Type."));
			}
			dialog.hide();
		},
		primary_action_label: __('Download')
	});

	$(dialog.body).find('div[data-fieldname="select_all"], div[data-fieldname="unselect_all"]')
		.wrapAll('<div class="inline-buttons" />');
	const button_container = $(dialog.body).find('.inline-buttons');
	button_container.addClass('flex');
	$(button_container).find('.frappe-control').map((index, button) => {
		$(button).css({"margin-right": "1em"});
	});

	function checkbox_toggle(checked=false) {
		$(dialog.body).find('[data-fieldtype="MultiCheck"]').map((index, element) => {
			$(element).find(`:checkbox`).prop("checked", checked).trigger('click');
		});
	}

	return dialog;
};
