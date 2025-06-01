// Copyright (c) 2019, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("Milestone Tracker", {
	refresh: function (frm) {
		frm.trigger("update_options");
	},
	document_type: function (frm) {
		frm.trigger("update_options");
	},
	update_options: function (frm) {
		// update select options for `track_field`
		let doctype = frm.doc.document_type;
		let track_fields = [];

		if (doctype) {
			nts.model.with_doctype(doctype, () => {
				// get all date and datetime fields
				nts.get_meta(doctype).fields.map((df) => {
					if (["Link", "Select"].includes(df.fieldtype)) {
						track_fields.push({ label: df.label, value: df.fieldname });
					}
				});
				frm.set_df_property("track_field", "options", track_fields);
			});
		} else {
			// update select options
			frm.set_df_property("track_field", "options", []);
		}
	},
});
