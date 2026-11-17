// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Flow Agent", {
	async refresh(frm) {
		const { message } = await frappe.call(
			"frappe.flow.doctype.flow_tool.flow_tool.unavailable_tools"
		);
		frm.unavailable_tools = message;
		show_unavailable_tools(frm);
	},
});

frappe.ui.form.on("Flow Agent Tool", {
	tools_add: show_unavailable_tools,
	tools_remove: show_unavailable_tools,
});

function show_unavailable_tools(frm) {
	const off = (frm.doc.tools || [])
		.map((row) => row.tool)
		.filter((tool) => (frm.unavailable_tools || []).includes(tool));
	// translated here: joined to the note, it no longer matches its translation
	let description = __(
		frappe.meta.docfield_map["Flow Agent"].tools.description,
		null,
		"Flow Agent"
	);
	if (off.length) {
		description +=
			" " +
			__("Server scripts are off on this bench, so these can't run: {0}.", [
				off.map((tool) => tool.replace("frappe/", "")).join(", "),
			]);
	}
	frm.set_df_property("tools", "description", description);
}
