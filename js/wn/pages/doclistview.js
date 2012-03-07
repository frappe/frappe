// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

wn.provide('wn.pages.doclistview');
wn.provide('wn.doclistviews');

wn.pages.doclistview.pages = {};
wn.pages.doclistview.show = function(doctype) {
	var pagename = doctype + ' List';
	if(!wn.pages.doclistview.pages[pagename]) {
		var page = page_body.add_page(pagename);
		page.doclistview = new wn.pages.DocListView(doctype, page);
		wn.pages.doclistview.pages[pagename] = page;
	}
	page_body.change_to(pagename);
}

wn.pages.DocListView = wn.ui.Listing.extend({
	init: function(doctype, page) {
		this.doctype = doctype;
		this.$w = $(page);
		this.label = get_doctype_label(doctype);
		this.label = (this.label.toLowerCase().substr(-4) == 'list') ?
		 	this.label : (this.label + ' List');
		this.make_page();
		this.load_doctype();
	},
	
	make_page: function() {
		var me = this;
		this.$w.html(repl('<div class="layout-wrapper">\
				<a class="close" onclick="window.history.back();">&times;</a>\
				<h1>%(label)s</h1>\
				<hr>\
				<div class="wnlist-area"><div class="help">Loading...</div></div>\
		</div>', {label: this.label}));
	},

	load_doctype: function() {
		var me = this;
		wn.call({
			method: 'webnotes.widgets.form.load.getdoctype',
			args: {doctype: me.doctype},
			callback: function() {
				me.$w.find('.wnlist-area').empty(),
				me.setup_listview();
				me.init_list();
			}
		});
	},
	setup_listview: function() {
		if(locals.DocType[this.doctype].__listjs) {
			eval(locals.DocType[this.doctype].__listjs);
			this.listview = wn.doclistviews[this.doctype];
		} else {
			this.listview = {}
		}

		if(!this.listview.fields)
			this.listview.fields = [
				{field: "name", name:"ID"},
				{field: "modified", name:"Last Updated"},
				{field: "owner", name:"Created By"}
			];
		if(!this.listview.render)
			this.listview.render = this.default_render;
		
	},
	init_list: function() {
		// init list
		this.make({
			method: 'webnotes.widgets.doclistview.get',
			get_args: this.get_args,
			parent: this.$w.find('.wnlist-area'),
			start: 0,
			page_length: 20,
			show_filters: true,
			show_grid: true,
			columns: this.listview.fields
		});
		this.run();
	},
	render_row: function(row, data) {
		data.fullname = wn.user_info(data.owner).fullname;
		data.avatar = wn.user_info(data.owner).image;
		data.when = dateutil.comment_when(data.modified);
		data.doctype = this.doctype;
		this.listview.render(row, data, this);
	},	
	get_query_fields: function() {
		var fields = [];
		$.each(this.listview.fields, function(i,f) {
			fields.push(f.query || f.field);
		});
		return fields;
	},
	get_args: function() {
		return {
			doctype: this.doctype,
			subject: locals.DocType[this.doctype].subject,
			fields: JSON.stringify(this.get_query_fields()),
			filters: JSON.stringify(this.filter_list.get_filters())
		}
	},
	default_render: function(row, data) {
		$(row).html(repl('<span class="avatar-small"><img src="%(avatar)s" /></span>\
			<a href="#!Form/%(doctype)s/%(name)s">%(name)s</span>\
			<span style="float:right; font-size: 11px; color: #888">%(when)s</span>', data))
			.addClass('list-row');
	}
});
