// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// recent document list
wn.ui.toolbar.Bookmarks = Class.extend({
	init:function() {
		$('.navbar .nav:first').append('<li class="dropdown">\
			<a class="dropdown-toggle" data-toggle="dropdown" href="#" \
				title="'+wn._("Bookmarks")+'"\
				onclick="return false;">'+wn._("Bookmarks")+'</a>\
			<ul class="dropdown-menu" id="toolbar-bookmarks">\
				<li class="divider"></li>\
				<li><a href="#" id="add-bookmark-link"><i class="icon-plus"></i> '
					+wn._('Add Bookmark')+'</a></li>\
				<li style="display: none" id="remove-bookmark-link"><a href="#"><i class="icon-minus"></i> '
					+wn._('Remove Bookmark')+'</a></li>\
			</ul>\
		</li>');
		
		
		this.setup();
	},
	setup: function() {
		var me = this;

		this.bookmarks = wn.defaults.get_default("_bookmarks") || [];
		for(var i=this.bookmarks.length-1; i>=0; i--) {
			var bookmark = this.bookmarks[i];
			this.add_item(bookmark.route, bookmark.title)
		}

		$("#add-bookmark-link").click(function() {
			me.add(wn.get_route_str(), document.title);
			return false;
		})

		$("#remove-bookmark-link").click(function() {
			me.remove(wn.get_route_str());
			me.save();
			me.show_hide_bookmark();
			return false;
		});

		$(window).bind('hashchange', function() {
			me.show_hide_bookmark();
		});
		
		me.show_hide_bookmark();
	},
	show_hide_bookmark: function() {
		$("#remove-bookmark-link").toggle(this.bookmarked(wn.get_route_str()) ? true : false);
	},
	add_item: function(route, title) {
		var route_parts = decodeURIComponent(route).split("/");
		if(route_parts[0]==="List" || route_parts[0]==="Form") {
			var icon = wn.boot.doctype_icons[route_parts[1]];
		} else {
			var icon = "icon-play";
		}
		var html = repl('<li><a href="#%(route)s"><i class="icon-fixed-width %(icon)s"></i> %(title)s</a></li>', 
			{route: route, title: title, icon: icon});
		$('#toolbar-bookmarks').prepend(html);
		
	},
	add: function(route, title) {
		// bring to front
		if(this.bookmarked(route)) {
			this.remove(route);
		}

		// max length
		if(this.bookmarks.length >= 11) {
			this.remove(this.bookmarks[this.bookmarks.length-1].route);
		}

		this.add_item(route, title);
		this.bookmarks = [{"route":route, "title":title}].concat(this.bookmarks);
		this.save();
	},
	bookmarked: function(route) {
		return wn.utils.filter_dict(this.bookmarks, {"route": route}).length;
	},
	save: function() {
		wn.defaults.set_default("_bookmarks", this.bookmarks);
	},
	remove: function(route) {
		this.bookmarks = $.map(this.bookmarks, function(d) { 
			if(d.route!=route) return d; });
		$(repl('#toolbar-bookmarks li a[href="#%(route)s"]', {route:route})).parent().remove();
	},
});