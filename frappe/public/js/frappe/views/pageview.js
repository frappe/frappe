// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views.pageview');
frappe.provide("frappe.standard_pages");

frappe.views.pageview = {
	with_page: function(name, callback) {
		if(in_list(keys(frappe.standard_pages), name)) {
			if(!frappe.pages[name]) {
				frappe.standard_pages[name]();
			}
			callback();
			return;
		}

		if((locals.Page && locals.Page[name]) || name==window.page_name) {
			// already loaded
			callback();
		} else if(localStorage["_page:" + name] && frappe.boot.developer_mode!=1) {
			// cached in local storage
			frappe.model.sync(JSON.parse(localStorage["_page:" + name]));
			callback();
		} else {
			// get fresh
			return frappe.call({
				method: 'frappe.desk.desk_page.getpage',
				args: {'name':name },
				callback: function(r) {
					localStorage["_page:" + name] = JSON.stringify(r.docs);
					callback();
				}
			});
		}
	},
	show: function(name) {
		if(!name) {
			name = (frappe.boot ? frappe.boot.home_page : window.page_name);
		}
		frappe.model.with_doctype("Page", function() {
			frappe.views.pageview.with_page(name, function(r) {
				if(r && r.exc) {
					if(!r['403'])
						frappe.show_not_found(name);
				} else if(!frappe.pages[name]) {
					new frappe.views.Page(name);
				}
				frappe.container.change_to(name);
			});
		});
	}
}

frappe.views.Page = Class.extend({
	init: function(name, wrapper) {
		this.name = name;
		var me = this;
		// web home page
		if(name==window.page_name) {
			this.wrapper = document.getElementById('page-' + name);
			this.wrapper.label = document.title || window.page_name;
			this.wrapper.page_name = window.page_name;
			frappe.pages[window.page_name] = this.wrapper;
		} else {
			this.pagedoc = locals.Page[this.name];
			if(!this.pagedoc) {
				frappe.show_not_found(name);
				return;
			}
			this.wrapper = frappe.container.add_page(this.name);
			this.wrapper.label = this.pagedoc.title || this.pagedoc.name;
			this.wrapper.page_name = this.pagedoc.name;

			// set content, script and style
			if(this.pagedoc.content)
				this.wrapper.innerHTML = this.pagedoc.content;
			frappe.dom.eval(this.pagedoc.__script || this.pagedoc.script || '');
			frappe.dom.set_style(this.pagedoc.style || '');
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

frappe.show_not_found = function(page_name) {
	frappe.show_message_page(page_name, '<i class="icon-exclamation-sign"></i> ' + __("Not Found"),
		__("Sorry we were unable to find what you were looking for."));
}

frappe.show_not_permitted = function(page_name) {
	frappe.show_message_page(page_name, '<i class="icon-exclamation-sign"></i> ' +__("Not Permitted"),
		__("Sorry you are not permitted to view this page."));
}

frappe.show_message_page = function(page_name, title, message) {
	if(!page_name) page_name = frappe.get_route_str();
	var page = frappe.pages[page_name] || frappe.container.add_page(page_name);
	$(page).html('<div class="page">\
		<div style="margin: 50px; text-align:center;">\
			<h3>'+title+'</h3><br>\
			<p>'+message+'</p><br>\
			<p><a href="#">Home <i class="icon-home"></i></a></p>\
		</div>\
		</div>');
	frappe.container.change_to(page_name);
}
