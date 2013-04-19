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

// recent document list
wn.ui.toolbar.RecentDocs = Class.extend({
	init:function() {
		$('.navbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" data-toggle="dropdown" href="#" \
				title="'+wn._("History")+'"\
				onclick="return false;">History</i></a>\
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
			<a href="#Form/%(dt)s/%(dn)s">\
				%(dn)s <span style="font-size: 10px">(%(dt)s)</span>\
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
		var rlist = JSON.parse(profile.recent||"[]");
		
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