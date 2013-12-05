// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

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
			
		$.each(wn.meta.docfield_list[doctype] || [], function(i, df) {
			c[doctype][docname][df.fieldname || df.label] = copy_dict(df);
		})
	},
	
	get_docfield: function(dt, fn, dn) {
		return wn.meta.get_docfield_copy(dt, dn)[fn];
	},
	
	get_docfields: function(doctype, name, filters) {
		var docfield_map = wn.meta.get_docfield_copy(doctype, name);
		
		var docfields = wn.meta.sort_docfields(docfield_map);
		
		if(filters) {
			docfields = wn.utils.filter_dict(docfields, filters);
		}
		
		return docfields;
	},
	
	sort_docfields: function(docs) {
		return values(docs).sort(function(a, b) { return a.idx - b.idx });
	},
	
	get_docfield_copy: function(doctype, name) {
		if(!name) return wn.meta.docfield_map[doctype];
		
		if(!(wn.meta.docfield_copy[doctype] && wn.meta.docfield_copy[doctype][name])) {
			wn.meta.make_docfield_copy_for(doctype, name);
		}
		
		return wn.meta.docfield_copy[doctype][name];
	},
	
	get_fieldnames: function(doctype, name, filters) {
		return $.map(wn.utils.filter_dict(wn.meta.docfield_map[doctype], filters), 
			function(df) { return df.fieldname; });
	},
	
	has_field: function(dt, fn) {
		return wn.meta.docfield_map[dt][fn];
	},

	get_parentfield: function(parent_dt, child_dt) {
		var df = wn.model.get("DocField", {parent:parent_dt, fieldtype:"Table", 
			options:child_dt})
		if(!df.length) 
			throw "parentfield not found for " + parent_dt + ", " + child_dt;
		return df[0].fieldname;
	},
		
	get_label: function(dt, fn, dn) {
		if(fn==="owner") {
			return "Owner";
		} else {
			return this.get_docfield(dt, fn, dn).label || fn;
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
			if(doc && df.options.indexOf(":")!=-1) {
				var options = df.options.split(":");
				if(options.length==3) {
					// get reference record e.g. Company
					var docname = doc[options[1]];
					if(!docname && cur_frm) {
						docname = cur_frm.doc[options[1]];
					}
					currency = wn.model.get_value(options[0], docname, options[2]) || 
						wn.model.get_value(":" + options[0], docname, options[2]) || 
						currency;
				}
			} else if(doc && doc[df.options]) {
				currency = doc[df.options];
			} else if(cur_frm && cur_frm.doc[df.options]) {
				currency = cur_frm.doc[df.options];
			}
		}
		return currency;
	},
	
	get_field_precision: function(df, doc) {
		var precision = wn.defaults.get_default("float_precision") || 3;
		if(df && df.fieldtype === "Currency") {
			var currency = this.get_field_currency(df, doc);
			var number_format = get_number_format(currency);
			var number_format_info = get_number_format_info(number_format);
			precision = number_format_info.precision || precision;
		}
		return precision;
	},
});