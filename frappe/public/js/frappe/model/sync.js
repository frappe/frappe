// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

Object.assign(frappe.model, {
	docinfo: {},
	sync: function (r) {
		/* docs:
			extract docs, docinfo (attachments, comments, assignments)
			from incoming request and set in `locals` and `frappe.model.docinfo`
		*/
		var isPlain;
		if (!r.docs && !r.docinfo) r = { docs: r };

		isPlain = $.isPlainObject(r.docs);
		if (isPlain) r.docs = [r.docs];

		if (r.docs) {
			for (var i = 0, l = r.docs.length; i < l; i++) {
				var d = r.docs[i];

				if (locals[d.doctype] && locals[d.doctype][d.name]) {
					// update values
					frappe.model.update_in_locals(d);
				} else {
					frappe.model.add_to_locals(d);
				}

				d.__last_sync_on = new Date();

				if (d.doctype === "DocType") {
					frappe.meta.sync(d);
				}

				if (d.localname) {
					frappe.model.rename_after_save(d, i);
				}
			}
		}

		frappe.model.sync_docinfo(r);
		return r.docs;
	},

	rename_after_save: (d, i) => {
		frappe.model.new_names[d.localname] = d.name;
		$(document).trigger("rename", [d.doctype, d.localname, d.name]);
		delete locals[d.doctype][d.localname];

		// update docinfo to new dict keys
		if (i === 0) {
			frappe.model.docinfo[d.doctype][d.name] = frappe.model.docinfo[d.doctype][d.localname];
			frappe.model.docinfo[d.doctype][d.localname] = undefined;
		}
	},

	sync_docinfo: (r) => {
		// set docinfo (comments, assign, attachments)
		if (r.docinfo) {
			const { doctype, name } = r.docinfo;
			if (!frappe.model.docinfo[doctype]) {
				frappe.model.docinfo[doctype] = {};
			}
			frappe.model.docinfo[doctype][name] = r.docinfo;

			// copy values to frappe.boot.user_info
			Object.assign(frappe.boot.user_info, r.docinfo.user_info);
		}

		return r.docs;
	},

	add_to_locals: function (doc) {
		if (!locals[doc.doctype]) locals[doc.doctype] = {};

		if (!doc.name && doc.__islocal) {
			// get name (local if required)
			if (!doc.parentfield) frappe.model.clear_doc(doc);

			doc.name = frappe.model.get_new_name(doc.doctype);

			if (!doc.parentfield)
				frappe.provide("frappe.model.docinfo." + doc.doctype + "." + doc.name);
		}

		locals[doc.doctype][doc.name] = doc;

		let meta = frappe.get_meta(doc.doctype);
		let is_table = meta ? meta.istable : doc.parentfield;
		// add child docs to locals
		if (!is_table) {
			for (var i in doc) {
				if (i.startsWith("__")) continue;
				var value = doc[i];

				if ($.isArray(value)) {
					for (var x = 0, y = value.length; x < y; x++) {
						var d = value[x];

						if (typeof d == "object" && !d.parent) d.parent = doc.name;

						frappe.model.add_to_locals(d);
					}
				}
			}
		}
	},

	update_in_locals: function (doc) {
		// update values in the existing local doc instead of replacing
		let local_doc = locals[doc.doctype][doc.name];
		let clear_keys = function (source, target) {
			Object.keys(target).map((key) => {
				if (source[key] == undefined) delete target[key];
			});
		};

		for (let fieldname in doc) {
			let df = frappe.meta.get_field(doc.doctype, fieldname);
			if (df && frappe.model.table_fields.includes(df.fieldtype)) {
				// table
				if (!(doc[fieldname] instanceof Array)) {
					doc[fieldname] = [];
				}

				if (!(local_doc[fieldname] instanceof Array)) {
					local_doc[fieldname] = [];
				}

				// reconcile child rows by identity (name), not index, so
				// server-side reorders/removals don't corrupt locals
				const incoming_names = new Set(doc[fieldname].map((d) => d.name));
				const local_rows = local_doc[fieldname];
				const local_by_name = {};
				for (const row of local_rows) local_by_name[row.name] = row;

				// unsaved local rows receive real names from the server on save;
				// pair them, in order, with incoming rows that match no local name
				const unmatched_new_rows = local_rows.filter(
					(row) => row.__islocal && !incoming_names.has(row.name)
				);

				const reconciled = [];
				for (const d of doc[fieldname]) {
					if (!d.name) d.name = frappe.model.get_new_name(doc.doctype);
					let local_d = local_by_name[d.name];

					if (!local_d && unmatched_new_rows.length) {
						local_d = unmatched_new_rows.shift();
						const old_name = local_d.name;
						if (locals[d.doctype]) delete locals[d.doctype][old_name];

						const dc = frappe.meta.docfield_copy[d.doctype];
						if (dc?.[old_name]) {
							dc[d.name] = dc[old_name];
							delete dc[old_name];
						}
					}

					if (local_d) {
						Object.assign(local_d, d);
						clear_keys(d, local_d);
					} else {
						local_d = d;
					}

					if (!local_d.parent) local_d.parent = doc.name;
					if (!locals[local_d.doctype]) locals[local_d.doctype] = {};
					locals[local_d.doctype][local_d.name] = local_d;
					reconciled.push(local_d);
				}

				// drop rows no longer present server-side
				const kept_names = new Set(reconciled.map((d) => d.name));
				for (const row of local_rows) {
					if (!kept_names.has(row.name) && locals[row.doctype]?.[row.name] === row) {
						delete locals[row.doctype][row.name];
					}
				}

				// rebuild in place so the array reference is preserved
				local_doc[fieldname].length = 0;
				local_doc[fieldname].push(...reconciled);
			} else {
				// literal
				local_doc[fieldname] = doc[fieldname];
			}
		}

		if ((local_doc?.on_paste_event || local_doc?.__islocal) && local_doc?.__newname) {
			doc.__newname = local_doc.__newname;
		}

		// clear keys on parent
		clear_keys(doc, local_doc);
	},
});
