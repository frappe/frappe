// Copyright (c) 2017, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("Print Style", {
	refresh: function (frm) {
		frm.add_custom_button(__("Print Settings"), () => {
			nts.set_route("Form", "Print Settings");
		});
	},
});
