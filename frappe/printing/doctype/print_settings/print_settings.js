// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Print Settings', {
	print_style: function(frm) {
		frappe.db.get_value('Print Style', frm.doc.print_style, 'preview').then((r) => {
			if(r.message.preview) {
				frm.get_field("print_style_preview").$wrapper.html(
					`<img src="${r.message.preview}" class="img-responsive">`);
			} else {
				frm.get_field("print_style_preview").$wrapper.html(
					`<p style="margin: 60px 0px" class="text-center text-muted">${__("No Preview")}</p>`);
			}
		});
	},
	onload: function(frm) {
		frm.script_manager.trigger("print_style");
	},
	server_ip: function(frm) {
		frm.trigger("connect_print_server");
	},
	port:function(frm) {
		frm.trigger("connect_print_server");
	},
	connect_print_server:function(frm) {
		if(frm.doc.server_ip && frm.doc.port){
			frappe.call({
				"doc": frm.doc,
				"method": "get_printers",
				"args": {
					ip: frm.doc.server_ip,
					port: frm.doc.port
				},
				callback: function(data) {
					frm.set_df_property('printer_name', 'options', [""].concat(data.message));
				},
				error: (data) => frm.set_value("enable_print_server", 0)
			});
		}
	}
});
