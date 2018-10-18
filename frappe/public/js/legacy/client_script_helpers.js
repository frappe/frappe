// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
/* eslint-disable no-console */

window.get_server_fields = function(method, arg, table_field, doc, dt, dn, allow_edit, call_back) {
	console.warn("This function 'get_server_fields' has been deprecated and will be removed soon.");
	frappe.dom.freeze();
	if($.isPlainObject(arg)) arg = JSON.stringify(arg);
	return $c('runserverobj', {'method': method, 'docs': JSON.stringify(doc), 'arg': arg },
		function(r) {
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
		});
};


window.set_multiple = function(dt, dn, dict, table_field) {
	var d = locals[dt][dn];
	for(var key in dict) {
		d[key] = dict[key];
		if (table_field)
			refresh_field(key, d.name, table_field);
		else
			refresh_field(key);
	}
};

window.refresh_many = function(flist, dn, table_field) {
	for(var i in flist) {
		if (table_field)
			refresh_field(flist[i], dn, table_field);
		else
			refresh_field(flist[i]);
	}
};

window.set_field_tip = function(n,txt) {
	var df = frappe.meta.get_docfield(cur_frm.doctype, n, cur_frm.docname);
	if(df)df.description = txt;

	if(cur_frm && cur_frm.fields_dict) {
		if(cur_frm.fields_dict[n])
			cur_frm.fields_dict[n].comment_area.innerHTML = frappe.utils.replace_newlines(txt);
		else
			console.log('[set_field_tip] Unable to set field tip: ' + n);
	}
};

window.refresh_field = function(n, docname, table_field) {
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
		cur_frm.refresh_field(n);
	}
};

window.set_field_options = function(n, txt) {
	cur_frm.set_df_property(n, 'options', txt);
};

window.set_field_permlevel = function(n, level) {
	cur_frm.set_df_property(n, 'permlevel', level);
};

window.toggle_field = function(n, hidden) {
	var df = frappe.meta.get_docfield(cur_frm.doctype, n, cur_frm.docname);
	if(df) {
		df.hidden = hidden;
		refresh_field(n);
	} else {
		console.log((hidden ? "hide_field" : "unhide_field") + " cannot find field " + n);
	}
};

window.hide_field = function(n) {
	if(cur_frm) {
		if(n.substr) toggle_field(n, 1);
		else {
			for(var i in n) toggle_field(n[i], 1);
		}
	}
};

window.unhide_field = function(n) {
	if(cur_frm) {
		if(n.substr) toggle_field(n, 0);
		else {
			for(var i in n) toggle_field(n[i], 0);
		}
	}
};

window.get_field_obj = function(fn) {
	return cur_frm.fields_dict[fn];
};

_f.Frm.prototype.get_doc = function() {
	return locals[this.doctype][this.docname];
};

_f.Frm.prototype.set_currency_labels = function(fields_list, currency, parentfield) {
	// To set the currency in the label
	// For example Total Cost(INR), Total Cost(USD)

	var me = this;
	var doctype = parentfield ? this.fields_dict[parentfield].grid.doctype : this.doc.doctype;
	var field_label_map = {};
	var grid_field_label_map = {};

	$.each(fields_list, function(i, fname) {
		var docfield = frappe.meta.docfield_map[doctype][fname];
		if(docfield) {
			var label = __(docfield.label || "").replace(/\([^\)]*\)/g, ""); // eslint-disable-line
			if(parentfield) {
				grid_field_label_map[doctype + "-" + fname] =
					label.trim() + " (" + __(currency) + ")";
			} else {
				field_label_map[fname] = label.trim() + " (" + currency + ")";
			}
		}
	});

	$.each(field_label_map, function(fname, label) {
		me.fields_dict[fname].set_label(label);
	});

	$.each(grid_field_label_map, function(fname, label) {
		fname = fname.split("-");
		var df = frappe.meta.get_docfield(fname[0], fname[1], me.doc.name);
		if(df) df.label = label;
	});
};

_f.Frm.prototype.field_map = function(fnames, fn) {
	if(typeof fnames==='string') {
		if(fnames == '*') {
			fnames = Object.keys(this.fields_dict);
		} else {
			fnames = [fnames];
		}
	}
	for (var i=0, l=fnames.length; i<l; i++) {
		var fieldname = fnames[i];
		var field = frappe.meta.get_docfield(cur_frm.doctype, fieldname, this.docname);
		if(field) {
			fn(field);
			this.refresh_field(fieldname);
		}
	}
};

