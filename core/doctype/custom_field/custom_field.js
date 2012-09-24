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

//168
// Refresh
// --------

cur_frm.cscript.refresh = function(doc, cdt, cdn) {
	cur_frm.toggle_enable('dt', doc.__islocal)
	cur_frm.cscript.dt(doc, cdt, cdn);
}


cur_frm.cscript.has_special_chars = function(t) {
	var iChars = "!@#$%^&*()+=-[]\\\';,./{}|\":<>?";
	for (var i = 0; i < t.length; i++) {
		if (iChars.indexOf(t.charAt(i)) != -1) {
			return true;
		}
	}
	return false;
}


// Label
// ------
cur_frm.cscript.label = function(doc){
	if(doc.label && cur_frm.cscript.has_special_chars(doc.label)){
		cur_frm.fields_dict['label_help'].disp_area.innerHTML = '<font color = "red">Special Characters are not allowed</font>';
		doc.label = '';
		refresh_field('label');
	}
	else
		cur_frm.fields_dict['label_help'].disp_area.innerHTML = '';
}


cur_frm.fields_dict['dt'].get_query = function(doc, dt, dn) {
	return 'SELECT name FROM `tabDocType` \
	WHERE IFNULL(issingle,0)=0 AND \
	IFNULL(in_create, 0)=0 AND \
	(module IN ("Accounts", "Buying", "HR", "Knowledge Base", \
		"Production", "Projects", "Selling", "Stock", "Support") OR \
		name IN ("Contact", "Address")) AND \
	name LIKE "%s" ORDER BY name ASC LIMIT 50';
}

cur_frm.cscript.fieldtype = function(doc, dt, dn) {
	if(doc.fieldtype == 'Link') cur_frm.fields_dict['Options Help'].disp_area.innerHTML = 'Please enter name of the document you want this field to be linked to in <b>Options</b>.<br> Eg.: Customer';
	else if(doc.fieldtype == 'Select') cur_frm.fields_dict['Options Help'].disp_area.innerHTML = 'Please enter values in <b>Options</b> separated by enter. <br>Eg.: <b>Field:</b> Country <br><b>Options:</b><br>China<br>India<br>United States<br><br><b> OR </b><br>You can also link it to existing Documents.<br>Eg.: <b>link:</b>Customer';
	else cur_frm.fields_dict['Options Help'].disp_area.innerHTML = '';
}


cur_frm.cscript.dt = function(doc, dt, dn) {
	if(!doc.dt) {
		set_field_options('insert_after', '');
		return;
	}
	wn.call({
		method: 'core.doctype.custom_field.custom_field.get_fields_label',
		args: { doctype: doc.dt, fieldname: doc.fieldname },
		callback: function(r, rt) {
			doc = locals[doc.doctype][doc.name];
			var insert_after_val = null;
			if(doc.insert_after) {
				insert_after_val = doc.insert_after;
			}
			set_field_options('insert_after', r.message, insert_after_val);
		}
	});
}
