frappe.listview_settings['Note'] = {
	onload: function(me) {
		me.page.set_title(__("Notes"), frappe.get_module("Notes").icon);
	},
	add_fields: ["title", "public"],
}
