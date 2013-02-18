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

// -------------
// Menu Display
// -------------
cur_frm.cscript.allow_attach = function(doc, cdt, cdn) {
	if(doc.allow_attach) {
		unhide_field('max_attachments');
	} else {
		hide_field('max_attachments');
	}
}

cur_frm.cscript.onload = function(doc, cdt, cdn) {
	this.allow_attach(doc, cdt, cdn);
}

cur_frm.cscript.refresh = function(doc, cdt, cdn) {
	if(in_list(user_roles, 'System Manager') && !in_list(user_roles, 'Administrator')) {
		// make the document read-only
		cur_frm.perm = [[1,0,0]]
		
		// make help heading
		msgprint('<b>Cannot Edit DocType directly</b>: \
			To edit DocType properties, \
			create / update <a href="#!List/Custom%20Field">Custom Field</a>, \
			<a href="#!List/Custom%20Script">Custom Script</a> \
			and <a href="#!List/Property%20Setter">Property Setter</a>')
	}
}

cur_frm.cscript.validate = function(doc, cdt, cdn) {
	doc.server_code_compiled = null;
}