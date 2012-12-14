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

wn.provide('wn.model');

$.extend(wn.model, {
	no_value_type: ['Section Break', 'Column Break', 'HTML', 'Table', 
 	'Button', 'Image'],

	std_fields_list: ['name', 'owner', 'creation', 'modified', 'modified_by',
		'_user_tags', 'docstatus', 'parent', 'parenttype', 'parentfield', 'idx'],
	std_fields: [
		{fieldname:'name', fieldtype:'Link', label:'ID'},
		{fieldname:'owner', fieldtype:'Data', label:'Created By'},
		{fieldname:'creation', fieldtype:'Date', label:'Created On'},
		{fieldname:'modified', fieldtype:'Date', label:'Last Updated On'},
		{fieldname:'modified_by', fieldtype:'Date', label:'Last Updated By'},
		{fieldname:'_user_tags', fieldtype:'Data', label:'Tags'},
		{fieldname:'docstatus', fieldtype:'Int', label:'Document Status'},
	],
	
	std_fields_table: [
		{fieldname:'parent', fieldtype:'Data', label:'Parent'},
		{fieldname:'idx', fieldtype:'Int', label:'Row No.'},
	],

	new_names: {},

	get_std_field: function(fieldname) {
		var docfield = $.map([].concat(wn.model.std_fields).concat(wn.model.std_fields_table), 
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
			wn.call({
				method:'webnotes.widgets.form.load.getdoctype',
				args: {
					doctype: doctype
				},
				callback: callback
			});
		}
	},
	
	with_doc: function(doctype, name, callback) {
		if(!name) name = doctype; // single type
		if(locals[doctype] && locals[doctype][name]) {
			callback(name);
		} else {
			wn.call({
				method: 'webnotes.widgets.form.load.getdoc',
				args: {
					doctype: doctype,
					name: name
				},
				callback: function(r) { callback(name, r); }
			});
		}
	},
	
	get_server_module_name: function(doctype) {
		var dt = wn.model.scrub(doctype)
		return wn.model.scrub(locals.DocType[doctype].module)
			+ '.doctype.' + dt + '.' + dt;
	},
	
	scrub: function(txt) {
		return txt.replace(/ /g, "_").toLowerCase();
	},

	can_create: function(doctype) {
		return wn.boot.profile.can_create.indexOf(doctype)!=-1;
	},
	
	can_read: function(doctype) {
		return wn.boot.profile.can_read.indexOf(doctype)!=-1;
	},

	can_write: function(doctype) {
		return wn.boot.profile.can_write.indexOf(doctype)!=-1;
	},

	can_delete: function(doctype) {
		if(!doctype) return false;
		return wn.boot.profile.can_cancel.indexOf(doctype)!=-1;
	},
	
	has_value: function(dt, dn, fn) {
		// return true if property has value
		var val = locals[dt] && locals[dt][dn] && locals[dt][dn][fn];
		var df = wn.meta.get_docfield(dt, fn, dn);
		
		if(df.fieldtype=='Table') {
			var ret = false;
			$.each(locals[df.options] || {}, function(k,d) {
				if(d.parent==dn && d.parenttype==dt && d.parentfield==df.fieldname) {
					ret = true;
				}
			});
		} else {
			var ret = !is_null(val);			
		}
		return ret ? true : false;
	},

	get: function(doctype, filters) {
		if(!locals[doctype]) return [];
		return wn.utils.filter_dict(locals[doctype], filters);
	},
	
	get_doc: function(doctype, name) {
		return locals[doctype] ? locals[doctype][name] : null;
	},
	
	get_doclist: function(doctype, name, filters) {
		var doclist = [];
		if(!locals[doctype]) 
			return doclist;

		doclist[0] = locals[doctype][name];

		$.each(wn.model.get("DocField", {parent:doctype, fieldtype:"Table"}), 
			function(i, table_field) {
				var child_doclist = wn.model.get(table_field.options, {
					parent:name, parenttype: doctype,
					parentfield: table_field.fieldname}).sort(
						function(a, b) { return a.idx - b.idx; });
				doclist = doclist.concat(child_doclist);
			}
		);
		
		if(filters) {
			doclist = wn.utils.filter_dict(doclist, filters);
		}
		
		return doclist;
	},

	get_children: function(child_dt, parent, parentfield, parenttype) { 
		if(parenttype) {
			var l = wn.model.get(child_dt, {parent:parent, 
				parentfield:parentfield, parenttype:parenttype});
		} else {
			var l = wn.model.get(child_dt, {parent:parent, 
				parentfield:parentfield});				
		}

		l.sort(function(a,b) { return cint(a.idx) - cint(b.idx) }); 
		$.each(l, function(i, v) { v.idx = i+1; }); // for chrome bugs ???
		return l; 
	},

	clear_doclist: function(doctype, name) {
		$.each(wn.model.get_doclist(doctype, name), function(i, d) {
			if(d) wn.model.clear_doc(d.doctype, d.name);
		});
	},
	
	clear_doc: function(doctype, name) {
		delete locals[doctype][name];		
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
	
	delete_doc: function(doctype, docname, callback) {
		wn.confirm("Permanently delete "+ docname + "?", function() {
			wn.call({
				method: 'webnotes.model.delete_doc',
				args: {
					dt:doctype, 
					dn:docname
				},
				callback: function(r, rt) {
					if(!r.exc) {
						wn.model.clear_doclist(doctype, docname);
						if(wn.ui.toolbar.recent) 
							wn.ui.toolbar.recent.remove(doctype, docname);
						if(callback) callback(r,rt);
					}
				}
			})
		})
	},
	
	rename_doc: function(doctype, docname, callback) {
		var d = new wn.ui.Dialog({
			title: "Rename " + docname,
			fields: [
				{label:"New Name", fieldtype:"Data", reqd:1},
				{label:"Rename", fieldtype: "Button"}
			]
		});
		d.get_input("rename").on("click", function() {
			var args = d.get_values();
			if(!args) return;
			d.get_input("rename").set_working();
			wn.call({
				method:"webnotes.model.rename_doc.rename_doc",
				args: {
					doctype: doctype,
					old: docname,
					"new": args.new_name
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
	}
});

// legacy
getchildren = wn.model.get_children
make_doclist = wn.model.get_doclist