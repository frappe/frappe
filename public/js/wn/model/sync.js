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

$.extend(wn.model, {
	docinfo: {},
	sync: function(r) {
		/* docs:
			extract doclist, docinfo (attachments, comments, assignments)
			from incoming request and set in `locals` and `wn.model.docinfo`
		*/
		var doclist = r.docs ? r.docs : r;

		if(doclist._kl)
			doclist = wn.model.expand(doclist);

		if(doclist && doclist.length)
			wn.model.clear_doclist(doclist[0].doctype, doclist[0].name)

		$.each(doclist, function(i, d) {
			if(!d.name) { // get name (local if required)
				d.name = wn.model.get_new_name(d.doctype);
				wn.provide("wn.model.docinfo." + d.doctype + "." + d.name);	
			}
				
			if(!locals[d.doctype])
				locals[d.doctype] = {};

			locals[d.doctype][d.name] = d;
			d.__last_sync_on = new Date();

			if(cur_frm && cur_frm.doctype==d.doctype && cur_frm.docname==d.name) {
				cur_frm.doc = d;
			}

			if(d.doctype=='DocField') wn.meta.add_field(d);
			if(d.doctype=='DocType') wn.meta.sync_messages(d);

			if(d.localname) {
				wn.model.new_names[d.localname] = d.name;
				$(document).trigger('rename', [d.doctype, d.localname, d.name]);
				delete locals[d.doctype][d.localname];
				
				// update docinfo to new dict keys
				if(i===0) {
					wn.model.docinfo[d.doctype][d.name] = wn.model.docinfo[d.doctype][d.localname];
					wn.model.docinfo[d.doctype][d.localname] = undefined;
				}
			}
		});
		
		// set docinfo
		if(r.docinfo) {
			var doc = doclist[0]
			if(!wn.model.docinfo[doc.doctype])
				wn.model.docinfo[doc.doctype] = {};
			wn.model.docinfo[doc.doctype][doc.name] = r.docinfo;
		}
		
		return doclist;
	},
	
	expand: function(data) {
		function zip(k,v) {
			var obj = {};
			for(var i=0;i<k.length;i++) {
				obj[k[i]] = v[i];
			}
			return obj;
		}

		var l = [];
		for(var i=0;i<data._vl.length;i++) {
			l.push(zip(data._kl[data._vl[i][0]], data._vl[i]));
		}
		return l;
	},
	
	compress: function(doclist) {
		var all_keys = {}; var values = [];
		
		function get_key_list(doctype) {
			// valid standard keys
			var key_list = ['doctype', 'name', 'docstatus', 'owner', 'parent', 
				'parentfield', 'parenttype', 'idx', 'creation', 'modified', 
				'modified_by', '__islocal', '__newname', '__modified', 
				'_user_tags', '__temp'];

			for(key in wn.meta.docfield_map[doctype]) { // all other values
				if(!in_list(key_list, key) 
					&& !in_list(wn.model.no_value_type, wn.meta.docfield_map[doctype][key].fieldtype)
					&& !wn.meta.docfield_map[doctype][key].no_column) {
						key_list[key_list.length] = key
					}
			}
			return key_list;
		}
		
		for(var i=0; i<doclist.length;i++) {
			var doc = doclist[i];
			
			// make keys
			if(!all_keys[doc.doctype]) { 
				all_keys[doc.doctype] = get_key_list(doc.doctype);
				// doctype must be first
			}
			
			var row = []
			var key_list = all_keys[doc.doctype];
			
			// make data rows
			for(var j=0;j<key_list.length;j++) {
				row.push(doc[key_list[j]]);
			}
			
			values.push(row);
		}

		return JSON.stringify({'_vl':values, '_kl':all_keys});
	}	
});

// legacy
compress_doclist = wn.model.compress;