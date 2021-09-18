frappe.listview_settings['Note'] = {
	onload: function(me) {
		me.page.set_title(__("Notes"));
	},
	add_fields: ["title", "public"],
	get_indicator: function(doc) {
		if(doc.public) {
			return [__("Public"), "green", "public,=,Yes"];
		} else {
			return [__("Private"), "gray", "public,=,No"];
		}
	}
}
