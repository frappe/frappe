// Copyright (c) 2019, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("Google Settings", {
	refresh: function (frm) {
		frm.dashboard.set_headline(
			__("For more information, {0}.", [
				`<a href='https://productionmanager.com/docs/user/manual/en/productionmanager_integration/google_settings'>${__(
					"Click here"
				)}</a>`,
			])
		);
	},
});
