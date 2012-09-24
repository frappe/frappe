// render formview

wn.provide('wn.views.formview');

wn.views.formview = {
	show: function(dt, dn) {
		// renamed (on save)?
		if(wn.model.new_names[dn])
			dn = wn.model.new_names[dn];
		
		// show doctype
		wn.model.with_doctype(dt, function() {
			wn.model.with_doc(dt, dn, function(dn, r) {
				if(r && r['403']) return; // not permitted
				
				if(!(locals[dt] && locals[dt][dn])) {
					wn.container.change_to('404');
					return;
				}
				if(!wn.views.formview[dt]) {
					wn.views.formview[dt] = wn.container.add_page('Form - ' + dt);
					wn.views.formview[dt].frm = new _f.Frm(dt, wn.views.formview[dt], true);
				}
				wn.container.change_to('Form - ' + dt);
				wn.views.formview[dt].frm.refresh(dn);
			});
		})
	},
	create: function(dt) {
		var new_name = LocalDB.create(dt);
		wn.set_route('Form', dt, new_name);
	}
}
