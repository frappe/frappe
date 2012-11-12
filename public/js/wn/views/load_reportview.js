// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//

wn.views.reportview = {
	show: function(dt, rep_name) {
		wn.require('js/report-legacy.js');
		dt = get_label_doctype(dt);

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