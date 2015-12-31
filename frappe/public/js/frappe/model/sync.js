// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

$.extend(frappe.model, {
	docinfo: {},
	sync: function(r) {
		/* docs:
			extract docs, docinfo (attachments, comments, assignments)
			from incoming request and set in `locals` and `frappe.model.docinfo`
		*/

		if(!r.docs && !r.docinfo) r = {docs:r};

		if($.isPlainObject(r.docs)) r.docs = [r.docs];

		if(r.docs) {
			var last_parent_name = null;
			var dirty = [];

			for(var i=0, l=r.docs.length; i<l; i++) {
				var d = r.docs[i];

				frappe.model.add_to_locals(d);

				d.__last_sync_on = new Date();

				if(d.doctype==="DocType") {
					frappe.meta.sync(d);
				}

				if(cur_frm && cur_frm.doctype==d.doctype && cur_frm.docname==d.name) {
					cur_frm.doc = d;
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

			if(cur_frm && dirty.indexOf(cur_frm.doctype)!==-1) cur_frm.dirty();

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
	}

});
