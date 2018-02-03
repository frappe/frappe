// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on("Website Slideshow", {
	refresh: (frm) => {
		let intro = frm.doc.__islocal?
			"First set the name and save the record.": "Attach files / urls and add in table.";
		frm.set_intro(intro);
	}
})