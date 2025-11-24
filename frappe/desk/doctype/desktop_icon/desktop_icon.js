// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Desktop Icon", {
	setup: function (frm) {
		frm.set_query("parent_icon", function () {
			return {
				filters: {
					icon_type: ["in", ["Folder", "App"]],
				},
			};
		});
	},
	refresh: function (frm) {
		if (frm.doc.link_to && frm.doc.link_type) {
			frm.add_custom_button(
				__("Workspace Sidebar"),
				function () {
					frappe.new_doc("Workspace Sidebar", {}, (doc) => {
						doc.title = frm.doc.label;
						doc.header_icon = frm.doc.icon;
						let sidebar_item = frappe.model.add_child(doc, "items");
						sidebar_item.label = frm.doc.link_to;
						sidebar_item.link_to = frm.doc.link_to;
						sidebar_item.link_type = frm.doc.link_type;
					});
				},
				__("Create")
			);
		}
	},
});
