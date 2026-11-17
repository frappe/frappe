// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Flow Tool", {
	async refresh(frm) {
		const { message: unavailable } = await frappe.call(
			"frappe.flow.doctype.flow_tool.flow_tool.unavailable_tools"
		);
		if (unavailable.includes(frm.doc.name)) {
			frm.set_intro(__("Server scripts are off on this bench, so this tool can't run."));
		}
	},
});
