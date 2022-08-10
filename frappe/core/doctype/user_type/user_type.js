// Copyright (c) 2021, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("User Type", {
	refresh: function (frm) {
		if (frm.is_new() && !frappe.boot.developer_mode) frm.set_value("is_standard", 1);

		frm.set_query("document_type", "user_doctypes", function () {
			return {
				filters: {
					istable: 0,
				},
			};
		});

		frm.set_query("document_type", "select_doctypes", function () {
			return {
				filters: {
					istable: 0,
				},
			};
		});

		frm.set_query("document_type", "custom_select_doctypes", function () {
			return {
				filters: {
					istable: 0,
				},
			};
		});

		frm.set_query("role", function () {
			return {
				filters: {
					is_custom: 1,
					disabled: 0,
					desk_access: 1,
				},
			};
		});

		frm.set_query("apply_user_permission_on", function () {
			return {
				query: "frappe.core.doctype.user_type.user_type.get_user_linked_doctypes",
			};
		});
	},

	onload: function (frm) {
		frm.trigger("get_user_id_fields");
	},

	apply_user_permission_on: function (frm) {
		frm.set_value("user_id_field", "");
		frm.trigger("get_user_id_fields");
	},

	get_user_id_fields: function (frm) {
		if (frm.doc.apply_user_permission_on) {
			frappe.call({
				method: "frappe.core.doctype.user_type.user_type.get_user_id",
				args: {
					parent: frm.doc.apply_user_permission_on,
				},
				callback: function (r) {
					set_field_options("user_id_field", [""].concat(r.message));
				},
			});
		}
	},
});
