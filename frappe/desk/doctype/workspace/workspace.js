// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Workspace", {
	setup: function () {
		frappe.meta.get_field("Workspace Link", "only_for").no_default = true;
	},

	refresh: function (frm) {
		frm.enable_save();
		frm.trigger("add_to_desktop");
		let url = `/desk/${
			frm.doc.public
				? frappe.router.slug(frm.doc.title)
				: "private/" + frappe.router.slug(frm.doc.title)
		}`;
		frm.sidebar
			.add_user_action(__("Go to Workspace"))
			.attr("href", url)
			.attr("target", "_blank");

		frm.layout.message.empty();
		let message = __("Please click Edit on the Workspace for best results");

		if (
			(frm.doc.for_user && frm.doc.for_user !== frappe.session.user) ||
			(frm.doc.public && !frappe.user.has_role("Workspace Manager"))
		) {
			frm.trigger("disable_form");

			if (frm.doc.public) {
				message = __("Only Workspace Manager can edit public workspaces");
			} else {
				message = __(
					"We do not allow editing of this document. Simply click the Edit button on the workspace page to make your workspace editable and customize it as you wish"
				);
			}
		}

		if (frappe.boot.developer_mode) {
			frm.set_df_property("module", "read_only", 0);
		}

		frm.layout.show_message(message);
	},

	add_to_desktop: function (frm) {
		if (frappe.app.sidebar.get_workspace_sidebars(frm.doc.title).length === 0) {
			frm.add_custom_button(__("Add to Desktop"), function () {
				frappe.call({
					method: "frappe.desk.doctype.desktop_icon.desktop_icon.add_workspace_to_desktop",
					args: {
						workspace: frm.doc.name,
					},
					callback: function (r) {
						if (r.message.status) {
							frappe.toast({
								message: __("Workspace added to desktop"),
								indicator: "green",
							});
						}
					},
				});
			});
		}
	},
	disable_form: function (frm) {
		frm.fields
			.filter((field) => field.has_input)
			.forEach((field) => {
				frm.set_df_property(field.df.fieldname, "read_only", "1");
			});
		frm.disable_save();
	},
});