_f.Frm.prototype.get_docfield = function(fieldname1, fieldname2) {
	if(fieldname2) {
		// for child
		var doctype = this.get_docfield(fieldname1).options;
		return frappe.meta.get_docfield(doctype, fieldname2, this.docname);
	} else {
		// for parent
		return frappe.meta.get_docfield(this.doctype, fieldname1, this.docname);
	}
};

_f.Frm.prototype.set_df_property = function(fieldname, property, value, docname, table_field) {
	var df;
	if (!docname && !table_field){
		df = this.get_docfield(fieldname);
	} else {
		var grid = this.fields_dict[table_field].grid,
			fname = frappe.utils.filter_dict(grid.docfields, {'fieldname': fieldname});
		if (fname && fname.length)
			df = frappe.meta.get_docfield(fname[0].parent, fieldname, docname);
	}
	if(df && df[property] != value) {
		df[property] = value;
		refresh_field(fieldname, table_field);
	}
};

_f.Frm.prototype.toggle_enable = function(fnames, enable) {
	this.field_map(fnames, function(field) {
		field.read_only = enable ? 0 : 1;
	});
};

_f.Frm.prototype.toggle_reqd = function(fnames, mandatory) {
	this.field_map(fnames, function(field) {
		field.reqd = mandatory ? true : false;
	});
};

_f.Frm.prototype.toggle_display = function(fnames, show) {
	this.field_map(fnames, function(field) {
		field.hidden = show ? 0 : 1;
	});
};

_f.Frm.prototype.call_server = function(method, args, callback) {
	return $c_obj(this.doc, method, args, callback);
};

_f.Frm.prototype.get_files = function() {
	return this.attachments
		? frappe.utils.sort(this.attachments.get_attachments(), "file_name", "string")
		: [] ;
};

_f.Frm.prototype.set_query = function(fieldname, opt1, opt2) {
	if(opt2) {
		// on child table
		// set_query(fieldname, parent fieldname, query)
		this.fields_dict[opt1].grid.get_field(fieldname).get_query = opt2;
	} else {
		// on parent table
		// set_query(fieldname, query)
		if(this.fields_dict[fieldname]) {
			this.fields_dict[fieldname].get_query = opt1;
		}
	}
};

_f.Frm.prototype.set_value_if_missing = function(field, value) {
	return this.set_value(field, value, true);
};

_f.Frm.prototype.clear_table = function(fieldname) {
	frappe.model.clear_table(this.doc, fieldname);
};

_f.Frm.prototype.add_child = function(fieldname, values) {
	var doc = frappe.model.add_child(this.doc, frappe.meta.get_docfield(this.doctype, fieldname).options, fieldname);
	if(values) {
		// Values of unique keys should not be overridden
		var d = {};
		var unique_keys = ["idx", "name"];

		Object.keys(values).map((key) => {
			if(!unique_keys.includes(key)) {
				d[key] = values[key];
			}
		});

		$.extend(doc, d);
	}
	return doc;
};

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
					return Promise.resolve();
				} else {
					return frappe.model.set_value(me.doctype, me.doc.name, f, v);
				}
			}
		} else {
			frappe.msgprint(__("Field {0} not found.",[f]));
			throw "frm.set_value";
		}
	};

	if(typeof field=="string") {
		return _set(field, value);
	} else if($.isPlainObject(field)) {
		let tasks = [];
		for (let f in field) {
			let v = field[f];
			if(me.get_field(f)) {
				tasks.push(() => _set(f, v));
			}
		}
		return frappe.run_serially(tasks);
	}
};

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
					for (var key in r.message) {
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
		};
	} else {
		opts.original_callback = opts.callback;
		opts.callback = function(r) {
			if(!r.exc) me.refresh_fields();

			opts.original_callback && opts.original_callback(r);
		};

	}
	return frappe.call(opts);
};

_f.Frm.prototype.get_field = function(field) {
	return this.fields_dict[field];
};


_f.Frm.prototype.set_read_only = function() {
	var perm = [];
	var docperms = frappe.perm.get_perm(this.doc.doctype);
	for (var i=0, l=docperms.length; i<l; i++) {
		var p = docperms[i];
		perm[p.permlevel || 0] = {read:1, print:1, cancel:1};
	}
	this.perm = perm;
};

_f.Frm.prototype.trigger = function(event) {
	return this.script_manager.trigger(event);
};

