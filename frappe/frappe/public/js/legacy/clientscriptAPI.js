// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

get_server_fields = function(method, arg, table_field, doc, dt, dn, allow_edit, call_back) {
	frappe.dom.freeze();
	if($.isPlainObject(arg)) arg = JSON.stringify(arg);
	return $c('runserverobj',
		args={'method': method, 'docs': JSON.stringify(doc), 'arg': arg },
	function(r, rt) {
		frappe.dom.unfreeze();
		if (r.message)  {
			var d = locals[dt][dn];
			var field_dict = r.message;
			for(var key in field_dict) {
				d[key] = field_dict[key];
				if (table_field)
					refresh_field(key, d.name, table_field);
				else
					refresh_field(key);
			}
		}
		if(call_back){
			doc = locals[doc.doctype][doc.name];
			call_back(doc, dt, dn);
		}
    }
  );
}


set_multiple = function (dt, dn, dict, table_field) {
	var d = locals[dt][dn];
	for(var key in dict) {
		d[key] = dict[key];
		if (table_field)
			refresh_field(key, d.name, table_field);
		else
			refresh_field(key);
	}
}

refresh_many = function (flist, dn, table_field) {
	for(var i in flist) {
		if (table_field)
			refresh_field(flist[i], dn, table_field);
		else
			refresh_field(flist[i]);
	}
}

set_field_tip = function(n,txt) {
	var df = frappe.meta.get_docfield(cur_frm.doctype, n, cur_frm.docname);
	if(df)df.description = txt;

	if(cur_frm && cur_frm.fields_dict) {
		if(cur_frm.fields_dict[n])
			cur_frm.fields_dict[n].comment_area.innerHTML = replace_newlines(txt);
		else
			console.log('[set_field_tip] Unable to set field tip: ' + n);
	}
}

refresh_field = function(n, docname, table_field) {
	// multiple
	if(typeof n==typeof [])
		refresh_many(n, docname, table_field);

	if(table_field && cur_frm.fields_dict[table_field].grid.grid_rows_by_docname) { // for table
		cur_frm.fields_dict[table_field].grid.grid_rows_by_docname[docname].refresh_field(n);
	} else if(cur_frm) {
		cur_frm.refresh_field(n)
	}
}

set_field_options = function(n, txt) {
	cur_frm.set_df_property(n, 'options', txt)
}

set_field_permlevel = function(n, level) {
	cur_frm.set_df_property(n, 'permlevel', level)
}

toggle_field = function(n, hidden) {
	var df = frappe.meta.get_docfield(cur_frm.doctype, n, cur_frm.docname);
	if(df) {
		df.hidden = hidden;
		refresh_field(n);
	}
	else {
		console.log((hidden ? "hide_field" : "unhide_field") + " cannot find field " + n);
	}
}

hide_field = function(n) {
	if(cur_frm) {
		if(n.substr) toggle_field(n, 1);
		else { for(var i in n) toggle_field(n[i], 1) }
	}
}

unhide_field = function(n) {
	if(cur_frm) {
		if(n.substr) toggle_field(n, 0);
		else { for(var i in n) toggle_field(n[i], 0) }
	}
}

get_field_obj = function(fn) {
	return cur_frm.fields_dict[fn];
}

// set missing values in given doc
set_missing_values = function(doc, dict) {
	// dict contains fieldname as key and "default value" as value
	var fields_to_set = {};

	$.each(dict, function(i, v) { if (!doc[i]) { fields_to_set[i] = v; } });

	if (fields_to_set) { set_multiple(doc.doctype, doc.name, fields_to_set); }
}

_f.Frm.prototype.get_doc = function() {
	return locals[this.doctype][this.docname];
}

_f.Frm.prototype.field_map = function(fnames, fn) {
	if(typeof fnames==='string') {
		if(fnames == '*') {
			fnames = keys(this.fields_dict);
		} else {
			fnames = [fnames];
		}
	}
	$.each(fnames, function(i,fieldname) {
		//var field = cur_frm.fields_dict[f]; - much better design
		var field = frappe.meta.get_docfield(cur_frm.doctype, fieldname, cur_frm.docname);
		if(field) {
			fn(field);
			cur_frm.refresh_field(fieldname);
		};
	})

}

