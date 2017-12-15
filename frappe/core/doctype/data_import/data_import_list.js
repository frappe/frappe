frappe.listview_settings['Data Import'] = {
	add_fields: ["import_status"],
	get_indicator: function(doc) {
		if (doc.import_status=="Successful") {
			return [__("Data imported"), "blue", "import_status,=,Successful"];
		} else if(doc.import_status == "Partially Successful") {
			return [__("Data partially imported"), "blue", "import_status,=,Partially Successful"];
		} else if(doc.import_status == "In Process") {
			return [__("Data import in progress"), "orange", "import_status,=,In Process"];
		} else if(doc.import_status == "Failed") {
			return [__("Data import failed"), "red", "import_status,=,Failed"];
		} else {
			return [__("Data import pending"), "green", "import_status,=,"];
		}
	}
};