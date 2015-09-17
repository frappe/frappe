frappe.listview_settings['Async Task'] = {
	add_fields: ["status"],
	get_indicator: function(doc) {
		if(doc.status==="Succeeded") {
			return [__("Succeeded"), "green", "status,=,Succeeded"];
		} else if(doc.status==="Failed") {
			return [__("Failed"), "red", "status,=,Failed"];
		}
	}
};
