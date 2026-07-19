// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Flow Run", {
	refresh(frm) {
		if (frm.doc.output) {
			const trimmed = frm.doc.output.trim();
			if (trimmed !== frm.doc.output) {
				frm.doc.output = trimmed;
				frm.refresh_field("output");
			}
		}

		const parse = (value) => {
			if (!value) return null;
			if (typeof value === "object") return value;
			try {
				return JSON.parse(value);
			} catch {
				return null;
			}
		};

		frm.get_field("detail_html").$wrapper.html(
			frappe.render_template("flow_run_detail", {
				usage: parse(frm.doc.usage),
				config: parse(frm.doc.config_snapshot),
				calls: parse(frm.doc.tool_calls),
				questions: parse(frm.doc.questions),
			})
		);
	},
});
