// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

$.extend(frappe.model, {
	docinfo: {},
	sync: function(r) {
		/* docs:
			extract docs, docinfo (attachments, comments, assignments)
			from incoming request and set in `locals` and `frappe.model.docinfo`
		*/
		var isPlain;
		if(!r.docs && !r.docinfo) r = {docs:r};

		isPlain = $.isPlainObject(r.docs);
		if(isPlain) r.docs = [r.docs];

		if(r.docs) {
			var last_parent_name = null;

			for(var i=0, l=r.docs.length; i<l; i++) {
				var d = r.docs[i];

				if (locals[d.doctype] && locals[d.doctype][d.name]) {
					// update values
					frappe.model.update_in_locals(d);
				} else {
					frappe.model.add_to_locals(d);
				}

				d.__last_sync_on = new Date();

				if(d.doctype==="DocType") {
					frappe.meta.sync(d);
				}

				if(d.localname) {
					frappe.model.new_names[d.localname] = d.name;
					$(document).trigger('rename', [d.doctype, d.localname, d.name]);
					delete locals[d.doctype][d.localname];

					// update docinfo to new dict keys
					if(i===0) {
						frappe.model.docinfo[d.doctype][d.name] = frappe.model.docinfo[d.doctype][d.localname];
						frappe.model.docinfo[d.doctype][d.localname] = undefined;
					}
				}
			}



		}

		// set docinfo (comments, assign, attachments)
		if(r.docinfo) {
			if(r.docs) {
				var doc = r.docs[0];
			} else {
				if(cur_frm)
					var doc = cur_frm.doc;
			}
			if(doc) {
				if(!frappe.model.docinfo[doc.doctype])
					frappe.model.docinfo[doc.doctype] = {};
				frappe.model.docinfo[doc.doctype][doc.name] = r.docinfo;
			}
		}

		return r.docs;
	},
	add_to_locals: function(doc) {
		if(!locals[doc.doctype])
			locals[doc.doctype] = {};

		if(!doc.name && doc.__islocal) { // get name (local if required)
			if(!doc.parentfield) frappe.model.clear_doc(doc);

			doc.name = frappe.model.get_new_name(doc.doctype);

			if(!doc.parentfield) frappe.provide("frappe.model.docinfo." + doc.doctype + "." + doc.name);
		}

		locals[doc.doctype][doc.name] = doc;

		// add child docs to locals
		if(!doc.parentfield) {
			for(var i in doc) {
				var value = doc[i];

				if($.isArray(value)) {
					for (var x=0, y=value.length; x < y; x++) {
						var d = value[x];

						if(!d.parent)
							d.parent = doc.name;

						frappe.model.add_to_locals(d);
					}
				}
			}
		}
	},
	update_in_locals: function(doc) {
		// update values in the existing local doc instead of replacing
		let local_doc = locals[doc.doctype][doc.name];
		for (let fieldname in doc) {
			if (local_doc[fieldname] instanceof Array) {
				// table
				if (!(doc[fieldname] instanceof Array)) {
					doc[fieldname] = [];
				}
				// child table, override each row and append new rows if required
				for (let i=0; i < doc[fieldname].length; i++ ) {
					let d = doc[fieldname][i];
					if (local_doc[fieldname][i]) {
						// row exists, just copy the values
						Object.assign(local_doc[fieldname][i], d);
					} else {
						local_doc[fieldname].push(d);
						if (!d.parent) d.parent = doc.name;
						frappe.model.add_to_locals(d);
					}
				}

				// remove extra rows
				if (local_doc[fieldname].length > doc[fieldname].length) {
					for (let i = doc[fieldname].length; i < local_doc[fieldname].length; i++) {

						// clear from local
						let d = local_doc[fieldname][i];
						if (locals[d.doctype] && locals[d.doctype][d.name]) {
							delete locals[d.doctype][d.name];
						}
					}
					local_doc[fieldname].length = doc[fieldname].length;


				}
			} else {
				// literal
				local_doc[fieldname] = doc[fieldname];
			}
		}
	}

});
