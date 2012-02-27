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

/** Page Body

	+ body
		+ body
			+ left_sidebar
			+ center
			+ right_sidebar
	+ dead session

**/

wn.provide('wn.pages');

function Body() { 
	this.left_sidebar = null;
	this.right_sidebar = null;
	this.status_area = null;
	var me = this;
	page_body = this;
	
	this.ready = function() {
		$dh('startup_div');
		$ds('body_div');	
	}
	
	this.setup_page_areas = function() {
		this.center = this.body;
		this.center.header = $a(this.center, 'div');
		this.center.body = $a(this.center, 'div');
		this.center.loading = $a(this.center, 'div', '', {margin:'200px 0px', fontSize:'14px', color:'#999', textAlign:'center'});
		this.center.loading.innerHTML = 'Loading...'
				
	}
	
	this.run_startup_code = function() {
		$(document).trigger('startup');
		// startup code
		try{
			if(this.cp.custom_startup_code)
				eval(this.cp.custom_startup_code);
		} catch(e) {
			errprint(e);
		}
	}
	
	this.setup = function() {
		this.cp = wn.control_panel;
		
		this.wrapper = $a($i('body_div'),'div');
		this.body = $a(this.wrapper, 'div');

		this.setup_page_areas();

		// core areas;
		if(user=='Guest') user_defaults.hide_webnotes_toolbar = 1;
		if(!cint(user_defaults.hide_webnotes_toolbar) || user=='Administrator') {
			this.wntoolbar = new wn.ui.toolbar.Toolbar();
		}
		
		// page width
		if(this.cp.page_width) 
			$y(this.wrapper,{width:cint(this.cp.page_width) + 'px'});
		
	}
	
	// Standard containers
	// - Forms
	// - Report Builder
	// - Item List
	// - [Pages by their names]

	this.cur_page = null;
	this.add_page = function(label, onshow, onhide) {
		var c = $a(this.center.body, 'div');
		if(onshow)
			c.page_show = onshow;
		if(onhide)
			c.page_hide = onhide;
		wn.pages[label] = c;
		$dh(c);
		return c;
	}
	
	this.change_to = function(label) {
		// hide existing
		$dh(this.center.loading);
		if(me.cur_page &&  wn.pages[label]!=me.cur_page) {
			if(me.cur_page.page_hide)
				me.cur_page.page_hide();
			$dh(me.cur_page);
		}
		// show
		me.cur_page = wn.pages[label];
		me.cur_page_label = label;
		$(me.cur_page).fadeIn();
	
		// on show
		if(me.cur_page.page_show)
			me.cur_page.page_show(me.cur_page);
	}
	
	this.set_session_changed = function() {
		if(this.session_message_set) return;
		var div = $a($i('body_div').parentNode,'div','',{textAlign: 'center', fontSize:'14px', margin:'150px auto'});
		$dh('body_div');
		div.innerHTML = 'This session has been changed. Please <span class="link_type" onclick="window.location.reload()">refresh</span> to continue';
		this.session_message_set = 1;
	}
	
	this.setup();
}