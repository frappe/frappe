// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("MCP Settings", {
	refresh(frm) {
		const url = frappe.utils.escape_html(`${frappe.urllib.get_base_url()}/api/v2/mcp`);
		frm.set_intro(
			[
				__("Connect MCP clients to {0}.", [`<code>${url}</code>`]),
				__(
					"Clients sign in with OAuth: they open this site's login and ask you to allow access. Configure this in {0}.",
					[
						frappe.utils.get_form_link(
							"OAuth Settings",
							"OAuth Settings",
							true,
							__("OAuth Settings")
						),
					]
				),
			].join("<br>")
		);
	},
});
