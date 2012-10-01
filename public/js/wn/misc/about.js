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

// ABOUT

wn.provide('wn.ui.misc');
wn.ui.misc.about = function() {
	if(!wn.ui.misc.about_dialog) {
		var d = new wn.ui.Dialog({title:'About wnframework'})
	
		$(d.body).html(repl("<div style='padding: 20px'<p><b>Application Name:</b> %(name)s</p>\
		<p><b>Version:</b> %(version)s</p>\
		<p><b>License:</b> %(license)s</p>\
		<p><b>Source Code:</b> %(source)s</p>\
		<p><b>Publisher:</b> %(publisher)s</p>\
		<p><b>Copyright:</b> %(copyright)s</p></div>", wn.app));
	
		wn.ui.misc.about_dialog = d;		
	}
	
	wn.ui.misc.about_dialog.show();
}
