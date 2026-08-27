// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

// An archive of the previous navigation: read-only, and no longer wired to anything. The
// "Migrate to Workspace" button is gone along with the column it wrote to. The conversion now
// reads these rows straight into module sidebars, from `bench migrate`.
frappe.ui.form.on("Workspace Sidebar", {
	refresh(frm) {
		frm.set_intro(
			__(
				"This is an archive of the previous navigation. Customize the module's sidebar instead."
			)
		);
		frm.set_read_only();
		frm.disable_save();
	},
});
