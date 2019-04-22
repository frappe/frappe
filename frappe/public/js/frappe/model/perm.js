// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.perm");

// backward compatibilty
Object.assign(window, {
	READ: "read",
	WRITE: "write",
	CREATE: "create",
	DELETE: "delete",
	SUBMIT: "submit",
	CANCEL: "cancel",
	AMEND: "amend",
});

$.extend(frappe.perm, {
	rights: ["read", "write", "create", "delete", "submit", "cancel", "amend",
		"report", "import", "export", "print", "email", "share", "set_user_permissions"],

	doctype_perm: {},

	has_perm: (doctype, permlevel, ptype, doc) => {
		if (!permlevel) permlevel = 0;
		if (!frappe.perm.doctype_perm[doctype]) {
			frappe.perm.doctype_perm[doctype] = frappe.perm.get_perm(doctype);
		}

		let perms = frappe.perm.doctype_perm[doctype];

		if (!perms || !perms[permlevel]) return false;

		let perm = !!perms[permlevel][ptype];

		if (permlevel === 0 && perm && doc) {
			let docinfo = frappe.model.get_docinfo(doctype, doc.name);
			if (docinfo && !docinfo.permissions[ptype])
				perm = false;
		}

		return perm;
	},

	get_perm: (doctype, doc) => {
		let perm = [{ read: 0 }];

		let meta = frappe.get_doc("DocType", doctype);
		const user  = frappe.session.user;

		if (user === "Administrator" || frappe.user_roles.includes("Administrator")) {
			perm[0].read = 1;
		}

		if (!meta) return perm;

		frappe.perm.build_role_permissions(perm, meta);

		if (doc) {
			// apply user permissions via docinfo (which is processed server-side)
			let docinfo = frappe.model.get_docinfo(doctype, doc.name);
			if (docinfo && docinfo.permissions) {
				Object.keys(docinfo.permissions).forEach((ptype) => {
					perm[0][ptype] = docinfo.permissions[ptype];
				});
			}

			// if owner
			if (!$.isEmptyObject(perm[0].if_owner)) {
				if (doc.owner === user) {
					$.extend(perm[0], perm[0].if_owner);
				} else {
					// not owner, remove permissions
					$.each(perm[0].if_owner, (ptype) => {
						if (perm[0].if_owner[ptype]) {
							perm[0][ptype] = 0;
						}
					});
				}
			}

			// apply permissions from shared
			if (docinfo && docinfo.shared) {
				for (let i = 0; i < docinfo.shared.length; i++) {
					let s = docinfo.shared[i];
					if (s.user === user) {
						perm[0]["read"] = perm[0]["read"] || s.read;
						perm[0]["write"] = perm[0]["write"] || s.write;
						perm[0]["share"] = perm[0]["share"] || s.share;

						if (s.read) {
							// also give print, email permissions if read
							// and these permissions exist at level [0]
							perm[0].email = frappe.boot.user.can_email.indexOf(doctype) !== -1 ? 1 : 0;
							perm[0].print = frappe.boot.user.can_print.indexOf(doctype) !== -1 ? 1 : 0;
						}
					}
				}
			}

		}

		if (frappe.model.can_read(doctype) && !perm[0].read) {
			// read via sharing
			perm[0].read = 1;
		}

		return perm;
	},

	build_role_permissions: (perm, meta) => {
		// Returns a `dict` of evaluated Role Permissions
		$.each(meta.permissions || [], (i, p) => {
			// if user has this role
			if (frappe.user_roles.includes(p.role)) {
				let permlevel = cint(p.permlevel);
				if (!perm[permlevel]) {
					perm[permlevel] = {};
					perm[permlevel]["permlevel"] = permlevel
				}

				$.each(frappe.perm.rights, (i, key) => {
					perm[permlevel][key] = perm[permlevel][key] || (p[key] || 0);
				});
			}
		});

		// remove values with 0
		$.each(perm[0], (key, val) => {
			if (!val) {
				delete perm[0][key];
			}
		});

		$.each(perm, (i, v) => {
			if (v === undefined) {
				perm[i] = {};
			}
		});
	},

	get_match_rules: (doctype, ptype) => {
		let match_rules = [];

		if (!ptype) ptype = "read";

		let perm = frappe.perm.get_perm(doctype);

		let user_permissions = frappe.defaults.get_user_permissions();

		if (user_permissions && !$.isEmptyObject(user_permissions)) {
			let rules = {};
			let fields_to_check = frappe.meta.get_fields_to_check_permissions(doctype);
			$.each(fields_to_check, (i, df) => {
				const user_permissions_for_doctype = user_permissions[df.options] || [];
				const allowed_records = frappe.perm.get_allowed_docs_for_doctype(user_permissions_for_doctype, doctype);
				if (allowed_records.length) {
					rules[df.label] = allowed_records;
				}
			});
			if (!$.isEmptyObject(rules)) {
				match_rules.push(rules);
			}
		}

		if (perm[0].if_owner && perm[0].read) {
			match_rules.push({ "Owner": frappe.session.user });
		}
		return match_rules;
	},

	get_field_display_status: (df, doc, perm, explain) => {
		// returns the display status of a particular field
		// returns one of "Read", "Write" or "None"
		if (!perm && doc) {
			perm = frappe.perm.get_perm(doc.doctype, doc);
		}

		if (!perm) {
			return (df && (cint(df.hidden) || cint(df.hidden_due_to_dependency))) ? "None" : "Write";
		}

		if (!df.permlevel) df.permlevel = 0;
		let p = perm[df.permlevel];
		let status = "None";

		// permission
		if (p) {
			if (p.write && !df.disabled) {
				status = "Write";
			} else if (p.read) {
				status = "Read";
			}
		}
		if (explain) console.log("By Permission:" + status);

		// hidden
		if (cint(df.hidden)) status = "None";
		if (explain) console.log("By Hidden:" + status);

		// hidden due to dependency
		if (cint(df.hidden_due_to_dependency)) status = "None";
		if (explain) console.log("By Hidden Due To Dependency:" + status);

		if (!doc) {
			return status;
		}

		// submit
		if (status === "Write" && cint(doc.docstatus) > 0) status = "Read";
		if (explain) console.log("By Submit:" + status);

		// allow on submit
		// let allow_on_submit = df.fieldtype==="Table" ? 0 : cint(df.allow_on_submit);
		let allow_on_submit = cint(df.allow_on_submit);
		if (status === "Read" && allow_on_submit && cint(doc.docstatus) === 1 && p.write) {
			status = "Write";
		}
		if (explain) console.log("By Allow on Submit:" + status);

		// workflow state
		if (status === "Read" && cur_frm && cur_frm.state_fieldname) {
			// fields updated by workflow must be read-only
			if (cint(cur_frm.read_only) ||
				in_list(cur_frm.states.update_fields, df.fieldname) ||
				df.fieldname == cur_frm.state_fieldname) {
				status = "Read";
			}
		}
		if (explain) console.log("By Workflow:" + status);

		// read only field is checked
		if (status === "Write" && cint(df.read_only)) {
			status = "Read";
		}
		if (explain) console.log("By Read Only:" + status);

		if (status === "Write" && df.set_only_once && !doc.__islocal) {
			status = "Read";
		}
		if (explain) console.log("By Set Only Once:" + status);

		return status;
	},

	is_visible: (df, doc, perm) => {
		if (typeof df === 'string') {
			// df is fieldname
			df = frappe.meta.get_docfield(doc.doctype, df, doc.parent || doc.name);
		}

		let status = frappe.perm.get_field_display_status(df, doc, perm);

		return status === "None" ? false : true;
	},

	get_allowed_docs_for_doctype: (user_permissions, doctype) => {
		// returns docs from the list of user permissions that are allowed under provided doctype
		return frappe.perm.filter_allowed_docs_for_doctype(user_permissions, doctype, false);
	},

	filter_allowed_docs_for_doctype: (user_permissions, doctype, with_default_doc=true) => {
		// returns docs from the list of user permissions that are allowed under provided doctype
		// also returns default doc when with_default_doc is set
		const filtered_perms = (user_permissions || []).filter(perm => {
			return (perm.applicable_for === doctype || !perm.applicable_for);
		});

		const allowed_docs = (filtered_perms).map(perm => perm.doc);

		if (with_default_doc) {
			const default_doc = allowed_docs.length === 1 ? allowed_docs : filtered_perms
				.filter(perm => perm.is_default)
				.map(record => record.doc);

			return {
				allowed_records: allowed_docs,
				default_doc: default_doc[0]
			};
		} else {
			return allowed_docs;
		}
	}
});