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

cur_frm.cscript.issingle = function(doc, cdt, cdn) {
	if(doc.issingle)
		unhide_field('show_in_menu');
	else {
		doc.show_in_menu = 0;
		hide_field('show_in_menu');
		hide_field('parent_node');
		hide_field('Parent HTML');
		hide_field('Menu HTML');
		hide_field('menu_index');
		hide_field('smallicon');
	}
}

cur_frm.cscript.show_in_menu = function(doc, cdt, cdn) {
	if(doc.show_in_menu) {
		unhide_field('parent_node');
		unhide_field('Parent HTML');
		unhide_field('Menu HTML');
		unhide_field('menu_index');
		unhide_field('smallicon');
	} else {
		hide_field('parent_node');
		hide_field('Parent HTML');
		hide_field('Menu HTML');
		hide_field('menu_index');
		hide_field('smallicon');
	} 
}

// Attachment

cur_frm.cscript.allow_attach = function(doc, cdt, cdn) {
	if(doc.allow_attach) {
		unhide_field('max_attachments');
	} else {
		hide_field('max_attachments');
	}
}

cur_frm.cscript.onload = function(doc, cdt, cdn) {
	this.issingle(doc, cdt, cdn);
	this.allow_attach(doc, cdt, cdn);
	this.show_in_menu(doc, cdt, cdn);
}

cur_frm.cscript.refresh = function(doc, cdt, cdn) {
	if(in_list(user_roles, 'System Manager') && !in_list(user_roles, 'Administrator')) {
		// make the document read-only
		cur_frm.perm = [[1,0,0]]
		
		// make help heading
		webnotes.msgprint('<b>Cannot Edit DocType directly</b>: \
			To edit DocType properties, \
			create / update <a href="#!List/Custom%20Field">Custom Field</a>, \
			<a href="#!List/Custom%20Script">Custom Script</a> \
			and <a href="#!List/Property%20Setter">Property Setter</a>')
	}


	// show button for import
	cur_frm.add_custom_button('Import from File', cur_frm.cscript.do_import);
}

cur_frm.cscript.validate = function(doc, cdt, cdn) {
	doc.server_code_compiled = null;
}

cur_frm.cscript.do_import = function(doc, cdt, cdn) {
	callback = function(r,rt) {
		cur_frm.refresh_doc();
	}
	$c_obj([doc], 'import_doctype', '', callback)
}