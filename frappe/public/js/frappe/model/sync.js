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
			var doc;
			if(r.docs) {
				doc = r.docs[0];
			} else {
				if(cur_frm) doc = cur_frm.doc;
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

						if(typeof d=='object' && !d.parent)
							d.parent = doc.name;

						frappe.model.add_to_locals(d);
					}
				}
			}
		}
	},
	update_in_locals: function(d) {
		// update values in the existing local doc instead of replacing
		let local_doc = locals[d.doctype][d.name];
		for (let fieldname in d) {
			if (local_doc[fieldname] instanceof Array) {
				// table
				if (!(d[fieldname] instanceof Array)) {
					d[fieldname] = [];
				}
				// child table, override each row and append new rows if required
				for (let i=0; i < d[fieldname].length; i++ ) {
					if (local_doc[fieldname][i]) {
						// row exists, just copy the values
						Object.assign(local_doc[fieldname][i], d[fieldname][i]);
					} else {
						local_doc[fieldname].push(d[fieldname][i]);
					}
				}

				// remove extra rows
				if (local_doc[fieldname].length > d[fieldname].length) {
					local_doc[fieldname].length = d[fieldname].length;
				}
			} else {
				// literal
				local_doc[fieldname] = d[fieldname];
			}
		}
	}

});
