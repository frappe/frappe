// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import', {

	onload: function(frm) {
		var doctype_options = "";
		for (var i=0, l=frappe.boot.user.can_import.sort().length; i<l; i++) {
			doctype_options = doctype_options + "\n" + frappe.boot.user.can_import[i];
		}
		frm.get_field('reference_doctype').df.options = doctype_options;
		frm.data_progress = 0;
	},

	refresh: function(frm) {
		var me = this;
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
			msg = JSON.parse(frm.doc.log_details);
			console.log(msg);
			frm.events.write_messages(frm, msg);
		}

		if (frm.doc.freeze_doctype) {
			frm.disable_save();
			frm.set_read_only();
		} else {
			frm.enable_save();
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
		var me = this;
				
		if (!frm.doc.import_file) {
			frappe.throw("Attach a file for importing")
		} else {

			console.log("before publishing");
			frappe.realtime.on("data_import", function(data) {
				console.log(data);
				if(data.progress) {
					frappe.hide_msgprint(true);
					frappe.show_progress(__("Importing"), data.progress[0],
						data.progress[1]);
				}
			})

			frappe.call({
				method: "insert_into_db",
				doc:frm.doc,
				callback: function(r) {
					console.log("in callback");
					frm.reload_doc();
				}
			});
		}
	},

	write_messages: function(frm, data) {
		var $log_wrapper = $(cur_frm.fields_dict.import_log.wrapper).empty();
		
		var log_template = '<div class="table-responsive">\
								<table class="table table-bordered table-hover log-details-table">\
									<tr>\
										<th>Row No</th> <th>Row Name</th> <th>Document Name</th> <th>Action</th>\
									</tr>\
								</table>\
							</div>';

		$('<div><div>').html(frappe.markdown(log_template)).appendTo($log_wrapper);

		// TODO render using template!
		for (var i=0, l=data.length; i<l; i++) {
			$("table.log-details-table tbody:last-child" ).append("<tr></tr>")
			var v = data[i];
			// var table_row = '';
			for (var j=0; j<data[i].length; j++) {
				// table_row = table_row + '<td>'+data[i][j]+'</td>';	
				$("table.log-details-table tr:last-child" ).append("<td>"+data[i][j]+"</td>")

			}
		}
	}
});