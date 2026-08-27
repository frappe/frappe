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
	// The "Create > Workspace Sidebar" button that used to live here is gone: that doctype is
	// now an inert archive the sidebar migration reads as its source, so a form minting fresh
	// rows on it would make the conversion's input a moving target. An icon's `link_to` names
	// a workspace, and the grid routes it through the module-keyed sidebar payload.
});
