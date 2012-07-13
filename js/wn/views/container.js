// page container
wn.provide('wn.pages');
wn.provide('wn.views');

wn.views.Container = Class.extend({
	init: function() {
		this.container = $('#body_div').get(0);
		this.page = null; // current page
		this.pagewidth = $('#body_div').width();
		this.pagemargin = 50;		
	},
	add_page: function(label, onshow, onhide) {
		var page = $('<div class="content"></div>')
			.attr('id', "page-" + label)
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
			console.log('Page not found ' + label);
			return;
		}
		
		// hide current
		if(this.page) {
			$(this.page).toggle(false);
			$(this.page).trigger('hide');
		}
		
		// show new
		this.page = page;
		$(this.page).fadeIn();
		this.page._route = window.location.hash;
		document.title = this.page.label;
		$(this.page).trigger('show');
		scroll(0,0);				
		return this.page;
	}
});

wn.views.add_module_btn = function(parent, module) {
	$(parent).append(
		repl('<span class="label" style="margin-right: 8px; cursor: pointer;"\
					onclick="wn.set_route(\'%(module_small)s-home\')">\
					<i class="icon-home icon-white"></i> %(module)s Home\
				</span>', {module: module, module_small: module.toLowerCase()}));	
}

wn.views.add_list_btn = function(parent, doctype) {
	$(parent).append(
		repl('<span class="label" style="margin-right: 8px; cursor: pointer;"\
					onclick="wn.set_route(\'List\', \'%(doctype)s\')">\
					<i class="icon-list icon-white"></i> %(doctype)s List\
				</span>', {doctype: doctype}));	
}
