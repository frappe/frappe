// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

wn.provide("wn.perm");

// backward compatibilty
var READ = "read", WRITE = "write", CREATE = "create"; 
var SUBMIT = "submit", CANCEL = "cancel", AMEND = "amend";

$.extend(wn.perm, {
	rights: ["read", "write", "create", "submit", "cancel", "amend",
		"report", "import", "export", "print", "email", "restrict"],
		
	doctype_perm: {},
	
	has_perm: function(doctype, permlevel, ptype, docname) {
		if(!permlevel) permlevel = 0;
		
		if(docname) {
			var perms = wn.perm.get_perm(doctype, docname);
		} else {
			if(!wn.perm.doctype_perm[doctype]) {
				wn.perm.doctype_perm[doctype] = wn.perm.get_perm(doctype);
			}
			var perms = wn.perm.doctype_perm[doctype];
		}
		
		if(!perms)
			return false;
			
		if(!perms[permlevel])
			return false;
			
		return !!perms[permlevel][ptype];
	},
	
	get_perm: function(doctype, docname) {
		var perm = [{read: 0}];
		
		var meta = wn.model.get_doc("DocType", doctype);
		if(!meta) {
			return perm;
		} else if(meta.istable) {
			// if a child table, use permissions of parent form
			var parent_df = wn.model.get("DocField", {fieldtype: "Table", options: doctype});
			if(parent_df.length) {
				if(docname) {
					docname = wn.model.get_doc(doctype, docname).parent;
				}
				doctype = parent_df[0].parent;
			}
		}
		
		if(user==="Administrator" || user_roles.indexOf("Administrator")!==-1) {
			perm[0].read = 1;
		}
		
		if(docname && !wn.perm.has_only_permitted_data(doctype, docname)) {
			// if has restricted data, return not permitted
			return perm;
		}
		
		var docperms = wn.model.get("DocPerm", {parent: doctype});
		$.each(docperms, function(i, p) {
			// if user has this role
			if(user_roles.indexOf(p.role)!==-1 && 
				(!docname || wn.perm.has_match(p, doctype, docname))) {
				var permlevel = cint(p.permlevel);
				if(!perm[permlevel]) {
					perm[permlevel] = {};
				}
				$.each(wn.perm.rights, function(i, key) {
					perm[permlevel][key] = perm[permlevel][key] || (p[key] || 0);
				});
			}
		});
		
		return perm;
	},
	
	has_only_permitted_data: function(doctype, docname) {
		var restrictions = wn.defaults.get_restrictions();
		if(!restrictions || $.isEmptyObject(restrictions)) {
			return true;
		}
		
		// prepare restricted fields
		var fields_to_check = wn.perm.get_restricted_fields(doctype, docname, restrictions);
		
		// loop and find if has restricted data
		var has_restricted_data = false;
		var doc = wn.model.get_doc(doctype, docname);
		$.each(fields_to_check, function(i, df) {
			if(doc[df.fieldname] && restrictions[df.options].indexOf(doc[df.fieldname])===-1) {
				has_restricted_data = true;
				return false;
			}
		});
		
		return !has_restricted_data;
	},
	
	get_restricted_fields: function(doctype, docname, restrictions) {
		var fields_to_check = wn.meta.get_restricted_fields(doctype, docname,
			Object.keys(restrictions));
		if(Object.keys(restrictions).indexOf(doctype)!==-1) {
			fields_to_check = fields_to_check.concat(
				{label: "Name", fieldname: name, options: doctype});
		}
		return fields_to_check;
	},
	
	has_match: function(docperm, doctype, docname) {
		if(!docperm.match) return true;
		if(docperm.match==="owner") {
			var doc = wn.model.get_doc(doctype, docname);
			if(doc.owner===user) {
				return true;
			}
		}
		return false;
	},
	
	get_match_rules: function(doctype) {
		var match_rules = {};
		
		// Rule for owner match
		var owner_match = false;
		$.each(wn.model.get("DocPerm", {parent:doctype}), function(i, docperm) {
			if(docperm.match==="owner") {
				owner_match = true;
			} else {
				owner_match = false;
				return false;
			}
		});
		if(owner_match) match_rules["Created By"] = user;
		
		// Rule for restrictions
		var restrictions = wn.defaults.get_restrictions();
		if(restrictions && !$.isEmptyObject(restrictions)) {
			$.each(wn.perm.get_restricted_fields(doctype, null, restrictions), function(i, df) {
				match_rules[df.label] = restrictions[df.options];
			});
		}
		
		return match_rules;
	},
	
	get_field_display_status: function(df, doc, perm, explain) {
		if(!doc) return "Write";
		
		perm = perm || wn.perm.get_perm(doc.doctype, doc.name);
		if(!df.permlevel) df.permlevel = 0;
		var p = perm[df.permlevel];
		var status = "None";
		
		// permission
		if(p) {
			if(p.write && !df.disabled) {
				status = "Write";
			} else if(p.read) {
				status = "Read";
			}
		}		
		if(explain) console.log("By Permission:" + status);
		
		// hidden
		if(cint(df.hidden)) status = "None";
		if(explain) console.log("By Hidden:" + status);
		
		// hidden due to dependency
		if(cint(df.hidden_due_to_dependency)) status = "None";
		if(explain) console.log("By Hidden Due To Dependency:" + status);
		
		// submit
		if(status==="Write" && cint(doc.docstatus) > 0) status = "Read";
		if(explain) console.log("By Submit:" + status);
		
		// allow on submit
		var allow_on_submit = df.fieldtype==="Table" ? 0 : cint(df.allow_on_submit);
		if(status==="Read" && allow_on_submit && cint(doc.docstatus)===1 && p.write) {
			status = "Write";
		}
		if(explain) console.log("By Allow on Submit:" + status);
		
		// workflow state
		if(status==="Read" && cur_frm && cur_frm.state_fieldname) {
			// fields updated by workflow must be read-only
			if(cint(cur_frm.read_only) || 
				in_list(cur_frm.states.update_fields, df.fieldname) ||
				df.fieldname==cur_frm.state_fieldname) {
				status = "Read";
			}
		}
		if(explain) console.log("By Workflow:" + status);
		
		// read only field is checked
		if(status==="Write" && cint(df.read_only)) {
			status = "Read";
		}
		if(explain) console.log("By Read Only:" + status);
		
		return status;
	},
});