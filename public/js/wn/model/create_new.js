// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.provide("wn.model");

$.extend(wn.model, {
	new_names: {},
	new_name_count: {},

	get_new_doc: function(doctype, parent_doc) {
		wn.provide("locals." + doctype);
		var doc = {
			docstatus: 0,
			doctype: doctype,
			name: wn.model.get_new_name(doctype),
			__islocal: 1,
			__unsaved: 1,
			owner: user
		};
		wn.model.set_default_values(doc, parent_doc);
		locals[doctype][doc.name] = doc;
		wn.provide("wn.model.docinfo." + doctype + "." + doc.name);
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
	
	set_default_values: function(doc, parent_doc) {
		var doctype = doc.doctype;
		var docfields = wn.meta.docfield_list[doctype] || [];
		var updated = [];
		
		for(var fid=0;fid<docfields.length;fid++) {
			var f = docfields[fid];
			if(!in_list(wn.model.no_value_type, f.fieldtype) && doc[f.fieldname]==null) {
				var v = wn.model.get_default_value(f, doc, parent_doc);
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
	
	get_default_value: function(df, doc, parent_doc) {
		var def_vals = {
			"__user": user,
			"Today": dateutil.get_today(),
		}
		
		if(wn.defaults.get_user_default(df.fieldname))
			return wn.defaults.get_user_default(df.fieldname);
		else if(df["default"] && df["default"][0]===":")
			return wn.model.get_default_from_boot_docs(df, doc, parent_doc);
		else if(def_vals[df["default"]])
			return def_vals[df["default"]];
		else if(df.fieldtype=="Time" && (!df["default"]))
			return dateutil.get_cur_time()
		else if(df["default"] && df["default"][0]!==":")
			return df["default"];
	},
	
	get_default_from_boot_docs: function(df, doc, parent_doc) {
		// set default from partial docs passed during boot like ":Profile"
		if(wn.model.get(df["default"]).length > 0) {
			var ref_fieldname = df["default"].slice(1).toLowerCase().replace(" ", "_");
			var ref_value = parent_doc ? 
				parent_doc[ref_fieldname] :
				wn.defaults.get_user_default(ref_fieldname);
			var ref_doc = ref_value ? wn.model.get_doc(df["default"], ref_value) : null;
			
			if(ref_doc && ref_doc[df.fieldname]) {
				return ref_doc[df.fieldname];
			}
		}
	},
	
	add_child: function(parent_doc, doctype, parentfield, idx) {
		// create row doc
		idx = idx ?
			idx - 0.1 :
			wn.model.get_children(doctype, parent_doc.name, parentfield, 
				parent_doc.doctype).length + 1;

		var d = wn.model.get_new_doc(doctype, parent_doc);
		$.extend(d, {
			parent: parent_doc.name,
			parentfield: parentfield,
			parenttype: parent_doc.doctype,
			idx: idx
		});
				
		// renum for fraction
		idx !== cint(idx) && 
			wn.model.get_children(doctype, parent_doc.name, parentfield, 
				parent_doc.doctype);

		cur_frm && cur_frm.dirty();
				
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
	
	open_mapped_doc: function(opts) {
		return wn.call({
			type: "GET",
			method: opts.method,
			args: {
				"source_name": opts.source_name
			},
			callback: function(r) {
				if(!r.exc) {
					var doclist = wn.model.sync(r.message);
					wn.set_route("Form", doclist[0].doctype, doclist[0].name);
				}
			}
		})
	},

	map_current_doc: function(opts) {
		if(opts.get_query_filters) {
			opts.get_query = function() {
				return {filters: opts.get_query_filters};
			}
		}
		var _map = function() {
			return wn.call({
				type: "GET",
				method: opts.method,
				args: {
					"source_name": opts.source_name,
					"target_doclist": wn.model.get_doclist(cur_frm.doc.doctype, cur_frm.doc.name)
				},
				callback: function(r) {
					if(!r.exc) {
						var doclist = wn.model.sync(r.message);
						cur_frm.refresh();
					}
				}
			});
		}
		if(opts.source_doctype) {
			var d = new wn.ui.Dialog({
				title: wn._("Get From ") + wn._(opts.source_doctype),
				fields: [
					{
						"fieldtype": "Link", 
						"label": wn._(opts.source_doctype),
						"fieldname": opts.source_doctype, 
						"options": opts.source_doctype, 
						"get_query": opts.get_query,
						reqd:1},
					{
						"fieldtype": "Button",
						"label": wn._("Get"),
						click: function() {
							var values = d.get_values();
							if(!values) 
								return;
							opts.source_name = values[opts.source_doctype];
							d.hide();
							_map();
						}
					}
				]
			})
			d.show();
		} else if(opts.source_name) {
			_map();
		}
	}
})