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

// opts = { 'title': 'My Sidebar',
//  'sections': [
//     {'title': 'Actions', 
//		'items': [{type: , label:, onclick function / string to eval], ]
//		'render': function (optional) 
//		}
//
// item types = link, button, html, inpu


//
// Page Sidebar
//
wn.widgets.PageSidebar = function(parent, opts) {
	this.opts = opts
	this.sections = {}
	this.wrapper = $a(parent, 'div', 'psidebar')

	// refresh sidebar - make head and sections
	this.refresh = function() {
		this.wrapper.innerHTML = ''
		if(this.opts.title)
			this.make_head();
		for(var i=0; i<this.opts.sections.length; i++) {
			var section = this.opts.sections[i];

			if((section.display && section.display()) || !section.display) {
			
				this.sections[section.title] 
					= new wn.widgets.PageSidebarSection(this, section);
			}
		}
		if(this.opts.onrefresh) { this.opts.onrefresh(this) }
	}

	this.make_head = function() {
		this.head = $a(this.wrapper, 'div', 'head', '', this.opts.title);
	}
	
	this.refresh();
}

//
// Sidebar Section
//
wn.widgets.PageSidebarSection = function(sidebar, opts) {
	this.items = [];
	this.sidebar = sidebar;
	this.wrapper = $a(sidebar.wrapper, 'div', 'section');
	this.head = $a(this.wrapper, 'div', 'section-head', '', opts.title);
	this.body = $a(this.wrapper, 'div', 'section-body');
	$br(this.wrapper, '5px');
	this.opts = opts;


	// make items
	this.make_items = function() {
		for(var i=0; i<this.opts.items.length; i++) {
			
			var item = this.opts.items[i];
			if((item.display && item.display()) || !item.display) {
				
				var div = $a(this.body, 'div', 'section-item');
				this.make_one_item(item, div);
			}
				
		}
	}

	this.make_one_item = function(item, div) {
		if (item.type.toLowerCase()=='link')
			this.items[item.label] = new wn.widgets.PageSidebarLink(this, item, div);

		else if (item.type.toLowerCase()=='button')
			this.items[item.label] = new wn.widgets.PageSidebarButton(this, this.opts.items[i], div);

		//else if (item.type=='Input')
		//	new wn.widgets.PageSidebarInput(this, this.opts.items[i], div);

		else if (item.type.toLowerCase()=='html')
			this.items[item.label] = new wn.widgets.PageSidebarHTML(this, this.opts.items[i], div);
	}
	
	// image
	this.add_icon = function(parent, icon) {
		var img = $a(parent, 'i', icon, {marginRight: '7px', marginBottom:'-3px'});
	}
	
	this.refresh = function() {
		this.body.innerHTML = '';
		if(this.opts.render) { 
			this.opts.render(this.body); }
		else 
			this.make_items();
	}
	this.refresh();
}
//
// Elements
//

// link
wn.widgets.PageSidebarLink = function(section, opts, wrapper) {
	this.wrapper = wrapper;
	this.section = section;
	this.opts = opts;
	
	var me = this;
	if(opts.icon) {
		section.add_icon(this.wrapper, opts.icon);
	}
	this.ln = $a(this.wrapper, 'span', 'link_type section-link', opts.style, opts.label);
	this.ln.onclick = function() { me.opts.onclick(me) };
}

// button
wn.widgets.PageSidebarButton = function(section, opts, wrapper) {
	this.wrapper = wrapper;
	this.section = section;
	this.opts = opts;
	
	var me = this;
	this.btn = $btn(this.wrapper, opts.label, opts.onclick, opts.style, opts.color);
}

// html
wn.widgets.PageSidebarHTML = function(section, opts, wrapper) {
	wrapper.innerHTML = opts.content
}