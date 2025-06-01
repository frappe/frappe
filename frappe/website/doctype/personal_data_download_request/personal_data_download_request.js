// Copyright (c) 2019, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("Personal Data Download Request", {
	onload: function (frm) {
		if (frm.is_new()) {
			frm.doc.user = nts.session.user;
		}
	},
});
