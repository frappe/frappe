frappe.listview_settings['Feedback Request'] = {
	add_fields: ["rating"],
	get_indicator: function(doc) {
		if(doc.rating == 0) {
			return [__("Not Rated"), "darkgrey", "rating,=,0"];
		} else if (doc.rating<=2) {
			return ["", "red", "rating,in,1,2"];
		} else if (doc.rating>=3 && doc.rating<=4) {
			return ["", "orange", "rating,in,3,4"];
		} else if (doc.rating==5) {
			return ["", "green", "rating,=,5"];
		}
	},
}