// Copyright (c) 2020, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("Navbar Settings", {
	after_save: function (frm) {
		nts.ui.toolbar.clear_cache();
	},
});
