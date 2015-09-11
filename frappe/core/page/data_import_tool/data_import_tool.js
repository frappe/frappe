

frappe.DataImportTool = Class.extend({
	init: function(parent) {
		this.page = frappe.ui.make_app_page({
			parent: parent,
			title: __("Data Import Tool"),
			single_column: true
		});
		this.page.add_inner_button(__("Help"), function() {
			frappe.help.show_video("6wiriRKPhmg");
		});
		this.make();
		this.make_upload();
	},
	set_route_options: function() {
		var doctype = null;
		if(frappe.get_route()[1]) {
			doctype = frappe.get_route()[1];
		} else if(frappe.route_options && frappe.route_options.doctype) {
			doctype = frappe.route_options.doctype;
		}

		if(in_list(frappe.boot.user.can_import, doctype)) {
				this.select.val(doctype).change();
		}

		frappe.route_options = null;
	},
	make: function() {
		var me = this;
		frappe.boot.user.can_import = frappe.boot.user.can_import.sort();

		$(frappe.render_template("data_import_main", this)).appendTo(this.page.main);

		this.select = this.page.main.find("select.doctype");
		this.select.on("change", function() {
			me.doctype = $(this).val();
			me.page.main.find(".export-import-section").toggleClass(!!me.doctype);
			if(me.doctype) {
				me.set_btn_links();
				// set button links
			}
		});
	},
	set_btn_links: function() {
		var doctype = encodeURIComponent(this.doctype);
		this.page.main.find(".btn-download-template").attr("href",
			"/api/method/frappe.core.page.data_import_tool.exporter.get_template?"
			+ "doctype=" + doctype
			+ "&parent_doctype=" + doctype
			+ "&with_data=No&all_doctypes=Yes");

		this.page.main.find(".btn-download-data").attr("href",
			"/api/method/frappe.core.page.data_import_tool.exporter.get_template?"
			+ "doctype=" + doctype
			+ "&parent_doctype=" + doctype
			+ "&with_data=Yes&all_doctypes=Yes");
	},
	make_upload: function() {
		var me = this;
		frappe.upload.make({
			parent: this.page.main.find(".upload-area"),
			btn: this.page.main.find(".btn-import"),
			get_params: function() {
				return {
					submit_after_import: me.page.main.find('[name="submit_after_import"]').prop("checked"),
					ignore_encoding_errors: me.page.main.find('[name="ignore_encoding_errors"]').prop("checked"),
					overwrite: !me.page.main.find('[name="always_insert"]').prop("checked")
				}
			},
			args: {
				method: 'frappe.core.page.data_import_tool.importer.upload',
			},
			onerror: function(r) {
				me.onerror(r);
			},
			queued: function() {
				// async, show queued
				msg_dialog.clear();
				msgprint(__("Import Request Queued. This may take a few moments, please be patient."));
			},
			running: function() {
				// update async status as running
				msg_dialog.clear();
				msgprint(__("Importing..."));
				me.write_messages([__("Importing")]);
				me.has_progress = false;
			},
			progress: function(data) {
				// show callback if async
				if(data.progress) {
					frappe.hide_msgprint(true);
					me.has_progress = true;
					frappe.show_progress(__("Importing"), data.progress[0],
						data.progress[1]);
				}
			},
			callback: function(attachment, r) {
				if(r.message.error) {
					me.onerror(r);
				} else {
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

		frappe.realtime.on("data_import_progress", function(data) {
			if(data.progress) {
				frappe.hide_msgprint(true);
				me.has_progress = true;
				frappe.show_progress(__("Importing"), data.progress[0],
					data.progress[1]);
			}
		})

	},
	write_messages: function(data) {
		this.page.main.find(".import-log").removeClass("hide");
		var parent = this.page.main.find(".import-log-messages").empty();

		// TODO render using template!
		for (var i=0, l=data.length; i<l; i++) {
			var v = data[i];
			var $p = $('<p></p>').html(frappe.markdown(v)).appendTo(parent);
			if(v.substr(0,5)=='Error') {
				$p.css('color', 'red');
			} else if(v.substr(0,8)=='Inserted') {
				$p.css('color', 'green');
			} else if(v.substr(0,7)=='Updated') {
				$p.css('color', 'green');
			} else if(v.substr(0,5)=='Valid') {
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

			r.messages.push("Please correct and import again.");

			frappe.show_progress(__("Importing"), 1, 1);

			this.write_messages(r.messages);
		}
	}
});

frappe.pages['data-import-tool'].on_page_load = function(wrapper) {
	frappe.data_import_tool = new frappe.DataImportTool(wrapper);
}

frappe.pages['data-import-tool'].on_page_show = function(wrapper) {
	frappe.data_import_tool && frappe.data_import_tool.set_route_options();
}
