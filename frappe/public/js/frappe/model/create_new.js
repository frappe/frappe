// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.model");

$.extend(frappe.model, {
	new_names: {},
	new_name_count: {},

	get_new_doc: function(doctype, parent_doc) {
		frappe.provide("locals." + doctype);
		var doc = {
			docstatus: 0,
			doctype: doctype,
			name: frappe.model.get_new_name(doctype),
			__islocal: 1,
			__unsaved: 1,
			owner: user
		};
		frappe.model.set_default_values(doc, parent_doc);
		locals[doctype][doc.name] = doc;
		frappe.provide("frappe.model.docinfo." + doctype + "." + doc.name);
		return doc;
	},
	
	make_new_doc_and_get_name: function(doctype) {
		return frappe.model.get_new_doc(doctype).name;
	},
	
	get_new_name: function(doctype) {
		var cnt = frappe.model.new_name_count
		if(!cnt[doctype]) 
			cnt[doctype] = 0;
		cnt[doctype]++;
		return frappe._('New') + ' '+ frappe._(doctype) + ' ' + cnt[doctype];
	},
	
	set_default_values: function(doc, parent_doc) {
		var doctype = doc.doctype;
		var docfields = frappe.meta.docfield_list[doctype] || [];
		var updated = [];
		
		for(var fid=0;fid<docfields.length;fid++) {
			var f = docfields[fid];
			if(!in_list(frappe.model.no_value_type, f.fieldtype) && doc[f.fieldname]==null) {
				var v = frappe.model.get_default_value(f, doc, parent_doc);
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
		
		var restrictions = frappe.defaults.get_restrictions();
		if(df.fieldtype==="Link" && restrictions
			&& df.ignore_restrictions != 1
			&& restrictions[df.options] 
			&& (restrictions[df.options].length===1))
			return restrictions[df.options][0];
		else if(frappe.defaults.get_user_default(df.fieldname))
			return frappe.defaults.get_user_default(df.fieldname);
		else if(df["default"] && df["default"][0]===":")
			return frappe.model.get_default_from_boot_docs(df, doc, parent_doc);
		else if(def_vals[df["default"]])
			return def_vals[df["default"]];
		else if(df.fieldtype=="Time" && (!df["default"]))
			return dateutil.get_cur_time()
		else if(df["default"] && df["default"][0]!==":")
			return df["default"];
	},
	
	get_default_from_boot_docs: function(df, doc, parent_doc) {
		// set default from partial docs passed during boot like ":User"
		if(frappe.model.get(df["default"]).length > 0) {
			var ref_fieldname = df["default"].slice(1).toLowerCase().replace(" ", "_");
			var ref_value = parent_doc ? 
				parent_doc[ref_fieldname] :
				frappe.defaults.get_user_default(ref_fieldname);
			var ref_doc = ref_value ? frappe.model.get_doc(df["default"], ref_value) : null;
			
			if(ref_doc && ref_doc[df.fieldname]) {
				return ref_doc[df.fieldname];
			}
		}
	},
	
	add_child: function(parent_doc, doctype, parentfield, idx) {
		// create row doc
		idx = idx ?
			idx - 0.1 :
			frappe.model.get_children(doctype, parent_doc.name, parentfield, 
				parent_doc.doctype).length + 1;

		var d = frappe.model.get_new_doc(doctype, parent_doc);
		$.extend(d, {
			parent: parent_doc.name,
			parentfield: parentfield,
			parenttype: parent_doc.doctype,
			idx: idx
		});
				
		// renum for fraction
		idx !== cint(idx) && 
			frappe.model.get_children(doctype, parent_doc.name, parentfield, 
				parent_doc.doctype);

		cur_frm && cur_frm.dirty();
				
		return d;
	},
	
	copy_doc: function(dt, dn, from_amend) {
		var no_copy_list = ['name','amended_from','amendment_date','cancel_reason'];
		var newdoc = frappe.model.get_new_doc(dt);

		for(var key in locals[dt][dn]) {
			// dont copy name and blank fields
			var df = frappe.meta.get_docfield(dt, key);
			
			if(key.substr(0,2)!='__' 
				&& !in_list(no_copy_list, key) 
				&& !(df && (!from_amend && cint(df.no_copy)==1))) { 
				newdoc[key] = locals[dt][dn][key];
			}
		}
		return newdoc;
	},
	
	open_mapped_doc: function(opts) {
		return frappe.call({
			type: "GET",
			method: opts.method,
			args: {
				"source_name": opts.source_name
			},
			callback: function(r) {
				if(!r.exc) {
					var doclist = frappe.model.sync(r.message);
					frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
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
			return frappe.call({
				type: "GET",
				method: opts.method,
				args: {
					"source_name": opts.source_name,
					"target_doclist": frappe.model.get_doclist(cur_frm.doc.doctype, cur_frm.doc.name)
				},
				callback: function(r) {
					if(!r.exc) {
						var doclist = frappe.model.sync(r.message);
						cur_frm.refresh();
					}
				}
			});
		}
		if(opts.source_doctype) {
			var d = new frappe.ui.Dialog({
				title: frappe._("Get From ") + frappe._(opts.source_doctype),
				fields: [
					{
						"fieldtype": "Link", 
						"label": frappe._(opts.source_doctype),
						"fieldname": opts.source_doctype, 
						"options": opts.source_doctype, 
						"get_query": opts.get_query,
						reqd:1},
					{
						"fieldtype": "Button",
						"label": frappe._("Get"),
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