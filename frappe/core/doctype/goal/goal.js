// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Goal', {

	// Make fields mandatory

	refresh: function(frm) {
	},

	source: function(frm) {
		if(frm.doc.source) {
			return frm.call({
				method: "fetch_fields",
				doc: frm.doc,
				freeze: true,
				callback: function(r) {
					frm.fields_dict.source_filter.df.options = "\n" + r.message.source_filter.join("\n");
					frm.refresh_field("source_filter");
					frm.fields_dict.based_on.df.options = "\n" + r.message.based_on.join("\n");
					frm.refresh_field("based_on");

					// Also set type of field for plain target
					// User can also set percent target, different default field for that
				}
			});
		}
	},

});