_f.Frm.prototype.get_formatted = function(fieldname) {
	return frappe.format(this.doc[fieldname],
		frappe.meta.get_docfield(this.doctype, fieldname, this.docname),
		{no_icon:true}, this.doc);
};

_f.Frm.prototype.open_grid_row = function() {
	return frappe.ui.form.get_open_grid_form();
};

_f.Frm.prototype.is_new = function() {
	return this.doc.__islocal;
};

_f.Frm.prototype.get_title = function() {
	if(this.meta.title_field) {
		return this.doc[this.meta.title_field];
	} else {
		return this.doc.name;
	}
};

_f.Frm.prototype.get_selected = function() {
	// returns list of children that are selected. returns [parentfield, name] for each
	var selected = {}, me = this;
	frappe.meta.get_table_fields(this.doctype).forEach(function(df) {
		var _selected = me.fields_dict[df.fieldname].grid.get_selected();
		if(_selected.length) {
			selected[df.fieldname] = _selected;
		}
	});
	return selected;
};

_f.Frm.prototype.has_mapper = function() {
	// hackalert!
	// if open_mapped_doc is mentioned in the custom script, then mapper exists
	if(this._has_mapper === undefined) {
		this._has_mapper = (this.meta.__js && this.meta.__js.search('open_mapped_doc')!==-1) ?
			true: false;
	}
	return this._has_mapper;
};

_f.Frm.prototype.set_indicator_formatter = function(fieldname, get_color, get_text) {
	// get doctype from parent
	var doctype;
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
		});
	}

	frappe.meta.docfield_map[doctype][fieldname].formatter =
		function(value, df, options, doc) {
			if(value) {
				var label;
				if(get_text) {
					label = get_text(doc);
				} else if(frappe.form.link_formatters[df.options]) {
					label = frappe.form.link_formatters[df.options](value, doc);
				} else {
					label = value;
				}

				const escaped_name = encodeURIComponent(value);
				return repl('<a class="indicator %(color)s" href="#Form/%(doctype)s/%(name)s">%(label)s</a>', {
					color: get_color(doc || {}),
					doctype: df.options,
					name: escaped_name,
					label: label
				});
			} else {
				return '';
			}
		};
};

_f.Frm.prototype.can_create = function(doctype) {
	// return true or false if the user can make a particlar doctype
	// will check permission, `can_make_methods` if exists, or will decided on
	// basis of whether the document is submittable
	if(!frappe.model.can_create(doctype)) {
		return false;
	}

	if(this.custom_make_buttons && this.custom_make_buttons[doctype]) {
		// custom buttons are translated and so are the keys
		const key = __(this.custom_make_buttons[doctype]);
		// if the button is present, then show make
		return !!this.custom_buttons[key];
	}

	if(this.can_make_methods && this.can_make_methods[doctype]) {
		return this.can_make_methods[doctype](this);
	} else {
		if(this.meta.is_submittable && !this.doc.docstatus==1) {
			return false;
		} else {
			return true;
		}
	}
};

_f.Frm.prototype.make_new = function(doctype) {
	// make new doctype from the current form
	// will handover to `make_methods` if defined
	// or will create and match link fields
	var me = this;
	if(this.make_methods && this.make_methods[doctype]) {
		return this.make_methods[doctype](this);
	} else if(this.custom_make_buttons && this.custom_make_buttons[doctype]) {
		this.custom_buttons[__(this.custom_make_buttons[doctype])].trigger('click');
	} else {
		frappe.model.with_doctype(doctype, function() {
			var new_doc = frappe.model.get_new_doc(doctype);

			// set link fields (if found)
			frappe.get_meta(doctype).fields.forEach(function(df) {
				if(df.fieldtype==='Link' && df.options===me.doctype) {
					new_doc[df.fieldname] = me.doc.name;
				}
			});

			frappe.ui.form.make_quick_entry(doctype, null, null, new_doc);
			// frappe.set_route('Form', doctype, new_doc.name);
		});
	}
};

_f.Frm.prototype.update_in_all_rows = function(table_fieldname, fieldname, value) {
	// update the child value in all tables where it is missing
	if(!value) return;
	var cl = this.doc[table_fieldname] || [];
	for(var i = 0; i < cl.length; i++){
		if(!cl[i][fieldname]) cl[i][fieldname] = value;
	}
	refresh_field("items");
};

_f.Frm.prototype.get_sum = function(table_fieldname, fieldname) {
	let sum = 0;
	for (let d of (this.doc[table_fieldname] || [])) {
		sum += d[fieldname];
	}
	return sum;
};
