// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// page container
wn.provide('wn.pages');
wn.provide('wn.views');

wn.views.Container = Class.extend({
	_intro: "Container contains pages inside `#container` and manages \
			page creation, switching",
	init: function() {
		this.container = $('#body_div').get(0);
		this.page = null; // current page
		this.pagewidth = $('#body_div').width();
		this.pagemargin = 50;		
	},
	add_page: function(label, onshow, onhide) {
		var page = $('<div class="content"></div>')
			.attr('id', "page-" + label)
			.toggle(false)
			.appendTo(this.container).get(0);
		if(onshow)
			$(page).bind('show', onshow);
		if(onshow)
			$(page).bind('hide', onhide);
		page.label = label;
		wn.pages[label] = page;
		
		return page;
	},
	change_to: function(label) {
		if(this.page && this.page.label == label) {
			// don't trigger double events
			$(this.page).trigger('show');
			return;
		}
		
		var me = this;
		if(label.tagName) {
			// if sent the div, get the table
			var page = label;
		} else {
			var page = wn.pages[label];
		}
		if(!page) {
			console.log(wn._('Page not found')+ ': ' + label);
			return;
		}
		
		// hide dialog
		if(cur_dialog && cur_dialog.display && !cur_dialog.keep_open) {
			cur_dialog.hide();
		}
		
		// hide current
		if(this.page && this.page != page) {
			$(this.page).toggle(false);
			$(this.page).trigger('hide');
		}
		
		// show new
		if(!this.page || this.page != page) {
			this.page = page;
			//$(this.page).fadeIn();
			$(this.page).toggle(true);
		}
		
		$(document).trigger("page-change");
		
		this.page._route = window.location.hash;
		$(this.page).trigger('show');
		scroll(0,0);
		return this.page;
	}
});

wn.views.Factory = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
	},
	show: function() {
		var page_name = wn.get_route_str(),
			me = this;
		if(wn.pages[page_name]) {
			wn.container.change_to(wn.pages[page_name]);
		} else {
			var route = wn.get_route();
			if(route[1]) {
				me.make(route);
			} else {
				wn.show_not_found(route);
			}
		}
	},
	make_page: function(double_column) {
		var page_name = wn.get_route_str(),
			page = wn.container.add_page(page_name);

		wn.ui.make_app_page({
			parent: page, 
			single_column: !double_column
		});
		wn.container.change_to(page_name);
		return page;
	}
})