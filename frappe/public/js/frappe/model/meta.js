// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.meta.docfield_map');
frappe.provide('frappe.meta.docfield_copy');
frappe.provide('frappe.meta.docfield_list');
frappe.provide('frappe.meta.doctypes');
frappe.provide("frappe.meta.precision_map");

frappe.get_meta = function(doctype) {
	return locals["DocType"][doctype];
}

$.extend(frappe.meta, {
	sync: function(doc) {
		$.each(doc.fields, function(i, df) {
			frappe.meta.add_field(df);
		})
		frappe.meta.sync_messages(doc);
		if(doc.__print_formats) frappe.model.sync(doc.__print_formats);
		if(doc.__workflow_docs) frappe.model.sync(doc.__workflow_docs);
	},

	// build docfield_map and docfield_list
	add_field: function(df) {
		frappe.provide('frappe.meta.docfield_map.' + df.parent);
		frappe.meta.docfield_map[df.parent][df.fieldname || df.label] = df;

		if(!frappe.meta.docfield_list[df.parent])
			frappe.meta.docfield_list[df.parent] = [];

		// check for repeat
		for(var i in frappe.meta.docfield_list[df.parent]) {
			var d = frappe.meta.docfield_list[df.parent][i];
			if(df.fieldname==d.fieldname)
				return; // no repeat
		}
		frappe.meta.docfield_list[df.parent].push(df);
	},

	make_docfield_copy_for: function(doctype, docname) {
		var c = frappe.meta.docfield_copy;
		if(!c[doctype])
			c[doctype] = {};
		if(!c[doctype][docname])
			c[doctype][docname] = {};

		var docfield_list = frappe.meta.docfield_list[doctype] || [];
		for(var i=0, j=docfield_list.length; i<j; i++) {
			var df = docfield_list[i];
			c[doctype][docname][df.fieldname || df.label] = copy_dict(df);
		}
	},

	get_docfield: function(dt, fn, dn) {
		return frappe.meta.get_docfield_copy(dt, dn)[fn];
	},

	get_docfields: function(doctype, name, filters) {
		var docfield_map = frappe.meta.get_docfield_copy(doctype, name);

		var docfields = frappe.meta.sort_docfields(docfield_map);

		if(filters) {
			docfields = frappe.utils.filter_dict(docfields, filters);
		}

		return docfields;
	},

	get_linked_fields: function(doctype) {
		return $.map(frappe.get_meta(doctype).fields,
			function(d) { return d.fieldtype=="Link" ? d.options : null; });
	},

	get_fields_to_check_permissions: function(doctype, name, user_permission_doctypes) {
		var fields = $.map(frappe.meta.get_docfields(doctype, name), function(df) {
			return (df.fieldtype==="Link" && df.ignore_user_permissions!==1 &&
				user_permission_doctypes.indexOf(df.options)!==-1) ? df : null;
		});

		if (user_permission_doctypes.indexOf(doctype)!==-1) {
			fields = fields.concat({label: "Name", fieldname: name, options: doctype});
		}

		return fields;
	},

	sort_docfields: function(docs) {
		return values(docs).sort(function(a, b) { return a.idx - b.idx });
	},

	get_docfield_copy: function(doctype, name) {
		if(!name) return frappe.meta.docfield_map[doctype];

		if(!(frappe.meta.docfield_copy[doctype] && frappe.meta.docfield_copy[doctype][name])) {
			frappe.meta.make_docfield_copy_for(doctype, name);
		}

		return frappe.meta.docfield_copy[doctype][name];
	},

	get_fieldnames: function(doctype, name, filters) {
		return $.map(frappe.utils.filter_dict(frappe.meta.docfield_map[doctype], filters),
			function(df) { return df.fieldname; });
	},

	has_field: function(dt, fn) {
		return frappe.meta.docfield_map[dt][fn];
	},

	get_parentfield: function(parent_dt, child_dt) {
		var df = (frappe.get_doc("DocType", parent_dt).fields || []).filter(function(d)
			{ return d.fieldtype==="Table" && options===child_dt })
		if(!df.length)
			throw "parentfield not found for " + parent_dt + ", " + child_dt;
		return df[0].fieldname;
	},

	get_label: function(dt, fn, dn) {
		if(fn==="owner") {
			return "Owner";
		} else {
			var df = this.get_docfield(dt, fn, dn);
			return (df ? df.label : "") || fn;
		}
	},

	get_print_formats: function(doctype) {
		var print_format_list = ["Standard"];
		var default_print_format = locals.DocType[doctype].default_print_format;

		var print_formats = frappe.get_list("Print Format", {doc_type: doctype})
			.sort(function(a, b) { return (a > b) ? 1 : -1; });
		$.each(print_formats, function(i, d) {
			if(!in_list(print_format_list, d.name))
				print_format_list.push(d.name);
		});

		if(default_print_format && default_print_format != "Standard") {
			var index = print_format_list.indexOf(default_print_format) - 1;
			print_format_list.sort().splice(index, 1);
			print_format_list.unshift(default_print_format);
		}

		return print_format_list;
	},

	sync_messages: function(doc) {
		if(doc.__messages) {
			$.extend(frappe._messages, doc.__messages);
		}
	},

	get_field_currency: function(df, doc) {
		var currency = frappe.boot.sysdefaults.currency;
		if(!doc && cur_frm)
			doc = cur_frm.doc;

		if(df && df.options) {
			if(doc && df.options.indexOf(":")!=-1) {
				var options = df.options.split(":");
				if(options.length==3) {
					// get reference record e.g. Company
					var docname = doc[options[1]];
					if(!docname && cur_frm) {
						docname = cur_frm.doc[options[1]];
					}
					currency = frappe.model.get_value(options[0], docname, options[2]) ||
						frappe.model.get_value(":" + options[0], docname, options[2]) ||
						currency;
				}
			} else if(doc && doc[df.options]) {
				currency = doc[df.options];
			} else if(cur_frm && cur_frm.doc[df.options]) {
				currency = cur_frm.doc[df.options];
			}
		}
		return currency;
	},

	get_field_precision: function(df, doc) {
		var precision = cint(frappe.defaults.get_default("float_precision")) || 3;
		if (df && cint(df.precision)) {
			precision = cint(df.precision);
		} else if(df && df.fieldtype === "Currency") {
			var currency = this.get_field_currency(df, doc);
			var number_format = get_number_format(currency);
			var number_format_info = get_number_format_info(number_format);
			precision = number_format_info.precision;
		}
		return precision;
	},
});
