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

wn.provide('wn.meta.docfield_map');
wn.provide('wn.meta.docfield_copy');
wn.provide('wn.meta.docfield_list');
wn.provide('wn.meta.doctypes');
wn.provide("wn.meta.precision_map");

$.extend(wn.meta, {
	// build docfield_map and docfield_list
	add_field: function(df) {
		wn.provide('wn.meta.docfield_map.' + df.parent);
		wn.meta.docfield_map[df.parent][df.fieldname || df.label] = df;
		
		if(!wn.meta.docfield_list[df.parent])
			wn.meta.docfield_list[df.parent] = [];
			
		// check for repeat
		for(var i in wn.meta.docfield_list[df.parent]) {
			var d = wn.meta.docfield_list[df.parent][i];
			if(df.fieldname==d.fieldname) 
				return; // no repeat
		}
		wn.meta.docfield_list[df.parent].push(df);
	},
	
	make_docfield_copy_for: function(doctype, docname) {
		var c = wn.meta.docfield_copy;
		if(!c[doctype]) 
			c[doctype] = {};
		if(!c[doctype][docname]) 
			c[doctype][docname] = {};
			
		$.each(wn.meta.docfield_list[doctype], function(i, df) {
			c[doctype][docname][df.fieldname || df.label] = copy_dict(df);
		})
	},
	
	get_docfield: function(dt, fn, dn) {
		if(dn && wn.meta.docfield_copy[dt] && wn.meta.docfield_copy[dt][dn]){
			return wn.meta.docfield_copy[dt][dn][fn];
		} else {
			return wn.meta.docfield_map[dt][fn];
		}
	},
	
	get_print_formats: function(doctype) {
		// if default print format is given, use it
		var print_format_list = [];
		if(locals.DocType[doctype].default_print_format)
			print_format_list.push(locals.DocType[doctype].default_print_format)
		
		if(!in_list(print_format_list, "Standard"))
			print_format_list.push("Standard");
		
		var print_formats = wn.model.get("Print Format", {doc_type: doctype})
			.sort(function(a, b) { return (a > b) ? 1 : -1; });
		$.each(print_formats, function(i, d) {
			if(!in_list(print_format_list, d.name))
				print_format_list.push(d.name);
		});
		
		return print_format_list;
	},
	
	get_precision_map: function(doctype) {
		if(!wn.meta.precision_map[doctype]) {
			wn.meta.precision_map[doctype] = {};
			
			var fields = wn.model.get("DocField", {parent:doctype, fieldtype: "Currency"})
				.concat(wn.model.get("DocField", {parent: doctype, fieldtype: "Float"}));
			
			
			$.each(fields, function(i, df) {
				wn.meta.precision_map[doctype][df.fieldname] = df.precision;
			});
		}
		
		return wn.meta.precision_map[doctype];
	},

	sync_messages: function(doc) {
		if(doc.__messages) {
			$.extend(wn._messages, doc.__messages);
		}
	},
	
	get_field_currency: function(df, doc) {
		var currency = wn.boot.sysdefaults.currency;
		
		if(!doc && cur_frm) 
			doc = cur_frm.doc;
			
		if(df && df.options) {
			if(df.options.indexOf(":")!=-1) {
				var options = df.options.split(":");
				if(options.length==3) {
					// get reference record e.g. Company
					currency = wn.model.get_value(options[0], doc[options[1]], 
						options[2]) || currency;
				}
			} else if(doc && doc[df.options]) {
				currency = doc[df.options];
			} else if(cur_frm && cur_frm.doc[df.options]) {
				currency = cur_frm.doc[df.options];
			}
		}
		return currency;
	}

});