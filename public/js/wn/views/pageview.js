// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
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
		} else if(localStorage["_page:" + name] && wn.boot.developer_mode!=1) {
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
					wn.show_not_found(name);
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
			if(!this.pagedoc) {
				wn.show_not_found(name);
				return;
			}
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

wn.show_not_found = function(page_name) {
	wn.show_message_page(page_name, '<i class="icon-exclamation-sign"></i> ' + wn._("Not Found"), 
		wn._("Sorry we were unable to find what you were looking for."));
}

wn.show_not_permitted = function(page_name) {
	wn.show_message_page(page_name, '<i class="icon-exclamation-sign"></i> ' +wn._("Not Permitted"), 
		wn._("Sorry you are not permitted to view this page."));
}

wn.show_message_page = function(page_name, title, message) {
	if(!page_name) page_name = wn.get_route_str();
	var page = wn.pages[page_name] || wn.container.add_page(page_name);
	$(page).html('<div class="appframe">\
		<div style="margin: 50px; text-align:center;">\
			<h3>'+title+'</h3><br>\
			<p>'+message+'</p><br>\
			<p><a href="#">Home <i class="icon-home"></i></a></p>\
		</div>\
		</div>');
	wn.container.change_to(page_name);
}