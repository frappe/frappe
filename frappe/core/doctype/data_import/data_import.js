// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Import', {

	onload: function(frm) {
		console.log("in the onload");
		var doctype_options = "";
		for (var i=0; i < frappe.boot.user.can_import.sort().length; i++) {
			doctype_options = doctype_options + "\n" + frappe.boot.user.can_import[i];
		}
		frm.get_field('reference_doctype').df.options = doctype_options;
		frm.enable_save();
	},

	refresh: function(frm) {
		var me = this;
		console.log("in the refresh");
		frm.events.add_primary_class(frm);

		// if (frm.doc.import_file) {
		// 	$("button.primary-action :last-child").html("Import");
		// }

		if(!frm.doc.freeze_doctype && frm.doc.template == "raw") { 
			console.log("trigeering render function");
			frm.events.render_html(frm);
			frm.doc.only_new_records = 1;
		}

		if (frm.doc.template != "raw") {
			frm.doc.only_new_records = 0;
		}
		if(frm.doc.reference_doctype && !frm.doc.import_file) {
			frm.add_custom_button(__("Download template"), function() {
				frm.doc.__unsaved = 0;
				frappe.model.open_mapped_doc({
					method: "frappe.core.doctype.data_import.data_import.route_to_export_template",
					frm: frm
				})
			}).addClass("btn-primary");
		}
		if (frm.doc.log_details) {
			console.log("in the log details");
			msg = JSON.parse(frm.doc.log_details);
			frm.events.write_messages(frm, msg);
		}
		if (frm.doc.freeze_doctype) {
			frm.disable_save();
			frm.set_read_only();
		}
		frm.events.setup_dashboard(frm);

	},

	setup_dashboard: function(frm) {

		cur_frm.dashboard.add_progress("Status", [
			{
				title: "Inserted",
				width: "40%",
				progress_class: "progress-bar-success"
			},
			{
				title: "Ignored",
				width: "30%",
				progress_class: "progress-bar-warning"
			},
			{
				title: "Error",
				width: "20%",
				progress_class: "progress-bar-danger"
			}
		]);
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

	save_columns: function(frm) {
		console.log("before saving columns");
		if (frm.doc.flag_file_preview) {
			var column_map = [];
			$(frm.fields_dict.file_preview.wrapper).find("select.column-map" ).each(function(index) {
				column_map.push($(this).val());
			});
			if(column_map.length != 0){
				frm.doc.selected_columns = JSON.stringify(column_map);
			}
			// frm.save();
		}
	},

	reference_doctype: function(frm) {
		frm.save();
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
						$(this).on("change",function() {
							frm.events.save_columns(frm);

						})
				});
			}
		});
		frm.doc.flag_file_preview = 1;
	},

	import_button: function(frm) {
		import_button = frm.get_field('import_button');
		frm.save();
		var me = this;
		if (!frm.doc.import_file) {
			frappe.throw("Attach a file for importing")
		} else {
			console.log(" before frappe.call");

			// $(import_button.input).set_working();

			frappe.call({
				method: "runserverobj",
				args: {'docs':frm.doc, 'method': 'insert_into_db'},
				// btn: import_button.$input,
				callback: function(r) {
					console.log("in the frappe.call callback");
					frm.doc.log_details = JSON.stringify(r.message);
					// console.log(r.message);
					
					// frm.read_only = 1;
					// frm.events.write_messages(frm, r.messages);
					// frm.save();
					// if(!r.exc) {
					// 	if(onrefresh) {
					// 		onrefresh(r);
					// 	}

					// 	me.refresh_fields();
					// }
				}
			});	
			frm.doc.freeze_doctype = 1;
			console.log("before freeze doctype");
			frappe.realtime.on("data_import_p", function(data) {
				console.log("in frappe realtime");
				console.log(data)
				if(data.progress) {
					frappe.hide_msgprint(true);
					me.has_progress = true;
					frappe.show_progress(__("Importing"), data.progress[0],
						data.progress[1]);
				}
			})

		}
	},


	write_messages: function(frm, data) {
		console.log("in write messages");
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