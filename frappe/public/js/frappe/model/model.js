// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.model');
frappe.provide("frappe.model.map_info");

$.extend(frappe.model, {
	no_value_type: ['Section Break', 'Column Break', 'HTML', 'Table', 
 	'Button', 'Image'],

	std_fields_list: ['name', 'owner', 'creation', 'modified', 'modified_by',
		'_user_tags', '_comments', 'docstatus', 'parent', 'parenttype', 'parentfield', 'idx'],
	std_fields: [
		{fieldname:'name', fieldtype:'Link', label:'ID'},
		{fieldname:'owner', fieldtype:'Data', label:'Created By'},
		{fieldname:'idx', fieldtype:'Int', label:'Index'},
		{fieldname:'creation', fieldtype:'Date', label:'Created On'},
		{fieldname:'modified', fieldtype:'Date', label:'Last Updated On'},
		{fieldname:'modified_by', fieldtype:'Data', label:'Last Updated By'},
		{fieldname:'_user_tags', fieldtype:'Data', label:'Tags'},
		{fieldname:'_comments', fieldtype:'Text', label:'Comments'},
		{fieldname:'docstatus', fieldtype:'Int', label:'Document Status'},
	],
	
	std_fields_table: [
		{fieldname:'parent', fieldtype:'Data', label:'Parent'},
	],

	new_names: {},
	events: {},

	get_std_field: function(fieldname) {
		var docfield = $.map([].concat(frappe.model.std_fields).concat(frappe.model.std_fields_table), 
			function(d) {
				if(d.fieldname==fieldname) return d;
			});
		if(!docfield.length) {
			msgprint("Unknown Column: " + fieldname);			
		}
		return docfield[0];
	},

	with_doctype: function(doctype, callback) {
		if(locals.DocType[doctype]) {
			callback();
		} else {
			var cached_timestamp = null;
			if(localStorage["_doctype:" + doctype]) {
				var cached_doclist = JSON.parse(localStorage["_doctype:" + doctype]);
				cached_timestamp = cached_doclist[0].modified;
			}
			return frappe.call({
				method:'frappe.widgets.form.load.getdoctype',
				type: "GET",
				args: {
					doctype: doctype,
					with_parent: 1,
					cached_timestamp: cached_timestamp
				},
				callback: function(r) {
					if(r.exc) {
						msgprint(frappe._("Unable to load") + ": " + frappe._(doctype));
						throw "No doctype";
						return;
					}
					if(r.message=="use_cache") {
						frappe.model.sync(cached_doclist);
					} else {
						localStorage["_doctype:" + doctype] = JSON.stringify(r.docs);
					}
					frappe.model.init_doctype(doctype);
					frappe.defaults.set_restrictions(r.restrictions);
					callback(r);
				}
			});
		}
	},
	
	init_doctype: function(doctype) {
		var meta = locals.DocType[doctype];
		if(meta.__list_js) {
			eval(meta.__list_js);
		}
		if(meta.__calendar_js) {
			eval(meta.__calendar_js);
		}
		if(meta.__map_js) {
			eval(meta.__map_js);
		}		
	},
	
	with_doc: function(doctype, name, callback) {
		if(!name) name = doctype; // single type
		if(locals[doctype] && locals[doctype][name] && frappe.model.get_docinfo(doctype, name)) {
			callback(name);
		} else {
			return frappe.call({
				method: 'frappe.widgets.form.load.getdoc',
				type: "GET",
				args: {
					doctype: doctype,
					name: name
				},
				callback: function(r) { callback(name, r); }
			});
		}
	},
	
	get_docinfo: function(doctype, name) {
		return frappe.model.docinfo[doctype] && frappe.model.docinfo[doctype][name] || null;
	},
	
	get_server_module_name: function(doctype) {
		var dt = frappe.model.scrub(doctype)
		return frappe.model.scrub(locals.DocType[doctype].module)
			+ '.doctype.' + dt + '.' + dt;
	},
	
	scrub: function(txt) {
		return txt.replace(/ /g, "_").toLowerCase();
	},

	can_create: function(doctype) {
		return frappe.boot.profile.can_create.indexOf(doctype)!==-1;
	},
	
	can_read: function(doctype) {
		return frappe.boot.profile.can_read.indexOf(doctype)!==-1;
	},

	can_write: function(doctype) {
		return frappe.boot.profile.can_write.indexOf(doctype)!==-1;
	},

	can_get_report: function(doctype) {
		return frappe.boot.profile.can_get_report.indexOf(doctype)!==-1;
	},
	
	can_delete: function(doctype) {
		if(!doctype) return false;
		return frappe.boot.profile.can_delete.indexOf(doctype)!==-1;
	},

	can_cancel: function(doctype) {
		if(!doctype) return false;
		return frappe.boot.profile.can_cancel.indexOf(doctype)!==-1;
	},
	
	is_submittable: function(doctype) {
		if(!doctype) return false;
		return locals.DocType[doctype] && locals.DocType[doctype].is_submittable;
	},
	
	can_import: function(doctype, frm) {
		// system manager can always import
		if(user_roles.indexOf("System Manager")!==-1) return true;
		
		if(frm) return frm.perm[0].import===1;
		return frappe.boot.profile.can_import.indexOf(doctype)!==-1;
	},
	
	can_export: function(doctype, frm) {
		// system manager can always export
		if(user_roles.indexOf("System Manager")!==-1) return true;
		
		if(frm) return frm.perm[0].export===1;
		return frappe.boot.profile.can_export.indexOf(doctype)!==-1;
	},
	
	can_print: function(doctype, frm) {
		if(frm) return frm.perm[0].print===1;
		return frappe.boot.profile.can_print.indexOf(doctype)!==-1;
	},
	
	can_email: function(doctype, frm) {
		if(frm) return frm.perm[0].email===1;
		return frappe.boot.profile.can_email.indexOf(doctype)!==-1;
	},
	
	can_restrict: function(doctype, frm) {
		// system manager can always restrict
		if(user_roles.indexOf("System Manager")!==-1) return true;
		
		if(frm) return frm.perm[0].restrict===1;
		return frappe.boot.profile.can_restrict.indexOf(doctype)!==-1;
	},
	
	has_value: function(dt, dn, fn) {
		// return true if property has value
		var val = locals[dt] && locals[dt][dn] && locals[dt][dn][fn];
		var df = frappe.meta.get_docfield(dt, fn, dn);
		
		if(df.fieldtype=='Table') {
			var ret = false;
			$.each(locals[df.options] || {}, function(k,d) {
				if(d.parent==dn && d.parenttype==dt && d.parentfield==df.fieldname) {
					ret = true;
					return false;
				}
			});
		} else {
			var ret = !is_null(val);
		}
		return ret ? true : false;
	},

	get: function(doctype, filters) {
		var src = locals[doctype] || locals[":" + doctype] || [];
		if($.isEmptyObject(src)) 
			return [];
		return frappe.utils.filter_dict(src, filters);
	},
	
	get_value: function(doctype, filters, fieldname) {
		if(typeof filters==="string") {
			return locals[doctype] && locals[doctype][filters] 
				&& locals[doctype][filters][fieldname];
		} else {
			var l = frappe.model.get(doctype, filters);
			return (l.length && l[0]) ? l[0][fieldname] : null;
		}
	},
	
	set_value: function(doctype, name, fieldname, value, fieldtype) {
		/* help: Set a value locally (if changed) and execute triggers */
		if(!name) name = doctype;
		var doc = locals[doctype] && locals[doctype][name] || null;
		
		if(doc && doc[fieldname] !== value) {
			doc[fieldname] = value;
			frappe.model.trigger(fieldname, value, doc); 
			return true;
		} else {
			// execute link triggers (want to reselect to execute triggers)
			if(fieldtype=="Link")
				frappe.model.trigger(fieldname, value, doc);
		}
	},
	
	on: function(doctype, fieldname, fn) {
		/* help: Attach a trigger on change of a particular field.
		To trigger on any change in a particular doctype, use fieldname as "*"
		*/
		/* example: frappe.model.on("Customer", "age", function(fieldname, value, doc) {
		  if(doc.age < 16) {
		    msgprint("Warning, Customer must atleast be 16 years old.");
		    raise "CustomerAgeError";
		  }
		}) */
		frappe.provide("frappe.model.events." + doctype);
		if(!frappe.model.events[doctype][fieldname]) {
			frappe.model.events[doctype][fieldname] = [];
		}
		frappe.model.events[doctype][fieldname].push(fn);
	},
	
	trigger: function(fieldname, value, doc) {

		var run = function(events, event_doc) {
			$.each(events || [], function(i, fn) {
				fn && fn(fieldname, value, event_doc || doc);
			});
		};
				
		if(frappe.model.events[doc.doctype]) {
						
			// field-level
			run(frappe.model.events[doc.doctype][fieldname]);

			// doctype-level
			run(frappe.model.events[doc.doctype]['*']);
		};
	},
	
	get_doc: function(doctype, name) {
		return locals[doctype] ? locals[doctype][name] : null;
	},
	
	get_doclist: function(doctype, name, filters) {
		var doclist = [];
		if(!locals[doctype]) 
			return doclist;

		doclist[0] = locals[doctype][name];

		$.each(frappe.model.get("DocField", {parent:doctype, fieldtype:"Table"}), 
			function(i, table_field) {
				var child_doclist = frappe.model.get(table_field.options, {
					parent:name, parenttype: doctype,
					parentfield: table_field.fieldname});
				
				if($.isArray(child_doclist)) {
					child_doclist.sort(function(a, b) { return a.idx - b.idx; });
					doclist = doclist.concat(child_doclist);
				}
			}
		);
		
		if(filters) {
			doclist = frappe.utils.filter_dict(doclist, filters);
		}
		
		return doclist;
	},

	get_children: function(doctype, parent, parentfield, parenttype) { 
		if(parenttype) {
			var l = frappe.model.get(doctype, {parent:parent, 
				parentfield:parentfield, parenttype:parenttype});
		} else {
			var l = frappe.model.get(doctype, {parent:parent, 
				parentfield:parentfield});
		}

		if(l.length) {
			l.sort(function(a,b) { return flt(a.idx) - flt(b.idx) }); 
			
			// renumber
			$.each(l, function(i, v) { v.idx = i+1; }); // for chrome bugs ???
		}
		return l; 
	},

	clear_doclist: function(doctype, name) {
		$.each(frappe.model.get_doclist(doctype, name), function(i, d) {
			if(d) frappe.model.clear_doc(d.doctype, d.name);
		});
	},
	
	clear_table: function(doctype, parenttype, parent, parentfield) {
		$.each(locals[doctype] || {}, function(i, d) {
			if(d.parent===parent && d.parenttype===parenttype && d.parentfield===parentfield) {
				delete locals[doctype][d.name];
			}
		})
	},

	remove_from_locals: function(doctype, name) {
		this.clear_doclist(doctype, name);
		if(frappe.views.formview[doctype]) {
			delete frappe.views.formview[doctype].frm.opendocs[name];
		}
	},

	clear_doc: function(doctype, name) {
		var doc = locals[doctype][name];
		
		if(doc && doc.parenttype) {
			var parent = doc.parent,
				parenttype = doc.parenttype,
				parentfield = doc.parentfield;
		}
		delete locals[doctype][name];
		if(parent)
			frappe.model.get_children(doctype, parent, parentfield, parenttype);
	},
	
	get_no_copy_list: function(doctype) {
		var no_copy_list = ['name','amended_from','amendment_date','cancel_reason'];
		$.each(frappe.model.get("DocField", {parent:doctype}), function(i, df) {
			if(cint(df.no_copy)) no_copy_list.push(df.fieldname);
		})
		return no_copy_list;
	},

	// args: source (doclist), target (doctype), table_map, field_map, callback
	map: function(args) {
		frappe.model.with_doctype(args.target, function() {
			var map_info = frappe.model.map_info[args.target]
			if(map_info) 
				map_info = map_info[args.source[0].doctype];
			if(!map_info) {
				map_info = {
					table_map: args.table_map || {},
					field_map: args.field_map || {}
				}
			}
			
			// main
			var target = frappe.model.map_doc(args.source[0], args.target, map_info.field_map[args.target]);
			
			// children
			$.each(map_info.table_map, function(child_target, child_source) {
				$.each($.map(args.source, function(d) 
					{ if(d.doctype==child_source) return d; else return null; }), function(i, d) {
						var child = frappe.model.map_doc(d, child_target, map_info.field_map[child_target]);
						$.extend(child, {
							parent: target.name,
							parenttype: target.doctype,
							parentfield: frappe.meta.get_parentfield(target.doctype, child.doctype),
							idx: i+1
						});
				});
			});
			
			if(args.callback) {
				args.callback(target);
			} else {
				frappe.set_route("Form", target.doctype, target.name);
			}
		});
	},
	
	// map a single doc to a new doc of given DocType and field_map
	map_doc: function(source, doctype, field_map) {
		var new_doc = frappe.model.get_new_doc(doctype);
		var no_copy_list = frappe.model.get_no_copy_list(doctype);
		if(!field_map) field_map = {};
		delete no_copy_list[no_copy_list.indexOf("name")];
		
		for(fieldname in frappe.meta.docfield_map[doctype]) {
			var df = frappe.meta.docfield_map[doctype][fieldname];
			if(!df.no_copy) {
				var source_key = field_map[df.fieldname] || df.fieldname;
				if(source_key.substr(0,1)=="=") {
					var value = source_key.substr(1);
				} else {
					var value = source[source_key];
				}
				if(value!==undefined) {
					new_doc[df.fieldname] = value;
				}
			}
		}
		return new_doc;
	},
	
	delete_doc: function(doctype, docname, callback) {
		frappe.confirm("Permanently delete "+ docname + "?", function() {
			return frappe.call({
				method: 'frappe.client.delete',
				args: {
					doctype: doctype, 
					name: docname
				},
				callback: function(r, rt) {
					if(!r.exc) {
						frappe.model.clear_doclist(doctype, docname);
						if(frappe.ui.toolbar.recent) 
							frappe.ui.toolbar.recent.remove(doctype, docname);
						if(callback) callback(r,rt);
					}
				}
			})
		})
	},
	
	rename_doc: function(doctype, docname, callback) {
		var d = new frappe.ui.Dialog({
			title: "Rename " + docname,
			fields: [
				{label:"New Name", fieldtype:"Data", reqd:1},
				{label:"Merge with existing", fieldtype:"Check", fieldname:"merge"},
				{label:"Rename", fieldtype: "Button"}
			]
		});
		d.get_input("rename").on("click", function() {
			var args = d.get_values();
			if(!args) return;
			d.get_input("rename").set_working();
			return frappe.call({
				method:"frappe.model.rename_doc.rename_doc",
				args: {
					doctype: doctype,
					old: docname,
					"new": args.new_name,
					"merge": args.merge
				},
				callback: function(r,rt) {
					d.get_input("rename").done_working();
					if(!r.exc) {
						$(document).trigger('rename', [doctype, docname,
							r.message || args.new_name]);
						if(locals[doctype] && locals[doctype][docname])
							delete locals[doctype][docname];
						d.hide();
						if(callback)
							callback(r.message);
					}
				}
			});
		});
		d.show();
	},
	
	round_floats_in: function(doc, fieldnames) {
		if(!fieldnames) {
			fieldnames = frappe.meta.get_fieldnames(doc.doctype, doc.name, 
				{"fieldtype": ["in", ["Currency", "Float"]]});
		}
		$.each(fieldnames, function(i, fieldname) {
			doc[fieldname] = flt(doc[fieldname], precision(fieldname, doc));
		});
	},
	
	validate_missing: function(doc, fieldname) {
		if(!doc[fieldname]) {
			frappe.throw(frappe._("Please specify") + ": " + 
				frappe._(frappe.meta.get_label(doc.doctype, fieldname, doc.parent || doc.name)));
		}
	}
});

// legacy
getchildren = frappe.model.get_children
make_doclist = frappe.model.get_doclist
