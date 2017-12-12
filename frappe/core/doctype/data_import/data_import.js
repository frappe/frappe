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
					let progress_bar = $(cur_frm.dashboard.progress_area).find(".progress-bar");
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
		if (frm.doc.import_status) {
			frm.dashboard.clear_headline();
			frm.dashboard.add_comment(frm.doc.import_status);
		}
		if (frm.doc.import_status==="In Progress") {
			frm.dashboard.add_progress("Data Import Progress", "0");
			frm.set_read_only();
		}

		var download_dialog = new frappe.ui.Dialog({
			title: __('Download Template'),
			fields: [
				{
					"label": "Select Columns",
					"fieldname": "select_columns",
					"fieldtype": "Select",
					"options": "All\nMandatory\nManually",
					"reqd": 1,
					"onchange": function() {
						frm.$dialog_wrapper = $(download_dialog.fields_dict.doctype_columns.wrapper).empty();
						frappe.model.with_doctype(frm.doc.reference_doctype, function() {
							if(frm.doc.reference_doctype) {
								// render select columns
								var parent_doctype = frappe.get_doc('DocType', frm.doc.reference_doctype);
								parent_doctype["reqd"] = true;
								var doctype_list = [parent_doctype];
								frappe.meta.get_table_fields(frm.doc.reference_doctype).forEach(function(df) {
									var d = frappe.get_doc('DocType', df.options);
									d["reqd"]=df.reqd;
									doctype_list.push(d);
								});
								$(frappe.render_template("export_template", {doctype_list: doctype_list}))
									.appendTo(frm.$dialog_wrapper.empty());
							}
						});
						if (this.value === "All") {
							frm.$dialog_wrapper.addClass("hidden");
							frm.$dialog_wrapper.find('.select-column-check').prop('checked', true);
						} else if (this.value === "Mandatory") {
							frm.$dialog_wrapper.addClass("hidden");
							frm.$dialog_wrapper.find('.select-column-check').prop('checked', false);
							frm.$dialog_wrapper.find('.select-column-check[data-reqd="1"]').prop('checked', true);
						} else if (this.value === "Manually") {
							frm.$dialog_wrapper.removeClass("hidden");
						}
					}
				},
				{
					"label": "File Type",
					"fieldname": "file_type",
					"fieldtype": "Select",
					"options": "Excel\nCSV",
					"default": "Excel"
				},
				{
					"label": "Download with Data",
					"fieldname": "with_data",
					"fieldtype": "Check"
				},
				{
					"label": "",
					"fieldname": "doctype_columns",
					"fieldtype": "HTML"
				}
			],
			primary_action: function() {
				var data = download_dialog.get_values();
				if (frm.doc.reference_doctype) {
					var export_params = () => {
						let columns = {};
						frm.$dialog_wrapper.find('.select-column-check:checked').each(function() {
							let _doctype = $(this).attr('data-doctype');
							let _fieldname = $(this).attr('data-fieldname');
							if(!columns[_doctype]) {
								columns[_doctype] = [];
							}
							columns[_doctype].push(_fieldname);
						});
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
				download_dialog.hide();
			},
			primary_action_label: __('Download')
		});
		frm.add_custom_button(__("Help"), function() {
			frappe.help.show_video("6wiriRKPhmg");
		});

		if(frm.doc.reference_doctype && frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Download template"), function() {
				download_dialog.show();
			});
		}

		if (frm.doc.reference_doctype && frm.doc.import_file && frm.doc.total_rows  && frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Start Import"), function() {
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

	import_file: function(frm) {
		frm.save();
	},

	only_new_records: function(frm) {
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
		$(frappe.render_template("log_details", {data: msg.messages, skip_errors: frm.doc.skip_errors,
			show_only_errors: frm.doc.show_only_errors})).appendTo($log_wrapper);
	}
});