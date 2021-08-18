frappe.listview_settings['Web Page'] = {
	add_fields: ["title", "published"],
	get_indicator: function(doc) {
		if(doc.published) {
			return [__("Published"), "green", "published,=,Yes"];
		} else {
			return [__("Not Published"), "gray", "published,=,Yes"];
		}
	}
};
