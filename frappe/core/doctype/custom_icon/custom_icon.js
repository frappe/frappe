// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Custom Icon", {
	refresh(frm) {
		frm.trigger("warn_if_shadowed");
	},

	icon_name(frm) {
		frm.trigger("warn_if_shadowed");
	},

	warn_if_shadowed(frm) {
		// Two symbols with one id resolve to whichever the sprite loaded first, so the
		// icon would silently keep rendering as the bundled one.
		frm.dashboard.clear_headline();
		let icon_name = frm.doc.icon_name;
		if (!icon_name) return;

		let registered = (frappe.boot.custom_icons || []).some((icon) => icon.name === icon_name);
		let matches = document.querySelectorAll(
			`#all-symbols symbol[id="icon-${CSS.escape(icon_name)}"]`
		).length;

		if (matches > (registered ? 1 : 0)) {
			frm.dashboard.set_headline_alert(
				__("An icon named {0} already ships with the desk, and it takes precedence.", [
					icon_name.bold(),
				]),
				"orange"
			);
		}
	},
});
