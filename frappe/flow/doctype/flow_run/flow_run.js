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
				input: (frm.doc.input || "").trim(),
				output: (frm.doc.output || "").trim(),
				error: (frm.doc.error || "").trim(),
				usage: parse(frm.doc.usage),
				calls: parse(frm.doc.tool_calls),
				questions: parse(frm.doc.questions),
			})
		);
	},
});
