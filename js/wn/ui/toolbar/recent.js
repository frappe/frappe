// recent document list
wn.ui.toolbar.RecentDocs = Class.extend({
	init:function() {
		$('.topbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" href="#" onclick="return false;">Recent</a>\
			<ul class="dropdown-menu" id="toolbar-recent"></ul>\
		</li>');
		this.setup();
		this.bind_events();
	},
	bind_events: function() {
		rename_observers.push(this);
	},
	rename_notify: function(dt, old, name) {
		this.remove(dt, old);
		this.add(dt, name, 1);
	},
	add: function(dt, dn, on_top) {
		if(this.istable(dt)) return;
		
		this.remove(dt, dn);
		var html = repl('<li data-docref="%(dt)s/%(dn)s">\
			<a href="#Form/%(dt)s/%(dn)s">\
				<span class="help">%(dt)s</span>: %(dn)s\
			</a></li>', 
			{dt:dt, dn:dn});
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
		try{ var rlist = JSON.parse(profile.recent); }
		catch(e) { return; /*old style-do nothing*/ }
		
		var m = rlist.length;
		if(m>15)m=15;
		for (var i=0;i<m;i++) {
			var rd = rlist[i]
			if(rd[1]) {
				var dt = rd[0]; var dn = rd[1];
				this.add(dt, dn, 0);
			}
		}		
	}
});