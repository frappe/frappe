// render formview

wn.provide('wn.views.formview');

wn.views.formview = {
	show: function(dt, dn) {
		// show doctype
		wn.model.with_doctype(dt, function() {
			wn.model.with_doc(dt, dn, function(dn) {
				if(!wn.views.formview[dt]) {
					wn.views.formview[dt] = wn.container.add_page('Form - ' + dt);
					wn.views.formview[dt].frm = new _f.Frm(dt, wn.views.formview[dt]);
				}
				wn.container.change_to('Form - ' + dt);
				wn.views.formview[dt].frm.refresh(dn);
			});
		})
	}
}