// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
// MIT License. See license.txt

wn.provide('wn.views.pageview');
wn.provide("wn.standard_pages");

wn.views.pageview = {
	with_page: function(name, callback) {
		if(in_list(keys(wn.standard_pages), name)) {
			if(!wn.pages[name]) {
				wn.standard_pages[name]();
			}
			callback();
			return;
		}

		if((locals.Page && locals.Page[name]) || name==window.page_name) {
			// already loaded
			callback();
		} else if(localStorage["_page:" + name]) {
			// cached in local storage
			wn.model.sync(JSON.parse(localStorage["_page:" + name]));
			callback();
		} else {
			// get fresh
			return wn.call({
				method: 'webnotes.widgets.page.getpage', 
				args: {'name':name },
				callback: function(r) {
					localStorage["_page:" + name] = JSON.stringify(r.docs);
					callback();
				}
			});
		}		
	},
	show: function(name) {
		if(!name) name = (wn.boot ? wn.boot.home_page : window.page_name);
		wn.views.pageview.with_page(name, function(r) {
			if(r && r.exc) {
				if(!r['403'])
					wn.set_route('404');
			} else if(!wn.pages[name]) {
				new wn.views.Page(name);
			}
			wn.container.change_to(name);			
		});
	}
}

wn.views.Page = Class.extend({
	init: function(name, wrapper) {
		this.name = name;
		var me = this;
		// web home page
		if(name==window.page_name) {
			this.wrapper = document.getElementById('page-' + name);
			this.wrapper.label = document.title || window.page_name;
			this.wrapper.page_name = window.page_name;
			wn.pages[window.page_name] = this.wrapper;
		} else {
			this.pagedoc = locals.Page[this.name];
			this.wrapper = wn.container.add_page(this.name);
			this.wrapper.label = this.pagedoc.title || this.pagedoc.name;
			this.wrapper.page_name = this.pagedoc.name;
		
			// set content, script and style
			if(this.pagedoc.content)
				this.wrapper.innerHTML = this.pagedoc.content;
			wn.dom.eval(this.pagedoc.__script || this.pagedoc.script || '');
			wn.dom.set_style(this.pagedoc.style || '');
		}

		this.trigger('onload');
		
		// set events
		$(this.wrapper).bind('show', function() {
			cur_frm = null;
			me.trigger('onshow');
			me.trigger('refresh');
		});
	},
	trigger: function(eventname) {
		var me = this;
		if(pscript[eventname+'_'+this.name]) {
			pscript[eventname+'_'+this.name](me.wrapper);				
		} else if(me.wrapper[eventname]) {
			me.wrapper[eventname](me.wrapper);
		}
	}
})


wn.standard_pages["404"] = function() {
	var page = wn.container.add_page('404');
	$(page).html('<div class="appframe col-md-12">\
		<h3><i class="icon-exclamation-sign"></i> '+wn._('Not Found')+'</h3><br>\
		<p>'+wn._('Sorry we were unable to find what you were looking for.')+'</p>\
		<p><a href="#">'+wn._('Go back to home')+'</a></p>\
		</div>');
};

wn.standard_pages["403"] = function() {
	var page = wn.container.add_page('403');
	$(page).html('<div class="appframe col-md-12">\
		<h3><i class="icon-minus-sign"></i> '+wn._('Not Permitted')+'</h3><br>\
		<p>'+wn._('Sorry you are not permitted to view this page.')+'.</p>\
		<p><a href="#">'+wn._('Go back to home')+'</a></p>\
		</div>');
};