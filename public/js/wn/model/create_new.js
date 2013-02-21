wn.provide("wn.model");

$.extend(wn.model, {
	new_names: {},
	new_name_count: {},

	get_new_doc: function(doctype) {
		wn.provide("locals." + doctype);
		var doc = {
			docstatus: 0,
			doctype: doctype,
			name: wn.model.get_new_name(doctype),
			__islocal: 1,
			owner: user
		};
		wn.model.set_default_values(doc);
		locals[doctype][doc.name] = doc;
		return doc;		
	},
	
	make_new_doc_and_get_name: function(doctype) {
		return wn.model.get_new_doc(doctype).name;
	},
	
	get_new_name: function(doctype) {
		var cnt = wn.model.new_name_count
		if(!cnt[doctype]) 
			cnt[doctype] = 0;
		cnt[doctype]++;
		return 'New '+ doctype + ' ' + cnt[doctype];
	},
	
	set_default_values: function(doc) {
		var doctype = doc.doctype;
		var docfields = wn.meta.docfield_list[doctype] || [];
		var updated = [];
		
		for(var fid=0;fid<docfields.length;fid++) {
			var f = docfields[fid];
			if(!in_list(no_value_fields, f.fieldtype) && doc[f.fieldname]==null) {
				var v = wn.model.get_default_value(f);
				if(v) {
					if(in_list(["Int", "Check"], f.fieldtype))
						v = cint(v);
					else if(in_list(["Currency", "Float"], f.fieldtype))
						v = flt(v);
					
					doc[f.fieldname] = v;
					updated.push(f.fieldname);
				}
			}
		}
		return updated;
	},
	
	get_default_value: function(df) {
		var def_vals = {
			"_Login": user,
			"__user": user,
			"Today": dateutil.get_today(),
			"__today": dateutil.get_today(),
			"Now": dateutil.get_cur_time()
		}
		
		if(def_vals[df["default"]])
			return def_vals[df["default"]];
		else if(df.fieldtype=="Time" && (!df["default"]))
			return dateutil.get_cur_time()
		else if(df["default"])
			return df["default"];
		else if(wn.defaults.get_user_default(df.fieldname))
			return wn.defaults.get_user_default(df.fieldname);
	},
	
	add_child: function(doc, childtype, parentfield) {
		// create row doc
		var d = wn.model.get_new_doc(childtype);
		$.extend(d, {
			parent: doc.name,
			parentfield: parentfield,
			parenttype: doc.doctype,
			idx: getchildren(childtype, d.parent, d.parentfield, d.parenttype).length 
		});
		return d;
	},
	
	copy_doc: function(dt, dn, from_amend) {
		var no_copy_list = ['name','amended_from','amendment_date','cancel_reason'];
		var newdoc = wn.model.get_new_doc(dt);

		for(var key in locals[dt][dn]) {
			// dont copy name and blank fields
			var df = wn.meta.get_docfield(dt, key);
			
			if(key.substr(0,2)!='__' 
				&& !in_list(no_copy_list, key) 
				&& !(df && (!from_amend && cint(df.no_copy)==1))) { 
				newdoc[key] = locals[dt][dn][key];
			}
		}
		return newdoc;
	},
	
})