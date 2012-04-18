wn.views.reportview = {
	show: function(dt, rep_name) {
		wn.require('lib/js/legacy/report.compressed.js');
		dt = get_label_doctype(dt);

		if(!_r.rb_con) {
			// first load
			_r.rb_con = new _r.ReportContainer();
		}

		_r.rb_con.set_dt(dt, function(rb) { 
			if(rep_name) {
				var t = rb.current_loaded;
				rb.load_criteria(rep_name);

				// if loaded, then run
				if((rb.dt) && (!rb.dt.has_data() || rb.current_loaded!=t)) {
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
