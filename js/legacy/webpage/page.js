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

// PAGE

function Page(page_name, content) {	
	var me = this;
	this.name = page_name;

	this.trigger = function(event) {
		try {
			if(pscript[event+'_'+this.name]) 
				pscript[event+'_'+this.name](me.wrapper);
			if(me.wrapper[event]) {
				me.wrapper[event](me.wrapper);
			}
		} catch(e) { 
			console.log(e); 
		}
	}

	this.page_show = function() {
		// default set_title
		set_title(me.doc.title ? me.doc.title : me.name);
		
		if(!me.onload_complete) {
			me.trigger('onload');
			me.onload_complete = true;
		}
		me.trigger('onshow');
		
		// clear cur_frm
		cur_frm = null;
	}

	this.wrapper = page_body.add_page(page_name, this.page_show);
	this.cont = this.wrapper // bc

	if(content)
		this.wrapper.innerHTML = content;
	
	return this;
}


function render_page(page_name, menuitem) {
	if(!page_name)return;
	if((!locals['Page']) || (!locals['Page'][page_name])) {
		// no page, go home
		loadpage('_home');
		return;
	}
	var pdoc = locals['Page'][page_name];

	// style
	if(pdoc.style) set_style(pdoc.style)

	// create page
	var p = new Page(page_name, pdoc._Page__content?pdoc._Page__content:pdoc.content);
	// script
	var script = pdoc.__script ? pdoc.__script : pdoc.script;
	p.doc = pdoc;

	if(script) {
		eval(script);
	}

	// change
	page_body.change_to(page_name);	
		
	return p;
}

function refresh_page(page_name) {
	var fn = function(r, rt) {
		render_page(page_name)	
	}
	$c('webnotes.widgets.page.getpage', {'name':page_name}, fn);
}
