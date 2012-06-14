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

/* standard 2-column layout with
	wrapper
		+ wtab
			+ main
				+ head
				+ toolbar_area
				+ body
				+ footer
			+ sidebar_area

*/

wn.PageLayout = function(args) {
	$.extend(this, args)
	this.wrapper 		= $a(this.parent, 'div', 'layout-wrapper layout-wrapper-background');
	this.head 			= $a(this.wrapper, 'div');	
	this.main 			= $a(this.wrapper, 'div', 'layout-main-section');
	this.sidebar_area 	= $a(this.wrapper, 'div', 'layout-side-section');
	$a(this.wrapper, 'div', '', {clear:'both'});
	this.body 			= $a(this.main, 'div');
	this.footer 		= $a(this.main, 'div');
	if(this.heading) {
		this.page_head = new PageHeader(this.head, this.heading);
	}
}