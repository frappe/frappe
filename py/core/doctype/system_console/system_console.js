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

cur_frm.cscript['server_python'] = function(doc, dt, dn) {
	doc.response = 'Executing...'
	refresh_field('response');
	$c_obj(make_doclist(doc.doctype, doc.name), 'execute_server', '', function(r, rt) {
		doc = locals[doc.doctype][doc.name];
		if(r.exc) {
			doc.response = r.exc;
		} else {
			doc.response = 'Worked!'.bold()
		}
		refresh_field('response');
	})
}

cur_frm.cscript['client_js'] = function(doc, dt, dn) {
	try {
		doc.response = eval(doc.script);		
	} catch(e) {
		doc.response = e.toString() 
			+ '\nMessage:' + e.message
			+ '\nLine Number:' + e.lineNumber
			+ '\nStack:' + e.stack;
	}
	refresh_field('response');
}
