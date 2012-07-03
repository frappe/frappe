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

// Client Side Scripting API
// ======================================================================================

$c_get_values = function(args, doc, dt, dn, user_callback) {
	var call_back = function(r,rt) {
		if(!r.message)return;
		if(user_callback) user_callback(r.message);
		
		var fl = args.fields.split(',');
		for(var i in fl) {
			locals[dt][dn][fl[i]] = r.message[fl[i]]; // set value
			if(args.table_field)
				refresh_field(fl[i], dn, args.table_field);
			else
				refresh_field(fl[i]);
		}
	}
	$c('webnotes.widgets.form.utils.get_fields',args,call_back);
}

get_server_fields = function(method, arg, table_field, doc, dt, dn, allow_edit, call_back) {
	if(!allow_edit)freeze('Fetching Data...');
	$c('runserverobj', args={'method':method, 'docs':compress_doclist(make_doclist(doc.doctype, doc.name)), 'arg':arg},
	function(r, rt) {
		if (r.message)  {
			var d = locals[dt][dn];
			var field_dict = r.message;
			for(var key in field_dict) {
				d[key] = field_dict[key];
				if (table_field) refresh_field(key, d.name, table_field);
				else refresh_field(key);
			}
		}
		if(call_back){
			doc = locals[doc.doctype][doc.name];
			call_back(doc, dt, dn);
		}
		if(!allow_edit)unfreeze();
    }
  );
}

set_multiple = function (dt, dn, dict, table_field) {
	var d = locals[dt][dn];
	for(var key in dict) {
		d[key] = dict[key];
	    if (table_field)	refresh_field(key, d.name, table_field);     
		else 				refresh_field(key);	
	}
}

refresh_many = function (flist, dn, table_field) {
	for(var i in flist) {
		if (table_field) refresh_field(flist[i], dn, table_field);
		else refresh_field(flist[i]);
	}
}

set_field_tip = function(n,txt) {
	var df = get_field(cur_frm.doctype, n, cur_frm.docname);
	if(df)df.description = txt;

	if(cur_frm && cur_frm.fields_dict) {
		if(cur_frm.fields_dict[n])
			cur_frm.fields_dict[n].comment_area.innerHTML = replace_newlines(txt);
		else
			errprint('[set_field_tip] Unable to set field tip: ' + n);
	}
}

refresh_field = function(n, docname, table_field) {
	// multiple
	if(typeof n==typeof []) refresh_many(n, docname, table_field);
	
	if(table_field) { // for table
		if(_f.frm_dialog && _f.frm_dialog.display) {
			// in dialog
			if(_f.frm_dialog.cur_frm.fields_dict[n] && _f.frm_dialog.cur_frm.fields_dict[n].refresh)
				_f.frm_dialog.cur_frm.fields_dict[n].refresh();
		} else {
			var g = _f.cur_grid_cell;
			if(g) var hc = g.grid.head_row.cells[g.cellIndex];
			
			if(g && hc && hc.fieldname==n && g.row.docname==docname) {
				hc.template.refresh(); // if active
			} else {
				cur_frm.fields_dict[table_field].grid.refresh_cell(docname, n);
			}
		}
	} else if(cur_frm && cur_frm.fields_dict) {
		if(cur_frm.fields_dict[n] && cur_frm.fields_dict[n].refresh)
			cur_frm.fields_dict[n].refresh();
	}
}

set_field_options = function(n, txt) {
	var df = get_field(cur_frm.doctype, n, cur_frm.docname);
	if(df)df.options = txt;
	refresh_field(n);
}

set_field_permlevel = function(n, level) {
	var df = get_field(cur_frm.doctype, n, cur_frm.docname);
	if(df)df.permlevel = level;
	refresh_field(n);
}

hide_field = function(n) {
	function _hide_field(n,hidden) {
		var df = get_field(cur_frm.doctype, n, cur_frm.docname);
		if(df) { df.hidden = hidden; refresh_field(n); }
		else { console.log("hide_field cannot find field " + n); }
	}	
	if(cur_frm) {
		if(n.substr) _hide_field(n,1);
		else { for(var i in n)_hide_field(n[i],1) }
	}
}

unhide_field = function(n) {
	function _hide_field(n,hidden) {
		var df = get_field(cur_frm.doctype, n, cur_frm.docname);
		if(df) {df.hidden = hidden; refresh_field(n); }
		else { console.log("unhide_field cannot find field " + n); }
	}	
	if(cur_frm) {
		if(n.substr) _hide_field(n,0);
		else { for(var i in n)_hide_field(n[i],0) }
	}
}

get_field_obj = function(fn) {
	return cur_frm.fields_dict[fn];
}
