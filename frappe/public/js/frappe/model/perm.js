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
	rights: [
		"select",
		"read",
		"write",
		"create",
		"delete",
		"submit",
		"cancel",
		"amend",
		"report",
		"import",
		"export",
		"print",
		"email",
		"share",
		"set_user_permissions",
	],

	doctype_perm: {},

	has_perm: (doctype, permlevel = 0, ptype = "read", doc) => {
		const perms = frappe.perm.get_perm(doctype, doc);
		return !!perms?.[permlevel]?.[ptype];
	},

	get_perm: (doctype, doc) => {
		// if document object is passed, get fresh doc based perms
		// (with ownership and user perms applied) else cached doctype perms

		if (doc && !doc.__islocal) {
			return frappe.perm._get_perm(doctype, doc);
		}

		return (frappe.perm.doctype_perm[doctype] ??= frappe.perm._get_perm(doctype));
	},

	_get_perm: (doctype, doc) => {
		let perm = [{ read: 0, permlevel: 0 }];

		let meta = frappe.get_doc("DocType", doctype);
		const user = frappe.session.user;

		if (user === "Administrator" || frappe.user_roles.includes("Administrator")) {
			perm[0].read = 1;
		}

		if (!meta) return perm;

		perm = frappe.perm.get_role_permissions(meta);
		const base_perm = perm[0];

		if (doc) {
			// apply user permissions via docinfo (which is processed server-side)
			let docinfo = frappe.model.get_docinfo(doctype, doc.name);
			if (docinfo && docinfo.permissions) {
				Object.keys(docinfo.permissions).forEach((ptype) => {
					base_perm[ptype] = docinfo.permissions[ptype];
				});
			}

			// if owner
			if (doc.owner !== user) {
				for (const right of frappe.perm.rights) {
					if (base_perm[right] && !base_perm.rights_without_if_owner.has(right)) {
						base_perm[right] = 0;
					}
				}
			}

			// apply permissions from shared
			if (docinfo && docinfo.shared) {
				for (const s of docinfo.shared) {
					if (s.user !== user) continue;

					for (const right of ["read", "write", "submit", "share"]) {
						if (!base_perm[right]) base_perm[right] = s[right];
					}

					if (s.read) {
						// also give print, email permissions if read
						// and these permissions exist at level [0]
						base_perm.email =
							frappe.boot.user.can_email.indexOf(doctype) !== -1 ? 1 : 0;
						base_perm.print =
							frappe.boot.user.can_print.indexOf(doctype) !== -1 ? 1 : 0;
					}
				}
			}
		}

		if (!base_perm.read && frappe.model.can_read(doctype)) {
			// read via sharing
			base_perm.read = 1;
		}

		return perm;
	},

	get_role_permissions: (meta) => {
		/** Returns a `dict` of evaluated Role Permissions like:
		{
			"read": 1,
			"write": 0,
			"rights_without_if_owner": {"read", "write"}  // for permlevel 0
		}
		*/

		let perm = [{ read: 0, permlevel: 0 }];

		(meta.permissions || []).forEach((p) => {
			const permlevel = cint(p.permlevel);
			const current_perm = (perm[permlevel] ??= { permlevel });

			if (permlevel === 0) {
				current_perm.rights_without_if_owner ??= new Set();
			}

			// if user has this role
			if (frappe.user_roles.includes(p.role)) {
				frappe.perm.rights.forEach((right) => {
					if (!p[right]) return;

					current_perm[right] = 1;

					if (permlevel === 0 && !p.if_owner) {
						current_perm.rights_without_if_owner.add(right);
					}
				});
			}
		});

		// fill gaps with empty object
		perm = perm.map((p) => p || {});
		return perm;
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
				const allowed_records = frappe.perm.get_allowed_docs_for_doctype(
					user_permissions_for_doctype,
					doctype
				);
				if (allowed_records.length) {
					rules[df.label] = allowed_records;
				}
			});
			if (!$.isEmptyObject(rules)) {
				match_rules.push(rules);
			}
		}

		const base_perm = perm[0];
		if (base_perm.read && !base_perm.rights_without_if_owner.has("read")) {
			match_rules.push({ Owner: frappe.session.user });
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
			let is_hidden = df && (cint(df.hidden) || cint(df.hidden_due_to_dependency));
			let is_read_only = df && cint(df.read_only);
			return is_hidden ? "None" : is_read_only ? "Read" : "Write";
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
			if (
				cint(cur_frm.read_only) ||
				in_list(cur_frm.states.update_fields, df.fieldname) ||
				df.fieldname == cur_frm.state_fieldname
			) {
				status = "Read";
			}
		}
		if (explain) console.log("By Workflow:" + status);

		// read only field is checked
		if (status === "Write" && (cint(df.read_only) || df.fieldtype === "Read Only")) {
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
		if (typeof df === "string") {
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

	filter_allowed_docs_for_doctype: (user_permissions, doctype, with_default_doc = true) => {
		// returns docs from the list of user permissions that are allowed under provided doctype
		// also returns default doc when with_default_doc is set
		const filtered_perms = (user_permissions || []).filter((perm) => {
			return perm.applicable_for === doctype || !perm.applicable_for;
		});

		const allowed_docs = filtered_perms.map((perm) => perm.doc);

		if (with_default_doc) {
			const default_doc =
				allowed_docs.length === 1
					? allowed_docs
					: filtered_perms.filter((perm) => perm.is_default).map((record) => record.doc);

			return {
				allowed_records: allowed_docs,
				default_doc: default_doc[0],
			};
		} else {
			return allowed_docs;
		}
	},
});
