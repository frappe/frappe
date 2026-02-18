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

	update_in_locals: function (updated_doc) {
		// update values in the existing local doc instead of replacing
		let local_parent_doc = locals[updated_doc.doctype][updated_doc.name];
		let clear_keys = function (source, target) {
			Object.keys(target).map((key) => {
				if (source[key] == undefined) delete target[key];
			});
		};

		for (let fieldname in updated_doc) {
			let df = frappe.meta.get_field(updated_doc.doctype, fieldname);
			if (df && frappe.model.table_fields.includes(df.fieldtype)) {
				// table
				if (!(updated_doc[fieldname] instanceof Array)) {
					updated_doc[fieldname] = [];
				}

				if (!(local_parent_doc[fieldname] instanceof Array)) {
					local_parent_doc[fieldname] = [];
				}

				// child table, override each row and append new rows if required
				for (let i = 0; i < updated_doc[fieldname].length; i++) {
					let updated_child_doc = updated_doc[fieldname][i];
					let local_child_doc_in_parent = local_parent_doc[fieldname][i];
					const local_child_doc = locals[updated_child_doc.doctype]
						? locals[updated_child_doc.doctype][updated_child_doc.name]
						: null;
					if (local_child_doc) {
						// update the existing child doc in locals
						Object.assign(local_child_doc, updated_child_doc);
						clear_keys(updated_child_doc, local_child_doc);
						// update parent array reference if needed
						if (local_child_doc_in_parent !== local_child_doc) {
							local_parent_doc[fieldname][i] = local_child_doc;
						}
						continue;
					}
					if (local_child_doc_in_parent) {
						// deleted and added again
						if (!locals[updated_child_doc.doctype])
							locals[updated_child_doc.doctype] = {};

						if (!updated_child_doc.name) {
							// incoming row is new, find a new name
							updated_child_doc.name = frappe.model.get_new_name(
								updated_doc.doctype
							);
						}

						// if incoming row is not registered, register it
						if (!locals[updated_child_doc.doctype][updated_child_doc.name]) {
							// detach old key
							delete locals[updated_child_doc.doctype][
								local_child_doc_in_parent.name
							];

							// re-attach with new name
							locals[updated_child_doc.doctype][updated_child_doc.name] =
								local_child_doc_in_parent;
						}

						// row exists, just copy the values
						Object.assign(local_child_doc_in_parent, updated_child_doc);
						clear_keys(updated_child_doc, local_child_doc_in_parent);
					} else {
						local_parent_doc[fieldname].push(updated_child_doc);
						if (!updated_child_doc.parent) updated_child_doc.parent = updated_doc.name;
						frappe.model.add_to_locals(updated_child_doc);
					}
				}

				// remove extra rows
				if (local_parent_doc[fieldname].length > updated_doc[fieldname].length) {
					for (
						let i = updated_doc[fieldname].length;
						i < local_parent_doc[fieldname].length;
						i++
					) {
						// clear from local
						let d = local_parent_doc[fieldname][i];
						if (locals[d.doctype] && locals[d.doctype][d.name]) {
							delete locals[d.doctype][d.name];
						}
					}
					local_parent_doc[fieldname].length = updated_doc[fieldname].length;
				}
			} else {
				// literal
				local_parent_doc[fieldname] = updated_doc[fieldname];
			}
		}

		if (
			(local_parent_doc?.on_paste_event || updated_doc.__islocal) &&
			local_parent_doc?.__newname
		) {
			updated_doc.__newname = local_parent_doc.__newname;
		}

		// clear keys on parent
		clear_keys(updated_doc, local_parent_doc);
	},
});
