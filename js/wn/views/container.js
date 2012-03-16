// page container
wn.provide('wn.pages');
wn.provide('wn.views');

wn.views.Container = Class.extend({
	init: function() {
		this.container = $('#body_div').get(0);
		this.page = null; // current page
	},
	add_page: function(label, onshow, onhide) {
		var page = $('<div class="content"></div>')
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
		if(label.tagName) {
			// if sent the div, get the table
			var page = label;
		} else {
			var page = wn.pages[label];			
		}
		if(!page) {
			console.log('Page not found ' + label);
			return;
		}
		
		// hide current
		if(this.page) {
			$(this.page).css('left', '-1000px');
		}
		
		// show new
		this.page = page;
		$(this.page).css('left', '0px');
		return this.page;
	},
	show: function(label) { 
		return this.change_to(label); 
	}
});