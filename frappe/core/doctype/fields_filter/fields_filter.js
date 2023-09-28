// Copyright (c) 2023, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Fields Filter", {
	refresh(frm) {},

	edit_filter: (frm) => {
		let doctype = frm.doc.reference_doctype;
		if (!doctype) {
			frappe.throw(__("Please select a Doctype first"));
		}
		make_dialog(frm);
		make_filter_area(frm);
		frappe.model.with_doctype(doctype, () => {
			this.dialog.show();
		});
	},
});

const make_dialog = (frm) => {
	this.dialog = new frappe.ui.Dialog({
		title: __("Select Fields"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "filter_area",
			},
		],
		primary_action: () => {
			console.log("hee");
		},
		primary_action_label: __("Done"),
	});
};

const make_filter_area = (frm) => {
	this.filter_group = new frappe.ui.FilterGroup({
		parent: this.dialog.get_field("filter_area").$wrapper,
		doctype: frm.doc.reference_doctype,
		only_link_fields: true,
		on_change: () => {
			console.log(this.filter_group.get_filters());
			// from the filter group I want to to dislpay only those fields which have fieldtype as Link
		},
	});
	console.log(frm);
};
