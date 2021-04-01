// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Workspace', {
	setup: function() {
		frappe.meta.get_field('Workspace Link', 'only_for').no_default = true;
	},

	refresh: function(frm) {
		frm.enable_save();
		frm.get_field("is_standard").toggle(frappe.boot.developer_mode);
		frm.get_field("developer_mode_only").toggle(frappe.boot.developer_mode);

		if (frm.doc.for_user) {
			frm.set_df_property("extends", "read_only", true);
		}

		if (frm.doc.for_user || (frm.doc.is_standard && !frappe.boot.developer_mode)) {
			frm.trigger('disable_form');
		}
	},

	disable_form: function(frm) {
		frm.fields
			.filter(field => field.has_input)
			.forEach(field => {
				frm.set_df_property(field.df.fieldname, "read_only", "1");
			});
		frm.disable_save();
	}
});