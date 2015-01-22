// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// recent document list
frappe.ui.toolbar.RecentDocs = Class.extend({
	init:function() {
		$('.navbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" data-toggle="dropdown" href="#" \
				title="'+__("History")+'"\
				onclick="return false;">'+__("History")+'</i></a>\
			<ul class="dropdown-menu" id="toolbar-recent"></ul>\
		</li>');
		this.setup();
		this.bind_events();
	},
	bind_events: function() {
		// notify on rename
		var me = this;
		$(document).bind('rename', function(event, dt, old_name, new_name) {
			me.rename_notify(dt, old_name, new_name)
		});
	},
	rename_notify: function(dt, old, name) {
		this.remove(dt, old);
		this.add(dt, name, 1);
	},
	add: function(dt, dn, on_top) {
		if(this.istable(dt)) return;

		this.remove(dt, dn);
		var html = repl('<li data-docref="%(dt)s/%(dn)s">\
			<a href="#Form/%(dt_encoded)s/%(dn_encoded)s">\
				<i class="icon-fixed-width %(icon)s"></i> \
				%(dnshow)s</span>\
			</a></li>',
			{dt_encoded:encodeURIComponent(dt), dn_encoded:encodeURIComponent(dn),
			dt: dt, dn: dn,dnshow:__(dn), icon:frappe.boot.doctype_icons[dt]});
		if(on_top) {
			$('#toolbar-recent').prepend(html);
		} else {
			$('#toolbar-recent').append(html);
		}
	},
	istable: function(dt) {
		return locals.DocType[dt] && locals.DocType[dt].istable || false;
	},
	remove: function(dt, dn) {
		$(repl('#toolbar-recent li[data-docref="%(dt)s/%(dn)s"]', {dt:dt, dn:dn})).remove();
	},
	setup: function() {
		// add menu items
		if(!user) return;
		var rlist = JSON.parse(frappe.boot.user.recent||"[]");
		if(!rlist) return;
		var m = rlist.length;
		if(m>15)m=15;
		for (var i=0;i<m;i++) {
			var rd = rlist[i]
			if(rd[1]) {
				var dt = rd[0]; var dn = rd[1];
				try {
					this.add(dt, dn, 0);
				} catch(e) {
					// don't crash
				}
			}
		}
	}
});
