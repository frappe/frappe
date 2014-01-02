// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.provide("wn.ui.form.handlers");

wn.ui.form.on_change = function(doctype, fieldname, handler) {
	if(!wn.ui.form.handlers[doctype]) {
		wn.ui.form.handlers[doctype] = {};
	}
	if(!wn.ui.form.handlers[doctype][fieldname]) {
		wn.ui.form.handlers[doctype][fieldname] = [];
	}
	wn.ui.form.handlers[doctype][fieldname].push(handler)
}

wn.ui.form.ScriptManager = Class.extend({
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
		
		$.each(handlers, function(i, fn) {
			fn();
		})
	},
	get_handlers: function(event_name, doctype, name, callback) {
		var handlers = [];
		var me = this;
		if(wn.ui.form.handlers[doctype] && wn.ui.form.handlers[doctype][event_name]) {
			$.each(wn.ui.form.handlers[doctype][event_name], function(i, fn) {
				handlers.push(function() { fn(me.frm, doctype, name) });
			});
		} 
		if(this.frm.cscript[event_name]) {
			handlers.push(function() { me.frm.cscript[event_name](me.frm.doc, doctype, name); });
		}
		if(this.frm.cscript["custom_" + event_name]) {
			handlers.push(function() { me.frm.cscript["custom_" + event_name](me.frm.doc, doctype, name); });
		}
		return handlers;
	},
	setup: function() {
		var doctype = this.frm.meta;

		// js
		var cs = doctype.__js;
		if(cs) {
			var tmp = eval(cs);
		}

		// css
		doctype.__css && wn.dom.set_style(doctype.__css);
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
	validate_link_and_fetch: function(df, docname, value, callback) {
		var me = this;
		
		if(value) {
			var fetch = '';
		
			if(this.frm && this.frm.fetch_dict[df.fieldname])
				fetch = this.frm.fetch_dict[df.fieldname].columns.join(', ');
			
			return wn.call({
				method:'webnotes.widgets.form.utils.validate_link',
				type: "GET",
				args: {
					'value': value, 
					'options': df.options, 
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
			wn.model.set_value(df.parent, docname, fl[i], fetch_values[i], df.fieldtype);
		}
	},
	copy_from_first_row: function(parentfield, current_row, fieldnames) {
		var doclist = wn.model.get_doclist(this.frm.doc.doctype, this.frm.doc.name, {parentfield: parentfield});
		if(doclist.length===1 || doclist[0]===current_row) return;
		
		$.each(fieldnames, function(i, fieldname) {
			current_row[fieldname] = doclist[0][fieldname];
		});
	}
});