// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

//168
// Refresh
// --------

cur_frm.cscript.refresh = function(doc, cdt, cdn) {
	cur_frm.toggle_enable('dt', doc.__islocal);
	cur_frm.cscript.dt(doc, cdt, cdn);
	cur_frm.toggle_reqd('label', !doc.fieldname);
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
	filters = [
		['DocType', 'issingle', '=', 0],
	];
	if(user!=="Administrator") {
		filters.push(['DocType', 'module', '!=', 'Core'])
	}
	return filters
}

cur_frm.cscript.fieldtype = function(doc, dt, dn) {
	if(doc.fieldtype == 'Link') {
		cur_frm.fields_dict['options_help'].disp_area.innerHTML =
		  __('Name of the Document Type (DocType) you want this field to be linked to. e.g. Customer');
	} else if(doc.fieldtype == 'Select') {
		cur_frm.fields_dict['options_help'].disp_area.innerHTML =
			__('Options for select. Each option on a new line.')+' '+__('e.g.:')+'<br>'+__('Option 1')+'<br>'+__('Option 2')+'<br>'+__('Option 3')+'<br>';
	} else if(doc.fieldtype == 'Dynamic Link') {
		cur_frm.fields_dict['options_help'].disp_area.innerHTML =
			__('Fieldname which will be the DocType for this link field.');
	} else {
		cur_frm.fields_dict['options_help'].disp_area.innerHTML = '';
	}
}


cur_frm.cscript.dt = function(doc, dt, dn) {
	if(!doc.dt) {
		set_field_options('insert_after', '');
		return;
	}
	var insert_after = doc.insert_after || null;
	return frappe.call({
		method: 'frappe.custom.doctype.custom_field.custom_field.get_fields_label',
		args: { doctype: doc.dt, fieldname: doc.fieldname },
		callback: function(r, rt) {
			set_field_options('insert_after', r.message);
			var fieldnames = $.map(r.message, function(v) { return v.value; });

			if(insert_after==null || !in_list(fieldnames, insert_after)) {
				insert_after = fieldnames[-1];
			}

			cur_frm.set_value('insert_after', insert_after);
		}
	});
}
