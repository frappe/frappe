// page container
wn.provide('wn.pages');
wn.provide('wn.views');

wn.views.Container = Class.extend({
	init: function() {
		this.container = $('#body_div').get(0);
		this.page = null; // current page
		this.pagewidth = $('#body_div').width();
		this.opened = [];
		this.pagemargin = 50;
	},
	add_page: function(label, onshow, onhide) {
		var page = $('<div class="content"></div>')
			.css('left', this.pagewidth + this.pagemargin + 'px')
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
			this.move_left(page);
			$(this.page).trigger('hide');
			this.opened.push(this.page);
			if(!this.opened_selector)
				this.select_opened_page();
		}
		
		// show new
		this.page = page;
		$(this.page).css('left', '0px').css('top', '0px');
		$(this.page).trigger('show');
		this.page._route = window.location.hash;
		document.title = this.page.label;
		
		// remove from opened
		this.stack();
		
		return this.page;
	},
	move_left: function(page) {
		$(page).css('left', (-1 * (this.pagewidth + this.pagemargin)) + 'px');
	},
	stack: function() {
		var me = this;
		var l = -1 * (this.pagewidth + this.pagemargin);
		var i = 0;
		
		// filter out current open
		this.opened = $.map(this.opened, 
			function(p, i) { 
				if(p!=me.page) return p;
			});
		
		// display as as stack
		var pcontent = [];
		$.map(this.opened, function(p, i) { 	
			$(p).css('left', l-(i*2) + 'px')
				.css('top', (i*2) + 'px')
				.css('z-index', i);
		});
	},
	
	build_open_links: function(p) {
		var open_links = [];
		// make popover content
		var me = this;
		
		$.each(me.opened.concat([me.page]), function(i, p) {
			var route = wn.get_route(p._route);
		
			if(route[0]=='Form') {
				var openlist = keys(wn.views.formview[route[1]].frm.opendocs).sort();
				$.each(openlist, function(i,v) {
					if(me.page!=p || (me.page==p && me.page.frm.docname!=v)) {
						open_links.push(repl('<p><a href="#!Form/%(dt)s/%(dn)s">%(dn)s (%(dt)s)</a></p>', {
							dt: route[1],
							dn: v
						}));
					}
				});
			} else {
				if(me.page!=p) {
					open_links.push(repl('<p><a href="%(route)s">%(label)s</a></p>', {
						route: p._route,
						label: p.label
					}));				
				}
			}
		});
		return open_links;
	},
	
	select_opened_page: function() {
		var me = this;
		// side image with popover
		this.opened_selector = $('<div id="opened-page-selector">\
			<div class="popover-container"></div></div>')
			.appendTo(this.container)
			.hover(function() {
				$(this).toggleClass('active')
			}).click(function() {
				// build links
				$('#opened-page-selector .popover-container')
					.attr('data-content', me.build_open_links().reverse().join(''));


				$(this).find('.popover-container').popover('show');
				me.popoveropen = true;
				return false;
			})
			
		this.opened_selector.find('.popover-container').popover({
			title: "Open Pages",
			trigger: 'manual',
			delay: 0
		});
		
		$(document).click(function() {

			if(me.popoveropen) {
				$('#opened-page-selector .popover-container').popover('hide');
				me.popoveropen = false;				
			}
		})
		
		this.move_left(this.opened_selector);
	},
	show: function(label) { 
		return this.change_to(label); 
	}
});