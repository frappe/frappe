// recent document list
wn.ui.toolbar.Bookmarks = Class.extend({
	init:function() {
		$('.navbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" data-toggle="dropdown" href="#" \
				title="'+wn._("Bookmarks")+'"\
				onclick="return false;"><i class="icon-star"></i></a>\
			<ul class="dropdown-menu" id="toolbar-bookmarks">\
				<li class="divider"></li>\
				<li><a href="#" id="add-bookmark-link">'+wn._('Add Bookmark')+'</a></li>\
			</ul>\
		</li>');
		
		
		this.setup();
	},
	setup: function() {
		var me = this;

		this.bookmarks = wn.user.get_default("_bookmarks") || [];
		for(var i=this.bookmarks.length-1; i>=0; i--) {
			var bookmark = this.bookmarks[i];
			this.add_item(bookmark.route, bookmark.title)
		}

		$("#add-bookmark-link").click(function() {
			me.add(wn.get_route_str(), document.title);
			return false;
		})

	},
	add_item: function(route, title) {
		var html = repl('<li><a href="#%(route)s">%(title)s</a></li>', 
			{route: route, title: title});
		$('#toolbar-bookmarks').prepend(html);
		
	},
	add: function(route, title) {
		// bring to front
		if(wn.utils.filter_dict(this.bookmarks, {"route": route}).length) {
			this.remove(route);
		}

		// max length
		if(this.bookmarks.length >= 11) {
			this.remove(this.bookmarks[this.bookmarks.length-1].route);
		}

		this.add_item(route, title);

		this.bookmarks = [{"route":route, "title":title}].concat(this.bookmarks);

		// update server
		wn.user.set_default("_bookmarks", this.bookmarks);
	},
	remove: function(route) {
		this.bookmarks = $.map(this.bookmarks, function(d) { 
			if(d.route!=route) return d; });
		$(repl('#toolbar-bookmarks li a[href="#%(route)s"]', {route:route})).parent().remove();
	},
});