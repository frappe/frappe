frappe.listview_settings['Prepared Report'] = {
	add_fields: ["status"],
	get_indicator: function(doc) {
		if(doc.status==="Completed"){
			return [__("Completed"), "green", "status,=,Completed"];
		} else if(doc.status ==="Error"){
			return [__("Error"), "red", "status,=,Error"];
		} else if(doc.status ==="Queued"){
			return [__("Queued"), "orange", "status,=,Queued"];
		}
	}
};