// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import', {

	onload: function(frm) {
		var doctype_options = "";
		for (var i=0; i < frappe.boot.user.can_import.sort().length; i++) {
			doctype_options = doctype_options + "\n" + frappe.boot.user.can_import[i];
		}
		frm.get_field('reference_doctype').df.options = doctype_options;
		if (frm.doc.flag_file_preview == 1) {
			console.log(frm.doc.flag_file_preview);
		}
	},

	refresh: function(frm) {
		if (frm.doc.import_file) {
			frm.get_field('import_button').$input.addClass("btn-primary btn-md")
				.removeClass('btn-xs');
		}
		if(frm.doc.preview_data && frm.doc.docstatus!=1) { 
			frm.events.render_html(frm);
			
		}
	},

	before_save: function(frm) {
		if (frm.doc.flag_file_preview && frm.doc.preview_data) {
			var column_map = [];
			$(frm.fields_dict.file_preview.wrapper).find("select.column-map" ).each(function(index) {
				column_map.push($(this).val());
			});
			if(column_map.length != 0){
				frm.doc.selected_columns = JSON.stringify(column_map);
			}
		}
	},

	render_html: function(frm) {
		var me = this;
		frappe.model.with_doctype(frm.doc.reference_doctype, function() {
			if(frm.doc.reference_doctype) {
				frm.selected_doctype = frappe.get_meta(frm.doc.reference_doctype).fields;

				$(frm.fields_dict.file_preview.wrapper).empty();
				me.preview_data = JSON.parse(frm.doc.preview_data);
				me.selected_columns = JSON.parse(frm.doc.selected_columns);
				$(frappe.render_template("file_preview", {imported_data: me.preview_data, 
					fields: frm.selected_doctype, column_map: me.selected_columns}))
					.appendTo(frm.fields_dict.file_preview.wrapper);

				me.selected_columns = JSON.parse(frm.doc.selected_columns);
				var count = 0;
				$(frm.fields_dict.file_preview.wrapper).find("select.column-map" )
					.each(function(index) {
						$(this).val(me.selected_columns[count]) 
						count++;
				});
			}
		});
		frm.doc.flag_file_preview = 1;
	},

	import_button: function(frm) {
		var me = this;
		frm.save();
		if (!frm.doc.idmport_file) {
			frappe.throw("Attach a file for importing")
		}
		if (frm.doc.file_format == '.xlsx') {
			frappe.call({
				method: "frappe.core.doctype.data_import.data_import.insert_into_db",
				args: {
					"reference_doctype": frm.doc.reference_doctype,
					"import_file": frm.doc.import_file,
					"selected_columns": frm.doc.selected_columns,
					"selected_row": frm.doc.selected_row,
				},
				callback: function(r) {
					frm.doc.freeze_doctype = 1;
					frm.save();
				}
			});
		}
		if (frm.doc.file_format == '.csv') {
			frappe.call({
				method: "frappe.core.doctype.data_import.data_import.upload",
				args: {
					"doc_name": frm.doc.name,
					"overwrite": frm.doc.only_new_records,
					"update_only": frm.doc.onyl_update,
					"submit_after_import": frm.doc.submit_after_import,
					"ignore_encoding_errors": frm.doc.ignore_encoding_errors,
					"no_email": frm.doc.no_email,
				},
				callback: function(r) {
					frm.doc.freeze_doctype = 1;

					if(r.message.error || r.message.messages.length==0) {
						me.onerror(r);
					} 
					else {
						if(me.has_progress) {
							frappe.show_progress(__("Importing"), 1, 1);
							setTimeout(frappe.hide_progress, 1000);
						}

						r.messages = ["<h5 style='color:green'>" + __("Import Successful!") + "</h5>"].
							concat(r.message.messages)

						me.write_messages(r.messages);
					}
				}
			});
		}
	},
	write_messages: function(data) {

		var $log_wrapper = $(cur_frm.fields_dict.import_log.wrapper).empty();		
		// TODO render using template!
		for (var i=0, l=data.length; i<l; i++) {
			var v = data[i];
			var $p = $('<p></p>').html(frappe.markdown(v)).appendTo($log_wrapper);
			if(v.substr(0,5)=='Error') {
				$p.css('color', 'red');
			} else if(v.substr(0,8)=='Inserted') {
				$p.css('color', 'green');
			} else if(v.substr(0,7)=='Updated') {
				$p.css('color', 'green');
			} else if(v.substr(0,5)=='Valid') {
				$p.css('color', '#777');
			} else if(v.substr(0,7)=='Ignored') {
				$p.css('color', '#777');
			}
		}
	},

	onerror: function(r) {
		if(r.message) {
			// bad design: moves r.messages to r.message.messages
			r.messages = $.map(r.message.messages, function(v) {
				var msg = v.replace("Inserted", "Valid")
					.replace("Updated", "Valid").split("<");
				if (msg.length > 1) {
					v = msg[0] + (msg[1].split(">").slice(-1)[0]);
				} else {
					v = msg[0];
				}
				return v;
			});

			r.messages = ["<h4 style='color:red'>" + __("Import Failed") + "</h4>"]
				.concat(r.messages);

			r.messages.push("Please correct the format of the file and import again.");
			frappe.show_progress(__("Importing"), 1, 1);
			this.write_messages(r.messages);
		}
	}
});