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

wn.pages.DocListView = Class.extend({
	init: function(doctype, page) {
		this.doctype = doctype;
		this.wrapper = page;
		this.label = get_doctype_label(doctype);
		this.label = (this.label.toLowerCase().substr(-4) == 'list') ?
		 	this.label : (this.label + ' List')	
		
		this.make();
	},
	make: function() {
		$(this.wrapper).html('<div class="layout_wrapper">\
			<div class="header"></div>\
			<div class="filters">[filters]</div>\
			<div class="body">[body]</div>\
		</div>');
		
		new PageHeader($(this.wrapper).find('.header').get(0), this.label)
	}
})
