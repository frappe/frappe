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
