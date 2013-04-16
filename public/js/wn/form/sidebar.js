wn.provide("wn.ui.form");
wn.ui.form.Sidebar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		$('<ul class="nav nav-list">').appendTo(this.frm.sidebar_area);
	},
	refresh: function() {
		
	},
});

// <ul class="nav nav-list">
//   <li class="nav-header">List header</li>
//   <li class="active"><a href="#">Home</a></li>
//   <li><a href="#">Library</a></li>
//   ...
// </ul>