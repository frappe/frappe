// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form.handlers");

frappe.ui.form.on = frappe.ui.form.on_change = function(doctype, fieldname, handler) {
	var add_handler = function(fieldname, handler) {
		if(!frappe.ui.form.handlers[doctype]) {
			frappe.ui.form.handlers[doctype] = {};
		}
		if(!frappe.ui.form.handlers[doctype][fieldname]) {
			frappe.ui.form.handlers[doctype][fieldname] = [];
		}
		frappe.ui.form.handlers[doctype][fieldname].push(handler);

		// add last handler to events so it can be called as
		// frm.events.handler(frm)
		cur_frm.events[fieldname] = handler;
	}

	if (!handler && $.isPlainObject(fieldname)) {
		// a dict of handlers {fieldname: handler, ...}
		for (var key in fieldname) {
			var fn = fieldname[key];
			if (typeof fn === "function") {
				add_handler(key, fn);
			}
		}
	} else {
		add_handler(fieldname, handler);
	}
}

frappe.ui.form.trigger = function(doctype, fieldname, callback) {
	cur_frm.script_manager.trigger(fieldname, doctype, null, callback);
}

frappe.ui.form.ScriptManager = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
	},
	make: function(ControllerClass) {
		this.frm.cscript = $.extend(this.frm.cscript, new ControllerClass({frm: this.frm}));
	},
	trigger: function(event_name, doctype, name, callback) {
		var me = this;
		doctype = doctype || this.frm.doctype;
		name = name || this.frm.docname;
		handlers = this.get_handlers(event_name, doctype, name, callback);
		if(callback) handlers.push(callback);

		return $.when.apply($, $.map(handlers, function(fn) { return fn(); }));
	},
	get_handlers: function(event_name, doctype, name, callback) {
		var handlers = [];
		var me = this;
		if(frappe.ui.form.handlers[doctype] && frappe.ui.form.handlers[doctype][event_name]) {
			$.each(frappe.ui.form.handlers[doctype][event_name], function(i, fn) {
				handlers.push(function() { return fn(me.frm, doctype, name) });
			});
		}
		if(this.frm.cscript[event_name]) {
			handlers.push(function() { return me.frm.cscript[event_name](me.frm.doc, doctype, name); });
		}
		if(this.frm.cscript["custom_" + event_name]) {
			handlers.push(function() { return me.frm.cscript["custom_" + event_name](me.frm.doc, doctype, name); });
		}
		return handlers;
	},
	setup: function() {
		var doctype = this.frm.meta;
		var me = this;

		// js
		var cs = doctype.__js;
		if(cs) {
			var tmp = eval(cs);
		}

		// setup add fetch
		$.each(this.frm.fields, function(i, field) {
			var df = field.df;
			if((df.fieldtype==="Read Only" || df.read_only==1) && df.options && df.options.indexOf(".")!=-1) {
				var parts = df.options.split(".");
				me.frm.add_fetch(parts[0], parts[1], df.fieldname);
			}
		});

		// css
		doctype.__css && frappe.dom.set_style(doctype.__css);

	},
	log_error: function(caller, e) {
		show_alert("Error in Client Script.");
		console.group && console.group();
		console.log("----- error in client script -----");
		console.log("method: " + caller);
		console.log(e);
		console.log("error message: " + e.message);
		console.trace && console.trace();
		console.log("----- end of error message -----");
		console.group && console.groupEnd();
	},
	validate_link_and_fetch: function(df, doctype, docname, value, callback) {
		var me = this;

		if(value) {
			var fetch = '';

			if(this.frm && this.frm.fetch_dict[df.fieldname])
				fetch = this.frm.fetch_dict[df.fieldname].columns.join(', ');

			return frappe.call({
				method:'frappe.desk.form.utils.validate_link',
				type: "GET",
				args: {
					'value': value,
					'options': doctype,
					'fetch': fetch
				},
				no_spinner: true,
				callback: function(r) {
					if(r.message=='Ok') {
						if(r.fetch_values)
							me.set_fetch_values(df, docname, r.fetch_values);
						if(callback) callback(value);
					} else {
						if(callback) callback("");
					}
				}
			});
		} else if(callback) {
			callback(value);
		}
	},
	set_fetch_values: function(df, docname, fetch_values) {
		var fl = this.frm.fetch_dict[df.fieldname].fields;
		for(var i=0; i < fl.length; i++) {
			frappe.model.set_value(df.parent, docname, fl[i], fetch_values[i], df.fieldtype);
		}
	},
	copy_from_first_row: function(parentfield, current_row, fieldnames) {
		var doclist = this.frm.doc[parentfield];
		if(doclist.length===1 || doclist[0]===current_row) return;

		$.each(fieldnames, function(i, fieldname) {
			current_row[fieldname] = doclist[0][fieldname];
		});
	}
});
