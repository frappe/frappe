// Copyright 2013 Web Notes Technologies Pvt Ltd
// License: MIT. See license.txt

// Routing Rules
// --------------
// `Report` shows list of all pages from which you can start a report + all saved reports
// (module wise)
// `Report/[doctype]` shows report for that doctype
// `Report/[doctype]/[report_name]` loads report with that name

wn.views.reportview = {
	show: function(dt) {
		var page_name = wn.get_route_str();
		if(wn.pages[page_name]) {
			wn.container.change_to(wn.pages[page_name]);
		} else {
			var route = wn.get_route();
			if(route[1]) {
				new wn.views.ReportViewPage(route[1], route[2]);
			} else {
				wn.set_route('404');
			}
		}
	}
}