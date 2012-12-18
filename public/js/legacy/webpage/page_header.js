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

/* standard page header

	+ wrapper
		+ [table]
			+ [r1c1] 
				+ main_head
				+ sub_head
			+ [r1c2] 
				+ close_btn
		+ toolbar_area
		+ tag_area
		+ seperator
*/

var def_ph_style = {
	wrapper: {marginBottom:'16px', backgroundColor:'#EEE'}
	,main_heading: { }
	,sub_heading: { marginBottom:'8px', color:'#555', display:'none' }
	,separator: { borderTop:'1px solid #ddd' } // show this when there is no toolbar
	,toolbar_area: { padding:'3px 0px', display:'none',borderBottom:'1px solid #ddd'}
}

function PageHeader(parent, main_text, sub_text) {

	this.wrapper = $a(parent,'div','page_header');
	this.close_btn = $a(this.wrapper, 'a', 'close', {}, '&times;');
	this.close_btn.onclick = function() { window.history.back(); };
	
	this.main_head = $a(this.wrapper, 'h1', '', def_ph_style.main_heading);
	this.sub_head = $a(this.wrapper, 'h4', '', def_ph_style.sub_heading);

	this.separator = $a(this.wrapper, 'div', '', def_ph_style.separator);
	this.toolbar_area = $a(this.wrapper, 'div', '', def_ph_style.toolbar_area);
	this.padding_area = $a(this.wrapper, 'div', '', {padding:'3px'});

	if(main_text) this.main_head.innerHTML = main_text;
	if(sub_text) this.sub_head.innerHTML = sub_text;
	
	this.buttons = {};
	this.buttons2 = {};
}

PageHeader.prototype.add_button = function(label, fn, bold, icon, green) {

	var tb = this.toolbar_area;
	if(this.buttons[label]) return;

	iconhtml = icon ? ('<i class="'+icon+'"></i> ') : '';

	var $button = $('<button class="btn">'+ iconhtml + label +'</button>')
		.click(fn)
		.appendTo(tb);
	if(green) {
		$button.addClass('btn-info');
		$button.find('i').addClass('icon-white');
	}
	if(bold) $button.css('font-weight', 'bold');
	
	this.buttons[label] = $button.get(0);
	$ds(this.toolbar_area);
	
	return this.buttons[label];
}

PageHeader.prototype.clear_toolbar = function() {
	this.toolbar_area.innerHTML = '';
	this.buttons = {};
}

PageHeader.prototype.make_buttonset = function() {
	$(this.toolbar_area).buttonset();
}