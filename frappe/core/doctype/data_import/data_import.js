// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import', {

	onload: function(frm) {
		var doctype_options = "";
		for (var i=0, l=frappe.boot.user.can_import.sort().length; i<l; i++) {
			doctype_options = doctype_options + "\n" + frappe.boot.user.can_import[i];
		}
		frm.get_field('reference_doctype').df.options = doctype_options;
	},

	refresh: function(frm) {
		frm.events.add_primary_class(frm);

		if(!frm.doc.freeze_doctype && frm.doc.template == "raw") { 
			frm.events.render_html(frm);
			frm.doc.only_new_records = 1;
		}

		if (frm.doc.template != "raw") {
			frm.doc.only_new_records = 0;
		}

		if(frm.doc.reference_doctype && !frm.doc.import_file) {
			frm.add_custom_button(__("Download template"), function() {
				frappe.set_route('Form', 'Export Template');
			}).addClass("btn-primary");
		}

		if (frm.doc.log_details) {

			frm.events.write_messages(frm);
			if (frm.doc.freeze_doctype) {
				frm.disable_save();
				frm.set_read_only();
			} else {
				frm.enable_save();
			}
		}
	},

	add_primary_class: function(frm) {
		if(frm.class_added) return;
		setTimeout(function() {
			try {
				frm.get_field('import_button').$input.addClass("btn-primary btn-md")
					.removeClass('btn-xs');
				frm.get_field('import_file').$input.addClass("btn-primary btn-md")
					.removeClass('btn-xs');
				frm.class_added = true;
			} catch (err) {
				frm.class_added = false;
			}
		}, 500)
	},

	before_save: function(frm) {
		if (frm.doc.flag_file_preview) {
			var column_map = [];
			$(frm.fields_dict.file_preview.wrapper).find("select.column-map" ).each(function(index) {
				column_map.push($(this).val());
			});
			if(column_map.length != 0){
				frm.doc.selected_columns = JSON.stringify(column_map);
			}
		}
	},

	reference_doctype: function(frm) {
		frm.save();
	},

	render_html: function(frm) {
		var me = this;
		frappe.model.with_doctype(frm.doc.reference_doctype, function() {
			
			if(frm.doc.reference_doctype && frm.doc.preview_data) {
				
				frm.selected_doctype = frappe.get_meta(frm.doc.reference_doctype).fields;
				me.preview_data = JSON.parse(frm.doc.preview_data);
				me.selected_columns = JSON.parse(frm.doc.selected_columns);
				
				$(frm.fields_dict.file_preview.wrapper).empty();
				$(frappe.render_template("file_preview_template", {imported_data: me.preview_data, 
					fields: frm.selected_doctype, column_map: me.selected_columns}))
					.appendTo(frm.fields_dict.file_preview.wrapper);

				me.selected_columns = JSON.parse(frm.doc.selected_columns);
				
				var count = 0;
				$(frm.fields_dict.file_preview.wrapper).find("select.column-map" )
					.each(function(index) {
						$(this).val(me.selected_columns[count])
						if (!me.selected_columns[count]) {
							$(this).parent().addClass("has-error");
						}

						count++;
						$(this).on("change",function() {
							frm.save();
						})
				});
			}
		});
		frm.doc.flag_file_preview = 1;
	},

	import_button: function(frm) {
		frm.save();
				
		if (!frm.doc.import_file) {
			frappe.throw("Attach a file for importing")
		} else {

			frappe.realtime.on("data_import", function(data) {
				if(data.progress) {
					frappe.hide_msgprint(true);
					frappe.show_progress(__("Importing"), data.progress[0],
						data.progress[1]);
				}
			})

			frappe.call({
				method: "file_import",
				doc:frm.doc,
				callback: function(r) {
					
				}
			});
		}
	},

	write_messages: function(frm) {

		msg = JSON.parse(frm.doc.log_details);
		var $log_wrapper = $(cur_frm.fields_dict.import_log.wrapper).empty();
		
		frappe.hide_msgprint(true);
		frappe.hide_progress();

		if (msg.error == false) {

			frappe.msgprint(__("Import Successful"));
			$(frappe.render_template("log_detail_template", {data:msg.messages, error:msg.error}))
				.appendTo($log_wrapper);	
		}

		else {

			frappe.msgprint(__("Import Failed"));
			msg.messages[1] = msg.messages[1].split("\n").join("<br>");
			$(frappe.render_template("log_detail_template", {data:msg.messages, error:msg.error}))
				.appendTo($log_wrapper);
		}
	}
});