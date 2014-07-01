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

	has_perm: function(doctype, permlevel, ptype, doc) {
		if (!permlevel) permlevel = 0;
		if (!frappe.perm.doctype_perm[doctype]) {
			frappe.perm.doctype_perm[doctype] = frappe.perm.get_perm(doctype);
		}

		var perms = frappe.perm.doctype_perm[doctype];
		if (!perms)
			return false;

		if (!perms[permlevel])
			return false;

		var perm = !!perms[permlevel][ptype];

		if(permlevel===0 && perm && doc) {
			var docinfo = frappe.model.get_docinfo(doctype, doc.name);
			if(docinfo && !docinfo.permissions[ptype])
				perm = false;
		}

		return perm;
	},

	get_perm: function(doctype, doc) {
		var perm = [{ read: 0, apply_user_permissions: {} }];

		var meta = frappe.get_doc("DocType", doctype);
		if (!meta) {
			return perm;
		}

		if (user==="Administrator" || user_roles.indexOf("Administrator")!==-1) {
			perm[0].read = 1;
		}

		frappe.perm.build_role_permissions(perm, meta);

		if(doc) {
			// apply user permissions via docinfo (which is processed server-side)
			var docinfo = frappe.model.get_docinfo(doctype, doc.name);
			if(docinfo) {
				$.each(docinfo.permissions || [], function(ptype, val) {
					perm[0][ptype] = val;
				});
			}
		}

		return perm;
	},

	build_role_permissions: function(perm, meta) {
		$.each(meta.permissions || [], function(i, p) {
			// if user has this role
			if(user_roles.indexOf(p.role)!==-1) {
				var permlevel = cint(p.permlevel);
				if(!perm[permlevel]) {
					perm[permlevel] = {};
				}
				$.each(frappe.perm.rights, function(i, key) {
					perm[permlevel][key] = perm[permlevel][key] || (p[key] || 0);

					if (permlevel===0) {
						var apply_user_permissions = perm[permlevel].apply_user_permissions;
						var current_value = (apply_user_permissions[key]===undefined ?
								1 : apply_user_permissions[key]);
						apply_user_permissions[key] = current_value && p.apply_user_permissions;
					}
				});
			}
		});

		// remove values with 0
		$.each(perm[0], function(key, val) {
			if (!val) {
				delete perm[0][key];
			}
		});
	},

	get_match_rules: function(doctype, ptype) {
		if (!ptype) ptype = "read";

		var perm = frappe.perm.get_perm(doctype);
		var apply_user_permissions = perm[0].apply_user_permissions;
		if (!apply_user_permissions[ptype]) {
			return {};
		}

		var match_rules = {};
		var user_permissions = frappe.defaults.get_user_permissions();
		if(user_permissions && !$.isEmptyObject(user_permissions)) {
			var fields_to_check = frappe.meta.get_fields_to_check_permissions(doctype, null, user_permissions);
			$.each(fields_to_check, function(i, df) {
				match_rules[df.label] = user_permissions[df.options];
			});
		}

		return match_rules;
	},

	get_field_display_status: function(df, doc, perm, explain) {
		if(!doc) return "Write";

		perm = perm || frappe.perm.get_perm(doc.doctype, doc);
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
