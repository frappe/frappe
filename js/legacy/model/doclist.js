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

function compress_doclist(list) {
	var kl = {}; var vl = []; var flx = {};
	for(var i=0; i<list.length;i++) {
		var o = list[i];
		var fl = [];
		if(!kl[o.doctype]) { // make key only once # doctype must be first
			var tfl = ['doctype', 'name', 'docstatus', 'owner', 'parent', 'parentfield', 'parenttype', 'idx', 'creation', 'modified', 'modified_by', '__islocal', '__newname', '__modified', '_user_tags'];  // for text
			var fl = [].concat(tfl);
			
			for(key in wn.meta.docfield_map[o.doctype]) { // all other values
				if(!in_list(fl, key) 
					&& !in_list(no_value_fields, wn.meta.docfield_map[o.doctype][key].fieldtype)
					&& !wn.meta.docfield_map[o.doctype][key].no_column) {
						fl[fl.length] = key; // save value list
						tfl[tfl.length] = key //.replace(/'/g, "\\'").replace(/\n/g, "\\n");
					}
			}
			flx[o.doctype] = fl;
			kl[o.doctype] = tfl
		}
		var nl = [];
		var fl = flx[o.doctype];
		// check all
		for(var j=0;j<fl.length;j++) {
			var v = o[fl[j]];
			nl.push(v);
		}
		vl.push(nl);
	}
		
	return JSON.stringify({'_vl':vl, '_kl':kl});
}

function expand_doclist(docs) {
	var l = [];
	for(var i=0;i<docs._vl.length;i++) 
		l[l.length] = zip(docs._kl[docs._vl[i][0]], docs._vl[i]);
	return l;
}
function zip(k,v) {
	var obj = {};
	for(var i=0;i<k.length;i++) {
		obj[k[i]] = v[i];
	}
	return obj;
}

function save_doclist(dt, dn, save_action, onsave, onerr) {
	var doc = locals[dt][dn];
	var doctype = locals['DocType'][dt];
	
	var tmplist = [];
	
	// make doc list
	var doclist = make_doclist(dt, dn, 1);
	var all_reqd_ok = true;
	
	if(save_action!='Cancel') {
		for(var n in doclist) {
			// type / mandatory checking
			var reqd_ok = check_required(doclist[n].doctype, doclist[n].name, doclist[0].doctype);
			if(doclist[n].docstatus+''!='2' && all_reqd_ok) // if not deleted
				all_reqd_ok = reqd_ok;
		}
	}
	
	// mandatory not filled
	if(!all_reqd_ok) {
		onerr()
		return;
	}
		
	var _save = function() {
		//console.log(compress_doclist(doclist));
		$c('webnotes.widgets.form.save.savedocs', {'docs':compress_doclist(doclist), 'docname':dn, 'action': save_action, 'user':user }, 
			function(r, rtxt) {
				if(f){ f.savingflag = false;}
				if(r.saved) {
					if(onsave)onsave(r);
				} else {
					if(onerr)onerr(r);
				}
			}, function() {
				if(f){ f.savingflag = false; } /*time out*/ 
			},0,(f ? 'Saving...' : '')
		);
	}

	// ask for name
	if(doc.__islocal && (doctype && doctype.autoname && doctype.autoname.toLowerCase()=='prompt')) {
		var newname = prompt('Enter the name of the new '+ dt, '');
		if(newname) { 
				doc.__newname = strip(newname); _save();
		} else {
			msgprint('Not Saved'); onerr();
		}
	} else {
		_save();
	}
}

function check_required(dt, dn, parent_dt) {
	var doc = locals[dt][dn];
	if(doc.docstatus>1)return true;
	var fl = wn.meta.docfield_list[dt];
	
	if(!fl)return true; // no doctype loaded
	
	var all_clear = true;
	var errfld = [];
	for(var i=0;i<fl.length;i++) {
		var key = fl[i].fieldname;
		var v = doc[key];
				
		if(fl[i].reqd && is_null(v) && fl[i].fieldname) {
			errfld[errfld.length] = fl[i].label;
			
			// Bring to front "Section"
			if(cur_frm) {
				// show as red
				var f = cur_frm.fields_dict[fl[i].fieldname];
				if(f) {
					// in form
					if(f.set_as_error) f.set_as_error(1);
					
					// switch to section
					if(!cur_frm.error_in_section && f.parent_section) {
						cur_frm.error_in_section = 1;
					}
				}
			}
						
			if(all_clear)all_clear = false;
		}
	}
	if(errfld.length)msgprint('<b>Mandatory fields required in '+
	 	(doc.parenttype ? (wn.meta.docfield_map[doc.parenttype][doc.parentfield].label + ' (Table)') : get_doctype_label(doc.doctype)) +
		':</b>\n' + errfld.join('\n'));
	return all_clear;
}
