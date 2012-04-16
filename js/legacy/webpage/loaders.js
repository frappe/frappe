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

function loadreport(dt, rep_name, onload) {
	if(rep_name)
		wn.set_route('Report', dt, rep_name);
	else
		wn.set_route('Report', dt);
}	

function loaddoc(doctype, name, onload) {
	//doctype = get_label_doctype(doctype);
	wn.model.with_doctype(doctype, function() {
		if(locals.DocType[doctype].in_dialog) {
			_f.edit_record(doctype, name);
		} else {
			wn.set_route('Form', doctype, name);			
		}
	})
}
var load_doc = loaddoc;

function new_doc(doctype, onload, in_dialog, on_save_callback, cdt, cdn, cnic) {
	doctype = get_label_doctype(doctype);
	wn.model.with_doctype(doctype, function() {
		if(locals.DocType[doctype].in_dialog) {
			var new_name = LocalDB.create(doctype);
			_f.edit_record(doctype, new_name);
		} else {
			wn.views.formview.create(doctype);
		}
	})
}
var newdoc = new_doc;

var pscript={};
function loadpage(page_name, call_back, no_history) {
	wn.set_route(page_name);
}

function loaddocbrowser(dt) {	
	wn.set_route('List', dt);
}
