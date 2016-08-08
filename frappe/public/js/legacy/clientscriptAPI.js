// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

get_server_fields = function(method, arg, table_field, doc, dt, dn, allow_edit, call_back) {
	console.warn("This function 'get_server_fields' has been deprecated and will be removed soon.");
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

	if (n && typeof n==='string' && table_field){
		var grid = cur_frm.fields_dict[table_field].grid,
			field = frappe.utils.filter_dict(grid.docfields, {fieldname: n});
		if (field && field.length){
			field = field[0];
			var meta = frappe.meta.get_docfield(field.parent, field.fieldname, docname);
			$.extend(field, meta);
			if (docname){
				cur_frm.fields_dict[table_field].grid.grid_rows_by_docname[docname].refresh_field(n);
			} else {
				cur_frm.fields_dict[table_field].grid.refresh();
			}
		}
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

	for (var i in dict) {
		var v = dict[i];
		if (!doc[i]) {
			fields_to_set[i] = v;
		}
	}

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
	for (var i=0, l=fnames.length; i<l; i++) {
		var fieldname = fnames[i];
		var field = frappe.meta.get_docfield(cur_frm.doctype, fieldname, cur_frm.docname);
		if(field) {
			fn(field);
			cur_frm.refresh_field(fieldname);
		};
	}
}

_f.Frm.prototype.get_docfield = function(fieldname1, fieldname2) {
	if(fieldname2) {
		// for child
		var doctype = this.get_docfield(fieldname1).options;
		return frappe.meta.get_docfield(doctype, fieldname2, this.docname);
	} else {
		// for parent
		return frappe.meta.get_docfield(this.doctype, fieldname1, this.docname);
	}
}

_f.Frm.prototype.set_df_property = function(fieldname, property, value, docname, table_field) {
	if (!docname && !table_field){
		var field = this.get_docfield(fieldname);
	} else {
		var grid = cur_frm.fields_dict[table_field].grid,
		fname = frappe.utils.filter_dict(grid.docfields, {'fieldname': fieldname});
		if (fname && fname.length)
			var field = frappe.meta.get_docfield(fname[0].parent, fieldname, docname);
	}
	if(field) {
		field[property] = value;
		refresh_field(fieldname, table_field);
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
	if(opt2) {
		this.fields_dict[opt1].grid.get_field(fieldname).get_query = opt2;
	} else {
		this.fields_dict[fieldname].get_query = opt1;
	}
}

_f.Frm.prototype.set_value_if_missing = function(field, value) {
	this.set_value(field, value, true);
}

_f.Frm.prototype.clear_table = function(fieldname) {
	frappe.model.clear_table(this.doc, fieldname);
}

_f.Frm.prototype.add_child = function(fieldname, values) {
	var doc = frappe.model.add_child(this.doc, frappe.meta.get_docfield(this.doctype, fieldname).options, fieldname);
	if(values) {
		$.extend(doc, values);
	}
	return doc;
}

_f.Frm.prototype.set_value = function(field, value, if_missing) {
	var me = this;
	var _set = function(f, v) {
		var fieldobj = me.fields_dict[f];
		if(fieldobj) {
			if(!if_missing || !frappe.model.has_value(me.doctype, me.doc.name, f)) {
				if(fieldobj.df.fieldtype==="Table" && $.isArray(v)) {

					frappe.model.clear_table(me.doc, fieldobj.df.fieldname);

					for (var i=0, j=v.length; i < j; i++) {
						var d = v[i];
						var child = frappe.model.add_child(me.doc, fieldobj.df.options,
							fieldobj.df.fieldname, i+1);
						$.extend(child, d);
					}

					me.refresh_field(f);

				} else {
					frappe.model.set_value(me.doctype, me.doc.name, f, v);
				}
			}
		} else {
			msgprint("Field " + f + " not found.");
			throw "frm.set_value";
		}
	}

	if(typeof field=="string") {
		_set(field, value)
	} else if($.isPlainObject(field)) {
		for (var f in field) {
			var v = field[f];
			if(me.get_field(f)) {
				_set(f, v);
			}
		}
	}
}

_f.Frm.prototype.call = function(opts, args, callback) {
	var me = this;
	if(typeof opts==='string') {
		// called as frm.call('do_this', {with_arg: 'arg'});
		opts = {
			method: opts,
			doc: this.doc,
			args: args,
			callback: callback
		};
	}
	if(!opts.doc) {
		if(opts.method.indexOf(".")===-1)
			opts.method = frappe.model.get_server_module_name(me.doctype) + "." + opts.method;
		opts.original_callback = opts.callback;
		opts.callback = function(r) {
			if($.isPlainObject(r.message)) {
				if(opts.child) {
					// update child doc
					opts.child = locals[opts.child.doctype][opts.child.name];

					var std_field_list = ["doctype"].concat(frappe.model.std_fields_list);
					for (key in r.message) {
						if (std_field_list.indexOf(key)===-1) {
							opts.child[key] = r.message[key];
						}
					}

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


_f.Frm.prototype.set_read_only = function() {
	var perm = [];
	var docperms = frappe.perm.get_perm(cur_frm.doc.doctype);
	for (var i=0, l=docperms.length; i<l; i++) {
		var p = docperms[i];
		perm[p.permlevel || 0] = {read:1};
	}
	cur_frm.perm = perm;
}

_f.Frm.prototype.trigger = function(event) {
	this.script_manager.trigger(event);
};

_f.Frm.prototype.get_formatted = function(fieldname) {
	return frappe.format(this.doc[fieldname],
			frappe.meta.get_docfield(this.doctype, fieldname, this.docname),
			{no_icon:true}, this.doc);
}

_f.Frm.prototype.open_grid_row = function() {
	return frappe.ui.form.get_open_grid_form();
}

_f.Frm.prototype.is_new = function() {
	return this.doc.__islocal;
}

_f.Frm.prototype.get_title = function() {
	if(this.meta.title_field) {
		return this.doc[this.meta.title_field];
	} else {
		return this.doc.name;
	}
}

_f.Frm.prototype.set_indicator_formatter = function(fieldname, get_color, get_text) {
	// get doctype from parent
	if(frappe.meta.docfield_map[this.doctype][fieldname]) {
		doctype = this.doctype;
	} else {
		frappe.meta.get_table_fields(this.doctype).every(function(df) {
			if(frappe.meta.docfield_map[df.options][fieldname]) {
				doctype = df.options;
				return false;
			} else {
				return true;
			}
		})
	}

	frappe.meta.get_docfield(doctype, fieldname, this.doc.name).formatter =
		function(value, df, options, doc) {
			if(value) {
				return repl('<a class="indicator %(color)s" href="#Form/%(doctype)s/%(name)s">%(label)s</a>', {
					color: get_color(doc),
					doctype: df.options,
					name: value,
					label: get_text ? get_text(doc) : value
				});
			} else {
				return '';
			}
		};

}