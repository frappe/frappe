frappe.listview_settings['Authentication Log'] = {
	get_indicator: function(doc) {
		if(doc.operation == "Login" && doc.status == "Success")
			return [__(doc.status), "green"];
		else if(doc.operation == "Login" && doc.status == "Failed")
			return [__(doc.status), "red"];
	}
};