_f.Frm.prototype.set_df_property = function(fieldname, property, value) {
	var field = frappe.meta.get_docfield(cur_frm.doctype, fieldname, cur_frm.docname)
	if(field) {
		field[property] = value;
		cur_frm.refresh_field(fieldname);
	};
}

_f.Frm.prototype.toggle_enable = function(fnames, enable) {
	cur_frm.field_map(fnames, function(field) {
		field.read_only = enable ? 0 : 1; });
}

_f.Frm.prototype.toggle_reqd = function(fnames, mandatory) {
	cur_frm.field_map(fnames, function(field) { field.reqd = mandatory ? true : false; });
}

_f.Frm.prototype.toggle_display = function(fnames, show) {
	cur_frm.field_map(fnames, function(field) { field.hidden = show ? 0 : 1; });
}

_f.Frm.prototype.call_server = function(method, args, callback) {
	return $c_obj(cur_frm.doc, method, args, callback);
}

_f.Frm.prototype.get_files = function() {
	return cur_frm.attachments
		? frappe.utils.sort(cur_frm.attachments.get_attachments(), "file_name", "string")
		: [] ;
}

_f.Frm.prototype.set_query = function(fieldname, opt1, opt2) {
	var func = (typeof opt1=="function") ? opt1 : opt2;
	if(opt2) {
		this.fields_dict[opt1].grid.get_field(fieldname).get_query = func;
	} else {
		this.fields_dict[fieldname].get_query = func;
	}
}

_f.Frm.prototype.set_value_if_missing = function(field, value) {
	this.set_value(field, value, true);
}

_f.Frm.prototype.set_value = function(field, value, if_missing) {
	var me = this;
	var _set = function(f, v) {
		var fieldobj = me.fields_dict[f];
		if(fieldobj) {
			if(!if_missing || !frappe.model.has_value(me.doctype, me.doc.name, f)) {
				if(fieldobj.df.fieldtype==="Table" && $.isArray(v)) {

					frappe.model.clear_table(me.doc, fieldobj.df.fieldname);

					$.each(v, function(i, d) {
						var child = frappe.model.add_child(me.doc, fieldobj.df.options,
							fieldobj.df.fieldname, i+1);
						$.extend(child, d);
					});

					me.refresh_field(f);
				} else {
					frappe.model.set_value(me.doctype, me.doc.name, f, v);
				}
			}
		}
	}

	if(typeof field=="string") {
		_set(field, value)
	} else if($.isPlainObject(field)) {
		$.each(field, function(f, v) {
			_set(f, v);
		})
	}
}

_f.Frm.prototype.call = function(opts) {
	var me = this;
	if(!opts.doc) {
		if(opts.method.indexOf(".")===-1)
			opts.method = frappe.model.get_server_module_name(me.doctype) + "." + opts.method;
		opts.original_callback = opts.callback;
		opts.callback = function(r) {
			if($.isPlainObject(r.message)) {
				if(opts.child) {
					// update child doc
					opts.child = locals[opts.child.doctype][opts.child.name];
					$.extend(opts.child, r.message);
					me.fields_dict[opts.child.parentfield].refresh();
				} else {
					// update parent doc
					me.set_value(r.message);
				}
			}
			opts.original_callback && opts.original_callback(r);
		}
	} else {
		opts.original_callback = opts.callback;
		opts.callback = function(r) {
			if(!r.exc) me.refresh_fields();

			opts.original_callback && opts.original_callback(r);
		}

	}
	return frappe.call(opts);
}

_f.Frm.prototype.get_field = function(field) {
	return cur_frm.fields_dict[field];
};

_f.Frm.prototype.new_doc = function(doctype, field) {
	frappe._from_link = field; frappe._from_link_scrollY = scrollY;
	new_doc(doctype);
}


_f.Frm.prototype.set_read_only = function() {
	var perm = [];
	$.each(frappe.perm.get_perm(cur_frm.doc.doctype), function(i, p) {
		perm[p.permlevel || 0] = {read:1};
	});
	cur_frm.perm = perm;
}

_f.Frm.prototype.get_formatted = function(fieldname) {
	return frappe.format(this.doc[fieldname],
			frappe.meta.get_docfield(this.doctype, fieldname, this.docname),
			{no_icon:true}, this.doc);
}
