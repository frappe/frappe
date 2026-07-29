frappe.provide("frappe.ui.report_link_preview");

Object.assign(frappe.ui.report_link_preview, {
	is_enabled() {
		// A fixed-width right-hand panel doesn't fit a mobile viewport — fall through to
		// normal navigation there regardless of the user's preference.
		if (frappe.is_mobile()) return false;
		return Boolean(frappe.boot.desk_settings?.report_link_preview);
	},

	setup({ $click_area, $mount_parent }) {
		const side_panel = new frappe.ui.SidePanel({ parent: $mount_parent });

		$click_area.on("click", "a[data-doctype][data-name]", (e) => {
			if (!this.is_enabled()) return;
			// Ctrl/Cmd-click, middle-click, or Shift-click all mean "open elsewhere" —
			// let the browser handle those instead of hijacking into the panel.
			if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;

			const $link = $(e.currentTarget);
			const doctype = $link.attr("data-doctype");
			const name = frappe.utils.unescape_html($link.attr("data-name"));

			if (!doctype || !name) return;

			e.preventDefault();
			e.stopPropagation();

			side_panel.open({
				title: name,
				doctype: __(doctype),
				render: (body_el, { set_header }) =>
					frappe.ui.render_side_panel_form_preview(body_el, doctype, name, set_header),
				on_open_full_page: () => {
					side_panel.close();
					frappe.set_route("Form", doctype, name);
				},
			});
		});

		return side_panel;
	},
});
