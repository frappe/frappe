// Copyright (c) 2023, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Custom HTML Block", {
	refresh(frm) {
		let wrapper = frm.fields_dict["preview"].wrapper;
		wrapper.classList.add("mb-3");

		frappe.create_shadow_element(wrapper, frm.doc.html, frm.doc.style, frm.doc.script);
	},
});
