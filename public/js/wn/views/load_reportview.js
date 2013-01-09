// Copyright 2013 Web Notes Technologies Pvt Ltd
// License: MIT. See license.txt

wn.views.reportview = {
	show: function(dt, rep_name) {
		wn.require('js/report-legacy.js');

		if(!_r.rb_con) {
			// first load
			_r.rb_con = new _r.ReportContainer();
		}

		_r.rb_con.set_dt(dt, function(rb) { 
			if(rep_name) {
				var route_changed = (rb.current_route != wn.get_route_str())
				rb.load_criteria(rep_name);

				// if loaded, then run				
				if(rb.dt && route_changed) {
					rb.dt.run();
				}
			}

			// show
			if(!rb.forbidden) {
				wn.container.change_to('Report Builder');
			}
		} );
	}
}

// Routing Rules
// --------------
// `Report` shows list of all pages from which you can start a report + all saved reports
// (module wise)
// `Report/[doctype]` shows report for that doctype
// `Report/[doctype]/[report_name]` loads report with that name

wn.views.reportview2 = {
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