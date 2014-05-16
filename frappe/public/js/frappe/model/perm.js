// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.perm");

// backward compatibilty
var READ = "read", WRITE = "write", CREATE = "create", DELETE = "delete";
var SUBMIT = "submit", CANCEL = "cancel", AMEND = "amend";

$.extend(frappe.perm, {
	rights: ["read", "write", "create", "delete", "submit", "cancel", "amend", "print", "email",
	"restricted", "dont_restrict", "can_restrict", "report", "import", "export"],

	restrictable_rights: ["read", "write", "create", "delete", "submit", "cancel", "amend"],

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
		if (!meta) {
			return perm;
		}

		if (user==="Administrator" || user_roles.indexOf("Administrator")!==-1) {
			perm[0].read = 1;
		}

		frappe.perm.build_user_perm(perm, meta);

		return perm;
	},

	build_user_perm: function(perm, meta) {
		var permissions = meta.permissions || [];
		permissions.sort(function(a, b) {
			var permlevel_diff = flt(a.permlevel) - flt(b.permlevel);
			if (permlevel_diff) {
				return permlevel_diff;
			} else {
				// restricted=1 should be before restricted=0
				return flt(b.restricted) - flt(a.restricted)
			}
		});
		$.each(permissions, function(i, p) {
			// if user has this role
			if(user_roles.indexOf(p.role)!==-1) {
				var permlevel = cint(p.permlevel);
				if(!perm[permlevel]) {
					perm[permlevel] = {};
				}
				$.each(frappe.perm.rights, function(i, key) {
					if(["restricted", "dont_restrict"].indexOf(key)!==-1) {
						if (!perm[permlevel][key]) {
							perm[permlevel][key] = [];
						}
						if (p[key] || 0) {
							$.each(frappe.perm.restrictable_rights, function(j, r) {
								if ((p[r] || 0) && perm[permlevel][key].indexOf(r)===-1) {
									perm[permlevel][key].push(r);
								}
							});
						} else if (key==="restricted") {
							$.each(frappe.perm.restrictable_rights, function(j, r) {
								if (p[r] || 0) {
									var index = perm[permlevel][key].indexOf(r);
									if (index!==-1) {
										perm[permlevel][key].splice(index, 1);
									}
								}
							});
						}
					} else {
						perm[permlevel][key] = perm[permlevel][key] || (p[key] || 0);
					}
				});
			}
		});
	},

	get_restricted_fields: function(doctype, docname, restrictions) {
		var fields_to_check = frappe.meta.get_restricted_fields(doctype, docname,
			Object.keys(restrictions));
		if(Object.keys(restrictions).indexOf(doctype)!==-1) {
			fields_to_check = fields_to_check.concat(
				{label: "Name", fieldname: name, options: doctype});
		}
		return fields_to_check;
	},

	get_match_rules: function(doctype, ptype) {
		if (!ptype) ptype = "read";
		var perm = frappe.perm.get_perm(doctype);

		var dont_restrict = perm[0].dont_restrict || [];
		if (dont_restrict.length && dont_restrict.indexOf(ptype)!==-1) {
			return {};
		}

		var restricted = perm[0].restricted || [];
		var restrictions = frappe.defaults.get_restrictions();
		if (restricted.length && restricted.indexOf(ptype)!==-1) {
			return { "Name": restrictions[doctype] || [] };
		}

		// Rule for restrictions
		var match_rules = {};
		if(restrictions && !$.isEmptyObject(restrictions)) {
			$.each(frappe.perm.get_restricted_fields(doctype, null, restrictions), function(i, df) {
				match_rules[df.label] = restrictions[df.options];
			});
		}
		return match_rules;
	},

	get_field_display_status: function(df, doc, perm, explain) {
		if(!doc) return "Write";

		perm = perm || frappe.perm.get_perm(doc.doctype);
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
