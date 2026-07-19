// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Flow Session", {
	refresh(frm) {
		const parse = (v) => {
			try {
				return JSON.parse(v);
			} catch {
				return null;
			}
		};
		// Pretty-print JSON strings; leave plain text untouched.
		const pretty = (v) => {
			const p = parse(v);
			return p !== null ? JSON.stringify(p, null, 2) : v;
		};

		const items = (frm.doc.messages || []).map((r) => {
			const item = {
				role: r.role,
				content: r.role === "tool" ? null : (r.content || "").trim() || null,
				calls: [],
			};
			if (r.role === "tool") item.output = pretty(r.content);
			for (const c of parse(r.tool_calls) || []) {
				const fn = c.function || c;
				item.calls.push({ name: fn.name, args: pretty(fn.arguments) });
			}
			return item;
		});

		frm.get_field("transcript_html").$wrapper.html(
			frappe.render_template("flow_session_transcript", { items })
		);
	},
});
