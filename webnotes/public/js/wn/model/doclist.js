// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

wn.provide("wn.model");
wn.model.DocList = Class.extend({
	init: function(doctype, name) {
		this.doctype = doctype; this.name = name;
		this.doclist = wn.model.get_doclist(this.doctype, this.name);
		this.doc = this.doclist[0];
	},
	
	save: function(action, callback, btn) {
		this.check_name();
		if(this.check_mandatory()) {
			var me = this;
			this._call({
				method: "webnotes.widgets.form.save.savedocs",
				args: { docs: wn.model.compress(this.doclist), action:action},
				callback: function(r) {
					$(document).trigger("save", me.doc);
					callback(r);
				},
				btn: btn
			});
		}
	},
	
	cancel: function(callback, btn) {
		var me = this;
		this._call({
			method: "webnotes.widgets.form.save.cancel",
			args: { doctype: this.doctype, name: this.name },
			callback: function(r) {
				$(document).trigger("save", wn.model.get_doc(me.doctype, me.name));
				callback(r);
			},
			btn: btn
		});
	},
	
	check_name: function() {
		var doc = this.doclist[0];
		var meta = locals.DocType[doc.doctype];
		if(doc.__islocal && (meta && meta.autoname 
				&& meta.autoname.toLowerCase()=='prompt')) {
			var newname = prompt('Enter the name of the new '+ doc.doctype, '');
			if(newname) { 
				doc.__newname = strip(newname);
			} else {
				msgprint("Name is required.");
				throw "name required";
			}
		}
	},
	
	check_mandatory: function() {
		var me = this;
		var has_errors = false;
		this.scroll_set = false;
		
		if(this.doc.docstatus==2) return true; // don't check for cancel
		
		$.each(this.doclist, function(i, doc) {
			
			var error_fields = [];
			
			$.each(wn.meta.docfield_list[doc.doctype] || [], function(i, docfield) {
				if(docfield.fieldname) {
					var df = wn.meta.get_docfield(doc.doctype, 
						docfield.fieldname, me.doclist[0].name);

					if(df.reqd && !wn.model.has_value(doc.doctype, doc.name, df.fieldname)) {
						has_errors = true;
						error_fields[error_fields.length] = df.label;
						
						// scroll to field
						if(!me.scroll_set) 
							me.scroll_to(doc.parentfield || df.fieldname);
					}
					
				}
			});
			if(error_fields.length)
				msgprint('<b>Mandatory fields required in '+ (doc.parenttype 
					? (wn.meta.docfield_map[doc.parenttype][doc.parentfield].label + ' (Table)') 
					: doc.doctype) + ':</b>\n' + error_fields.join('\n'));	
		});
		
		return !has_errors;
	},
	
	scroll_to: function(fieldname) {
		var f = cur_frm.fields_dict[fieldname];
		if(f) {
			$(document).scrollTop($(f.wrapper).offset().top - 100);
		}
		this.scroll_set = true;
	},

	_call: function(opts) {
		// opts = {
		// 	method: "some server method",
		// 	args: {args to be passed},
		// 	callback: callback,
		// 	btn: btn
		// }
		$(opts.btn).prop("disabled", true);
		return wn.call({
			freeze: true,
			method: opts.method,
			args: opts.args,
			callback: function(r) {
				$(opts.btn).prop("disabled", false);
				opts.callback && opts.callback(r);
			}
		})
	},
});