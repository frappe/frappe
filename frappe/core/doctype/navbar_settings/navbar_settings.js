// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Navbar Settings", {
<<<<<<< HEAD
	// refresh: function(frm) {
	// }
=======
	after_save: function (frm) {
		frappe.ui.toolbar.clear_cache();
	},
>>>>>>> 8eb8c64fbd (fix(Navbar Settings): reload page after save (#26274))
});
