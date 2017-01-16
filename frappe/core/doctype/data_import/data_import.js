// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import', {

	onload: function(frm) {
		var doctype_options = "";
		for (var i=0; i < frappe.boot.user.can_import.sort().length; i++) {
			doctype_options = doctype_options + "\n" + frappe.boot.user.can_import[i];
		}
		frm.get_field('reference_doctype').df.options = doctype_options;
		// setTimeout(function() {
		// 	console.log("Loading");
		// }, 500)
		cur_frm.enable_save();
	},

	refresh: function(frm) {
		var me = this;
		console.log("in the refresh");
		frm.events.add_primary_class(frm);

		if(frm.doc.template == "raw" && frm.doc.freeze_doctype != 1) { 
			console.log("trigeering render function");
			frm.events.render_html(frm);
			frm.doc.only_new_records = 1;
			frm.get_field('only_new_records').df.read_only = 1;
		}
		if (frm.doc.template != "raw") {
			frm.doc.only_new_records = 0;
			frm.get_field('only_new_records').df.read_only = 0;
		}
		if(frm.doc.reference_doctype && frm.doc.template != "raw") {
			frm.add_custom_button(__("Download template"), function() {
				frappe.model.open_mapped_doc({
					method: "frappe.core.doctype.data_import.data_import.route_to_export_template",
					frm: frm
				})
			}).addClass("btn-primary");
		}
		if (frm.doc.freeze_doctype == 1) {
			cur_frm.disable_save();
			console.log("in the frezze doctype after freezing the document");
			if (frm.doc.log_details) {
				console.log("callback received");
				r = JSON.parse(frm.doc.log_details);
				if(r.message.error || r.message.messages.length==0) {
					frm.events.onerror(r);
				} 
				else {
					if(me.has_progress) {
						frappe.show_progress(__("Importing"), 1, 1);
						setTimeout(frappe.hide_progress, 3000);
					}

					r.messages = ["<h5 style='color:green'>" + __("Import Successful!") + "</h5>"].
						concat(r.message.messages);

					// cur_frm.cscript.display_import_log(r.messages);
					frm.events.write_messages(frm, r.messages);
				}
			 } //else {
			// 	console.log("callback not received");
			// 	// $(frm.fields_dict.import_log.wrapper).empty();
			// 	var $log_wrapper = $(cur_frm.fields_dict.import_log.wrapper).empty();
			// 	$('<h2></h2>').html(frappe.markdown("Importing the documents...")).appendTo($log_wrapper);
			// 	// frappe.realtime.on("data_import_progress", function(data) {
			// 	// 	if(data.progress) {
			// 	// 		frappe.hide_msgprint(true);
			// 	// 		me.has_progress = true;
			// 	// 		frappe.show_progress(__("Importing"), data.progress[0],
			// 	// 			data.progress[1]);
			// 	// 	}
			// 	// })
			// }
		}
		// var data = [["#1","Asdfhr sdfbr","Row Inserted","Saved"],["#2","Sgdgrtg ddggrt","Row Updated","Updated"],
		// 		["#3","Rdfgf dfggf","Row Ignored","Ignored"]];
		// frm.events.write_messages(frm,data);
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

	reference_doctype: function(frm) {
		frm.save();
	},

	import_file: function(frm) {
		// frm.save();
	},

	render_html: function(frm) {
		console.log("in render_template");
		var me = this;
		frappe.model.with_doctype(frm.doc.reference_doctype, function() {
			if(frm.doc.reference_doctype && frm.doc.preview_data) {
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
						if (!me.selected_columns[count]) {
							$(this).parent().addClass("has-error");
						}
						count++;
				});
			}
		});
		frm.doc.flag_file_preview = 1;
	},

	import_button: function(frm) {
		var me = this;
		frm.save();
		if (!frm.doc.import_file) {
			frappe.throw("Attach a file for importing")
		}
		else {
			console.log("frappe.call");
			frappe.call({
				method: "frappe.core.doctype.data_import.data_import.insert_into_db",
				args: {
					"reference_doctype": frm.doc.reference_doctype,
					"import_file": frm.doc.import_file,
					"selected_columns": frm.doc.selected_columns,
					"selected_row": frm.doc.selected_row,
					"doc_name": frm.doc.name,
					"only_new_records": frm.doc.only_new_records,
					"only_update": frm.doc.only_update,
					"submit_after_import": frm.doc.submit_after_import,
					"ignore_encoding_errors": frm.doc.ignore_encoding_errors,
					"no_email": frm.doc.no_email,
					"template": frm.doc.template
				},
				callback: function(r) {
					console.log("in the frappe.call callback");
					frm.doc.log_details = JSON.stringify(r);
					frm.events.write_messages(frm, r.messages);
					// frm.save();

				}
			});
			console.log("before the freeze doctype");
			frm.doc.freeze_doctype = 1;
			frm.save();
		}
	},


	write_messages: function(frm, data) {
		console.log("in write messages");
		// $(frm.fields_dict.import_log.wrapper).empty();
		var $log_wrapper = $(cur_frm.fields_dict.import_log.wrapper).empty();
		
		var log_template = '<div class="table-responsive">\
								<table class="table table-bordered table-hover log-details-table">\
									<tr>\
										<th>Row No</th> <th>Row Name</th> <th>Document Name</th> <th>Action Performed</th>\
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
			// $('.log-details-table > tbody:last-child').append('<tr>...</tr><tr>...</tr>');

			// var $p = $('<tr></tr>').html(frappe.markdown(table_row)).appendTo($log_wrapper);

			// if(v.substr(0,5)=='Error') {
			// 	$p.css('color', 'red');
			// } else if(v.substr(0,8)=='Inserted') {
			// 	$p.css('color', 'green');
			// } else if(v.substr(0,7)=='Updated') {
			// 	$p.css('color', 'green');
			// } else if(v.substr(0,5)=='Valid') {
			// 	$p.css('color', '#777');
			// } else if(v.substr(0,7)=='Ignored') {
			// 	$p.css('color', '#777');
			// }
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

			r.messages = ["<h5 style='color:red'>" + __("Import Failed") + "</h5>"]
				.concat(r.messages);

			r.messages.push("Please correct the format of the file and import again.");
			frappe.show_progress(__("Importing"), 1, 1);
			// cur_frm.cscript.display_import_log(r.messages);
			frm.events.write_messages(frm, r.messages);
		}
	}
});

// cur_frm.cscript.display_import_log = function(data) {
// 	cur_frm.log_html = $a(cur_frm.fields_dict['import_log'].wrapper,'p');
// 	var msg = "";
// 	if(data) {
// 		for (var i=0, l=data.length; i<l; i++) {
// 			var v = data[i];
// 			// cur_frm.log_html.innerHTML ='<h4>'+__("Activity Log:")+'</h4>'+msg;
// 			msg += '<h6>'+frappe.markdown(v)+'</h6>';
// 		}
// 	}
// 	cur_frm.log_html.innerHTML = msg;
// }
