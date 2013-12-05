// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

wn.provide("wn.perm");
var READ = 0, WRITE = 1, CREATE = 2; 
var SUBMIT = 3, CANCEL = 4, AMEND = 5;

$.extend(wn.perm, {
	doctype_perm: {},
	has_perm: function(doctype, level, type) {
		if(!level) level = 0;
		var perms = wn.perm.doctype_perm;
		if(!perms[doctype]) 
			perms[doctype] = wn.perm.get_perm(doctype);
		
		if(!perms[doctype])
			return false;
			
		if(!perms[doctype][level])
			return false;
			
		return perms[doctype][level][type];
	},
	get_perm: function(doctype, dn) {
		var perm = [[0,0],];
		if(in_list(user_roles, 'Administrator')) 
			perm[0][READ] = 1;
		
		if(locals["DocType"][doctype] && locals["DocType"][doctype].istable) {
			parent_df = wn.model.get("DocField", {fieldtype:"Table", options:doctype});
			if(parent_df.length) {
				dn = locals[doctype][dn].parent;
				doctype = parent_df[0].parent;
			}
		}
		
		$.each(wn.model.get("DocPerm", {parent:doctype}), function(i, p) {
			var pl = cint(p.permlevel?p.permlevel:0);
			// if user role
			if(in_list(user_roles, p.role)) {
				// if field match
				if(wn.perm.check_match(p, doctype, dn)) { // new style
					if(!perm[pl])
						perm[pl] = [];
						
					if(!perm[pl][READ]) {
						if(cint(p.read)) perm[pl][READ]=1; else perm[pl][READ]=0;
					}
					if(!perm[pl][WRITE]) { 
						if(cint(p.write)) { perm[pl][WRITE]=1; perm[pl][READ]=1; }
						else perm[pl][WRITE]=0;
					}
					if(!perm[pl][CREATE]) { 
						if(cint(p.create))perm[pl][CREATE]=1; else perm[pl][CREATE]=0;
					}
					if(!perm[pl][SUBMIT]) { 
						if(cint(p.submit))perm[pl][SUBMIT]=1; else perm[pl][SUBMIT]=0;
					}
					if(!perm[pl][CANCEL]) { 
						if(cint(p.cancel))perm[pl][CANCEL]=1; else perm[pl][CANCEL]=0;
					}
					if(!perm[pl][AMEND]) { 
						if(cint(p.amend)) perm[pl][AMEND]=1;  else perm[pl][AMEND]=0;
					}
				}
			}
		});

		return perm;
	},
	
	get_match_rule: function(doctype) {
		var match_rules = {};
		var match = true;
		$.each(wn.model.get("DocPerm", {parent:doctype}), function(i, p) {
			if(p.permlevel==0 && in_list(user_roles, p.role)) {
				if(p.match) {
					match_keys = wn.perm.get_match_keys(p.match);
					match_rules[match_keys[0]] = wn.defaults.get_user_defaults(match_keys[1]);
				} else {
					match = false;
				}
			}
		});
		return match ? match_rules : {};
	},

	get_match_keys: function(match) {
		if(match.indexOf(":")!=-1) {
			key_list = match.split(":");
		} else {
			key_list = [match, match];
		}
		return key_list;
	},
	
	check_match: function(p, doctype, name) {
		if(!name) return true;
		var out =false;
		if(p.match) {
			var key_list = wn.perm.get_match_keys(p.match);
			var document_key = key_list[0];
			var default_key = key_list[1];

			var match_values = wn.defaults.get_user_defaults(default_key);
			if(match_values) {
				for(var i=0 ; i<match_values.length;i++) {
					 // user must have match field in defaults
					if(match_values[i]==locals[doctype][name][document_key]) {
					    // must match document
			  			return true;
					}
				}
				return false;
			} else if(!locals[doctype][name][document_key]) { // blanks are true
				return true;
			} else {
				return false;
			}
		} else {
			return true;
		}
	},	
	get_field_display_status: function(df, doc, perm, explain) {
		if(!doc) return "Write"

		if(!df.permlevel) df.permlevel = 0;

		perm = perm || wn.perm.get_perm(doc.doctype, doc.name);
		var p = perm[df.permlevel],
			ret = null;

		// permission level
		if(p && p[WRITE] && !df.disabled)
			ret='Write';
		else if(p && p[READ])
			ret='Read';
		else 
			ret='None';

		if(explain) console.log("By Permission:" + ret)

		// hidden
		if(cint(df.hidden)) {
			ret = 'None';
		}

		if(explain) console.log("By Hidden:" + ret)

		// hidden due to dependency
		if(ret!=='None' && df.hidden_due_to_dependency) 
			ret = 'None';

		if(explain) console.log("By Hidden Due To Dependency:" + ret)

		// for submit
		if(ret=='Write' && cint(doc.docstatus) > 0) {
			ret = 'Read';
		}

		if(explain) console.log("By Submit:" + ret)

		// allow on submit
		var allow_on_submit = df.fieldtype!= "Table" ? 
			cint(df.allow_on_submit) :
			0;
		
		// if(allow_on_submit && doc.parent) {
		// 	parent_df = wn.model.get("DocField", {
		// 		"parent": doc.parenttype,
		// 		"fieldname": doc.parentfield
		// 	});
		// 	allow_on_submit = parent_df ? 
		// 		parent_df[0].allow_on_submit :
		// 		0;
		// }

		if(explain) console.log("Allow on Submit:" + allow_on_submit)

		if(ret=="Read" && allow_on_submit && cint(doc.docstatus)==1 && 
			perm[df.permlevel][WRITE]) {
			ret='Write';
		}

		if(explain) console.log("By Allow on Submt:" + ret)

		// workflow state
		if(ret=="Write" && cur_frm && cur_frm.state_fieldname) {
			if(cint(cur_frm.read_only)) {
				ret = 'Read';
			}
			// fields updated by workflow must be read-only
			if(in_list(cur_frm.states.update_fields, df.fieldname) ||
				df.fieldname==cur_frm.state_fieldname) {
				ret = 'Read';
			}
		}

		if(explain) console.log("By Workflow:" + ret)

		// make a field read_only if read_only 
		// is checked (disregards write permission)
		if(ret=="Write" && cint(df.read_only)) {
			ret = "Read";
		}

		if(explain) console.log("By Read Only:" + ret)
		
		return ret;
		
	}
});