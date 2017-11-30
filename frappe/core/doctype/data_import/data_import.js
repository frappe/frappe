// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import', {	
	setup: function(frm) {
		var doctype_options = "";
		for (var i=0, l=frappe.boot.user.can_import.sort().length; i<l; i++) {
			doctype_options = doctype_options + "\n" + frappe.boot.user.can_import[i];
		}
		frm.get_field('reference_doctype').df.options = doctype_options;
	},
	
	onload: function(frm) {
		frm.disable_save();
		frappe.realtime.on("data_import", function(data) {
			if(data.progress) {
				frappe.hide_msgprint(true);
				frappe.show_progress(__("Importing"), data.progress[0],
				data.progress[1]);
			}
		});		
	},
				
	refresh: function(frm) {
		var download_dialog = new frappe.ui.Dialog({
			title: __('Download Template'),
			fields: [
				{
					"label": "Document Fields",
					"fieldname": "document_fields",
					"fieldtype": "Select",
					"options": "Select All\nSelect Mandatory\nSelect Manually",
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
						if (this.value === "Select All") {
							frm.$dialog_wrapper.addClass("hidden");
							frm.$dialog_wrapper.find('.select-column-check').prop('checked', true);
						} else if (this.value === "Select Mandatory") {
							frm.$dialog_wrapper.addClass("hidden");
							frm.$dialog_wrapper.find('.select-column-check').prop('checked', false);
							frm.$dialog_wrapper.find('.select-column-check[data-reqd="1"]').prop('checked', true);
						} else if (this.value === "Select Manually") {
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
					var export_params = ()  => {
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
						}
					};
					let get_template_url = '/api/method/frappe.core.doctype.data_import.exporter.get_template';
					open_url_post(get_template_url, export_params());
				} else {
					frappe.msgprint(__("Please select the Document Type."))
				}			
				download_dialog.hide();
			},
			primary_action_label: __('Download')
		});
		frm.add_custom_button(__("Help"), function() {
			frappe.help.show_video("6wiriRKPhmg");
		});

		if(frm.doc.reference_doctype) {
			frm.add_custom_button(__("Download template"), function() {
				download_dialog.show();
			});
		}
		
		if (frm.doc.reference_doctype && frm.doc.import_file) {
			frm.add_custom_button(__("Validate Template"), function() {
				frm.events.data_import(frm, true);
			});
			frm.add_custom_button(__("Start Import"), function() {
				frm.events.data_import(frm, false);
			}).addClass('btn btn-primary');
		}
		
		if (frm.doc.log_details) {
			frm.events.write_messages(frm);
			// if (frm.doc.import_status == "Success") {
			// 	frm.disable_save();
			// } else {
			// 	frm.enable_save();
			// }
		}
	},
	
	reference_doctype: function(frm) {
		frm.save();
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

	data_import: function(frm, validate) {
		frappe.call({
			method: "import_data",
			doc: frm.doc,
			args: {
				validate: validate
			},
			callback: function(r) {
				frm.refresh();
			}
		});
	},

	write_messages: function(frm) {
		msg = JSON.parse(frm.doc.log_details);
		var $log_wrapper = $(frm.fields_dict.import_log.wrapper).empty();
		
		frappe.hide_msgprint(true);
		frappe.hide_progress();

		if (msg.error == false) {
			$(frappe.render_template("log_detail_template", {data:msg.messages}))
				.appendTo($log_wrapper);	
		}
		else {
			$(frappe.render_template("log_detail_template", {data:msg.messages}))
				.appendTo($log_wrapper);
		}
	}
});
