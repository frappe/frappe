// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.provide('wn.views.formview');

wn.views.FormFactory = wn.views.Factory.extend({
	make: function(route) {
		var me = this,
			dt = route[1];
			
		if(!wn.views.formview[dt]) {
			me.page = wn.container.add_page("Form/" + dt);
			wn.views.formview[dt] = me.page;
			wn.model.with_doctype(dt, function() {
				me.page.frm = new _f.Frm(dt, me.page, true);
				me.show_doc(route);
			});
		} else {
			me.show_doc(route);
		}
	},
	show_doc: function(route) {
		var dt = route[1],
			dn = route.slice(2).join("/"),
			me = this;

		if(wn.model.new_names[dn]) {
			dn = wn.model.new_names[dn];
			wn.set_route("Form", dt, dn);
			return;
		}

		wn.model.with_doc(dt, dn, function(dn, r) {
			if(r && r['403']) return; // not permitted
			
			if(!(locals[dt] && locals[dt][dn])) {
				// doc not found, but starts with New,
				// make a new doc and set it
				if(dn && dn.substr(0,4)=="New ") {
					var new_name = wn.model.make_new_doc_and_get_name(dt);
					if(new_name===dn) {
						me.load(dt, dn);
					} else {
						wn.set_route("Form", dt, new_name)
					}
				} else {
					wn.show_not_found(route);
				}
				return;
			}
			me.load(dt, dn);
		});
		
	},
	load: function(dt, dn) {
		wn.container.change_to("Form/" + dt);
		wn.views.formview[dt].frm.refresh(dn);
	}
});