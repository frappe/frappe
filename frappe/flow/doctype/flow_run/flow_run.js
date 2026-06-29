// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Flow Run", {
	refresh(frm) {
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
