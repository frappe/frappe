frappe.listview_settings['Scheduler Log'] = {
	add_fields: ["seen"],
	get_indicator: function(doc) {
        if(cint(doc.seen)) {
			return [__("Seen"), "green", "seen,=,1"];
        } else {
			return [__("Not Seen"), "red", "seen,=,0"];
		}
	},
	order_by: "seen asc, modified desc",
};
