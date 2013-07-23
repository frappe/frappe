cur_frm.cscript.refresh = function(doc) {
	cur_frm.add_custom_button("Show Report", function() {
		switch(doc.report_type) {
			case "Report Builder":
				wn.set_route("Report", doc.name);
				break;
			case "Query Report":
				wn.set_route("query-report", doc.name);
				break;
			case "Script Report":
				wn.set_route("query-report", doc.name);
				break;
		}
	}, "icon-table")
	
	cur_frm.set_intro("");
	switch(doc.report_type) {
		case "Report Builder":
			cur_frm.set_intro(wn._("Report Builder reports are managed directly by the report builder. Nothing to do."));
			break;
		case "Query Report":
			cur_frm.set_intro(wn._("Write a SELECT query. Note result is not paged (all data is sent in one go).")
				+ wn._("To format columns, give column labels in the query.") + "<br>"
				+ wn._("[Label]:[Field Type]/[Options]:[Width]") + "<br><br>"
				+ wn._("Example:") + "<br>"
				+ "Employee:Link/Employee:200" + "<br>"
				+ "Rate:Currency:120" + "<br>")
			break;
		case "Script Report":
			cur_frm.set_intro(wn._("Write a Python file in the same folder where this is saved and return column and result."))
			break;
	}
}