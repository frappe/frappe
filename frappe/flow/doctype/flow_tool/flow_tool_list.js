// Copyright (c) 2026, Frappe Technologies and contributors
// License: MIT. See LICENSE

frappe.listview_settings["Flow Tool"] = {
	unavailable: [],

	async onload(listview) {
		const { message } = await frappe.call({
			method: "frappe.flow.doctype.flow_tool.flow_tool.unavailable_tools",
			type: "GET",
		});
		this.unavailable = message;
		if (message.length) listview.refresh();
	},

	get_indicator(doc) {
		if (this.unavailable.includes(doc.name)) {
			return [__("Unavailable"), "gray", `name,=,${doc.name}`];
		}
	},
};
