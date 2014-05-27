// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.perm");

// backward compatibilty
var READ = "read", WRITE = "write", CREATE = "create", DELETE = "delete";
var SUBMIT = "submit", CANCEL = "cancel", AMEND = "amend";

$.extend(frappe.perm, {
	rights: ["read", "write", "create", "delete", "submit", "cancel", "amend",
		"report", "import", "export", "print", "email", "set_user_permissions"],

	doctype_perm: {},

	has_perm: function(doctype, permlevel, ptype) {
		if(!permlevel) permlevel = 0;
		if(!frappe.perm.doctype_perm[doctype]) {
			frappe.perm.doctype_perm[doctype] = frappe.perm.get_perm(doctype);
		}

		var perms = frappe.perm.doctype_perm[doctype];
		if(!perms)
			return false;

		if(!perms[permlevel])
			return false;

		return !!perms[permlevel][ptype];
	},

	get_perm: function(doctype) {
		var perm = [{read: 0}];

		var meta = frappe.get_doc("DocType", doctype);
		if(!meta) {
			return perm;
		}

		if(user==="Administrator" || user_roles.indexOf("Administrator")!==-1) {
			perm[0].read = 1;
		}

		frappe.perm.build_role_permissions(perm, meta);

		return perm;
	},

	build_role_permissions: function(perm, meta) {
		var permissions = meta.permissions || [];
		$.each(permissions, function(i, p) {
			// if user has this role
			if(user_roles.indexOf(p.role)!==-1) {
				var permlevel = cint(p.permlevel);
				if(!perm[permlevel]) {
					perm[permlevel] = {};
				}
				$.each(frappe.perm.rights, function(i, key) {
					if(key=="restricted") {
						perm[permlevel][key] = (perm[permlevel][key] || 1) && (p[key] || 0);
					} else {
						perm[permlevel][key] = perm[permlevel][key] || (p[key] || 0);
					}
				});
			}
		});
	},

	has_unrestricted_access: function(doctype, docname, restricted) {
		var user_permissions = frappe.defaults.get_user_permissions();
		var doc = frappe.get_doc(doctype, docname);

		if(restricted) {
			if(doc.owner==user) return true;
			if(!user_permissions || $.isEmptyObject(user_permissions)) {
				return false;
			}
		} else {
			if(!user_permissions || $.isEmptyObject(user_permissions)) {
				return true;
			}
		}

		// prepare restricted fields
		var fields_to_check = frappe.perm.get_fields_to_check_permissions(doctype, docname, user_permissions);

		// loop and find if has restricted data
		var has_restricted_data = false;
		var doc = frappe.get_doc(doctype, docname);
		$.each(fields_to_check, function(i, df) {
			if(doc[df.fieldname] && user_permissions[df.options].indexOf(doc[df.fieldname])===-1) {
				has_restricted_data = true;
				return false;
			}
		});

		return !has_restricted_data;
	},

	get_fields_to_check_permissions: function(doctype, docname, user_permissions) {
		var fields_to_check = frappe.meta.get_fields_to_check_permissions(doctype, docname,
			Object.keys(user_permissions));
		if(Object.keys(user_permissions).indexOf(doctype)!==-1) {
			fields_to_check = fields_to_check.concat(
				{label: "Name", fieldname: name, options: doctype});
		}
		return fields_to_check;
	},

	get_match_rules: function(doctype) {
		var match_rules = {};

		// Rule for user_permissions
		var user_permissions = frappe.defaults.get_user_permissions();
		if(user_permissions && !$.isEmptyObject(user_permissions)) {
			$.each(frappe.perm.get_fields_to_check_permissions(doctype, null, user_permissions), function(i, df) {
				match_rules[df.label] = user_permissions[df.options];
			});
		}

		return match_rules;
	},

	get_field_display_status: function(df, doc, perm, explain) {
		if(!doc) return "Write";

		perm = perm || frappe.perm.get_perm(doc.doctype, doc.name);
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

		if(status==="Write" && df.set_only_once && !doc.__islocal) {
			status = "Read";
		}
		if(explain) console.log("By Set Only Once:" + status);

		return status;
	},
});
