// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Print Settings", "print_style", function (frm) {
	frm.get_field("print_style_preview").html('<img src="/assets/frappe/images/help/print-style-' +
		frm.doc.print_style.toLowerCase() + '.png" class="img-responsive">');
});

frappe.ui.form.on("Print Settings", "onload", function (frm) {
	frm.script_manager.trigger("print_style");
});
