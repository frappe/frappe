// Copyright (c) 2020, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("Module Onboarding", {
	refresh: function (frm) {
		nts.boot.developer_mode &&
			frm.set_intro(
				__(
					"Saving this will export this document as well as the steps linked here as json."
				),
				true
			);
		if (!nts.boot.developer_mode) {
			frm.trigger("disable_form");
		}

		frm.add_custom_button(__("Reset"), () => {
			frm.call("reset_progress");
		});
	},

	disable_form: function (frm) {
		frm.set_read_only();
		frm.fields
			.filter((field) => field.has_input)
			.forEach((field) => {
				frm.set_df_property(field.df.fieldname, "read_only", "1");
			});
		frm.disable_save();
	},
});
