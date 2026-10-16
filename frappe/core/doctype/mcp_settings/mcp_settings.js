// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("MCP Settings", {
	refresh(frm) {
		const url = frappe.utils.escape_html(`${frappe.urllib.get_base_url()}/api/v2/mcp`);
		frm.set_intro(
			[
				__("Connect MCP clients to {0}.", [`<code>${url}</code>`]),
				__(
					"To authenticate, open the agent's User, select API Access > Generate Keys, and send the header {0}.",
					["<code>Authorization: token API_KEY:API_SECRET</code>"]
				),
			].join("<br>")
		);
	},
});
