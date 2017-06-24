// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.perm");

// backward compatibilty
var READ = "read", WRITE = "write", CREATE = "create", DELETE = "delete";
var SUBMIT = "submit", CANCEL = "cancel", AMEND = "amend";

$.extend(frappe.perm, {
	rights: ["read", "write", "create", "delete", "submit", "cancel", "amend",
		"report", "import", "export", "print", "email", "share", "set_user_permissions"],

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

		if (frappe.session.user === "Administrator" || frappe.user_roles.includes("Administrator")) {
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

			// if owner
			if(!$.isEmptyObject(perm[0].if_owner)) {
				if(doc.owner === frappe.session.user) {
					$.extend(perm[0], perm[0].if_owner);
				} else {
					// not owner, remove permissions
					$.each(perm[0].if_owner, function(ptype, value) {
						if(perm[0].if_owner[ptype]) {
							perm[0][ptype] = 0
						}
					})
				}
			}

			// apply permissions from shared
			if(docinfo && docinfo.shared) {
				for(var i=0; i<docinfo.shared.length; i++) {
					var s = docinfo.shared[i];
					if(s.user === frappe.session.user) {
						perm[0]["read"] = perm[0]["read"] || s.read;
						perm[0]["write"] = perm[0]["write"] || s.write;
						perm[0]["share"] = perm[0]["share"] || s.share;

						if(s.read) {
							// also give print, email permissions if read
							// and these permissions exist at level [0]
							perm[0].email = frappe.boot.user.can_email.indexOf(doctype)!==-1 ? 1 : 0;
							perm[0].print = frappe.boot.user.can_print.indexOf(doctype)!==-1 ? 1 : 0;
						}
					}
				}
			}

		}

		if(frappe.model.can_read(doctype) && !perm[0].read) {
			// read via sharing
			perm[0].read = 1;
		}

		return perm;
	},

	build_role_permissions: function(perm, meta) {
		// Returns a `dict` of evaluated Role Permissions
		// Apply User Permission and its DocTypes are used to display match rules in list view

		$.each(meta.permissions || [], function(i, p) {
			// if user has this role
			if(frappe.user_roles.includes(p.role)) {
				var permlevel = cint(p.permlevel);
				if(!perm[permlevel]) {
					perm[permlevel] = {};
				}

				$.each(frappe.perm.rights, function(i, key) {
					perm[permlevel][key] = perm[permlevel][key] || (p[key] || 0);

					// NOTE: this data is required for displaying match rules in list view
					if (permlevel===0) {
						var apply_user_permissions = perm[permlevel].apply_user_permissions;
						var current_value = (apply_user_permissions[key]===undefined ?
								1 : apply_user_permissions[key]);
						apply_user_permissions[key] = current_value && cint(p.apply_user_permissions);
					}
				});

				// NOTE: this data is required for displaying match rules in list view
				if (permlevel===0 && cint(p.apply_user_permissions) && p.user_permission_doctypes) {
					// set user_permission_doctypes in perms
					var user_permission_doctypes = JSON.parse(p.user_permission_doctypes);

					if (user_permission_doctypes && user_permission_doctypes.length) {
						if (!perm[permlevel]["user_permission_doctypes"]) {
							perm[permlevel]["user_permission_doctypes"] = {};
						}

						$.each(frappe.perm.rights, function(i, key) {
							if (!perm[permlevel]["user_permission_doctypes"][key]) {
								perm[permlevel]["user_permission_doctypes"][key] = [];
							}

							perm[permlevel]["user_permission_doctypes"][key].push(user_permission_doctypes);
						});
					}
				}
			}
		});

		// remove values with 0
		$.each(perm[0], function(key, val) {
			if (!val) {
				delete perm[0][key];
			}
		});

		$.each(perm, function(i, v) {
			if(v===undefined) {
				perm[i] = {};
			}
		});
	},

	get_match_rules: function(doctype, ptype) {
		var me = this;
		var match_rules = [];

		if (!ptype) ptype = "read";

		var perm = frappe.perm.get_perm(doctype);
		var apply_user_permissions = perm[0].apply_user_permissions;
		if (!apply_user_permissions[ptype]) {
			return match_rules;
		}

		var user_permissions = frappe.defaults.get_user_permissions();
		if(user_permissions && !$.isEmptyObject(user_permissions)) {
			if(perm[0].user_permission_doctypes) {
				var user_permission_doctypes = me.get_user_permission_doctypes(perm[0].user_permission_doctypes[ptype],
					user_permissions);
			} else {
				// json is not set, so give list of all doctypes
				var user_permission_doctypes = [[doctype].concat(frappe.meta.get_linked_fields(doctype))];
			}

			$.each(user_permission_doctypes, function(i, doctypes) {
				var rules = {};
				var fields_to_check = frappe.meta.get_fields_to_check_permissions(doctype, null, doctypes);
				$.each(fields_to_check, function(i, df) {
					rules[df.label] = user_permissions[df.options] || [];
				});
				if (!$.isEmptyObject(rules)) {
					match_rules.push(rules);
				}
			});
		}

		if (perm[0].if_owner && perm[0].read) {
			match_rules.push({"Owner": frappe.session.user});
		}

		return match_rules;
	},

	get_user_permission_doctypes: function(user_permission_doctypes, user_permissions) {
		// returns a list of list like [["User", "Blog Post"], ["User"]]
		var out = [];

		if (user_permission_doctypes && user_permission_doctypes.length) {
			$.each(user_permission_doctypes, function(i, doctypes) {
				var valid_doctypes = [];
				$.each(doctypes, function(i, d) {
					if (user_permissions[d]) {
						valid_doctypes.push(d);
					}
				});
				if (valid_doctypes.length) {
					out.push(valid_doctypes);
				}
			});

		} else {
			out = [Object.keys(user_permissions)];
		}

		if (out.length > 1) {
			// OPTIMIZATION
			// if intersection exists, use that to reduce the amount of querying
			// for example, [["Blogger", "Blog Category"], ["Blogger"]], should only search in [["Blogger"]] as the first and condition becomes redundant
			var common = out[0];
			for (var i=1, l=out.length; i < l; i++) {
				common = frappe.utils.intersection(common, out[i]);
				if (!common.length) {
					break;
				}
			}

			if (common.length) {
				// is common one of the user_permission_doctypes set?
				common.sort();
				for (var i=0, l=out.length; i < l; i++) {
					var arr = [].concat(out).sort();
					// are arrays equal?
					if (JSON.stringify(common)===JSON.stringify(arr)) {
						out = [common];
						break;
					}
				}
			}
		}

		return out
	},

	get_field_display_status: function(df, doc, perm, explain) {
		// returns the display status of a particular field
		// returns one of "Read", "Write" or "None"
		if(!perm && doc) {
			perm = frappe.perm.get_perm(doc.doctype, doc);
		}

		if(!perm) {
			return (df && (cint(df.hidden) || cint(df.hidden_due_to_dependency))) ? "None": "Write";
		}

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

		if(!doc) {
			return status;
		}

		// submit
		if(status==="Write" && cint(doc.docstatus) > 0) status = "Read";
		if(explain) console.log("By Submit:" + status);

		// allow on submit
		// var allow_on_submit = df.fieldtype==="Table" ? 0 : cint(df.allow_on_submit);
		var allow_on_submit = cint(df.allow_on_submit);
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

	is_visible: function(df, doc, perm) {
		if (typeof df === 'string') {
			// df is fieldname
			df = frappe.meta.get_docfield(doc.doctype, df, doc.parent || doc.name);
		}

		var status = frappe.perm.get_field_display_status(df, doc, perm);

		return status==="None" ? false : true;
	},
});
