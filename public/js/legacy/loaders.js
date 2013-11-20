// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

function loadreport(dt, rep_name, onload) {
	if(rep_name)
		wn.set_route('Report', dt, rep_name);
	else
		wn.set_route('Report', dt);
}	

function loaddoc(doctype, name, onload) {
	wn.model.with_doctype(doctype, function() {
		if(locals.DocType[doctype].in_dialog) {
			_f.edit_record(doctype, name);
		} else {
			wn.set_route('Form', doctype, name);			
		}
	})
}
var load_doc = loaddoc;

function new_doc(doctype, in_form) {
	wn.model.with_doctype(doctype, function() {
		var new_name = wn.model.make_new_doc_and_get_name(doctype);
		wn.set_route("Form", doctype, new_name);
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
