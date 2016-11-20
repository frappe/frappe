
frappe.DataTransferWizard = Class.extend({
	init: function(parent) {
		var me =this;
		this.page = frappe.ui.make_app_page({
			parent: parent,
			title: __("Data Transfer Wizard"),
			single_column: true
		});
		this.page.add_menu_item(__("Export"), function() {
			me.show_export();
		});
		this.page.add_menu_item(__("Import"), function() {	
			me.show_import();
		});
		this.make();
		this.make_upload();
	},
	
	make: function() {
		var me = this;
		frappe.boot.user.can_import = frappe.boot.user.can_import.sort();
		$(frappe.render_template("data_transfer_wizard", this)).appendTo(this.page.main);
		this.select = this.page.main.find("select.doctype");
		this.select.on("change", function() {
			me.doctype = $(this).val();
			console.log(me.doctype);
		});			
		
	},
	make_upload: function() {
		var me = this;
		frappe.upload.make({
			parent: this.page.main.find(".upload-area"),
			btn: this.page.main.find(".btn-import"),
			args: {
				method: 'frappe.core.page.data_transfer_wizard.import_tool.upload',
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
				if(r.message.error || r.message.messages.length==0) {
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
			},
			is_private: true
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


frappe.pages['data-transfer-wizard'].on_page_load = function(wrapper) {
	frappe.data_transfer_wizard = new frappe.DataTransferWizard(wrapper);
}


frappe.pages['data-transfer-wizard'].on_page_show = function(wrapper) {
	frappe.data_transfer_wizard; //&& frappe.data_transfer_wizard.set_route_options();
}