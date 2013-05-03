wn.ui.form.ScriptManager = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.setup();
		
		var me = this;

		// watch model updates

		// on main doc
		wn.model.on(me.frm.doctype, "*", function(value, doctype, name, fieldname) {
			me.trigger(fieldname, doctype, name);
		})
		
		// on table fields
		$.each(wn.model.get("DocField", {fieldtype:"Table", parent: me.frm.doctype}), function(i, df) {
			wn.model.on(df.options, "*", function(value, doctype, name, fieldname) {
				me.trigger(fieldname, doctype, name);
			})
		})
		
	},
	trigger: function(event_name, doctype, name) {
		doctype = doctype || this.frm.doctype;
		name = name || this.frm.docname;
		try {
			if(this.frm.cscript[event_name])
				this.frm.cscript[event_name](this.frm.doc, doctype, name);
			
			if(this.frm.cscript["custom_" + event_name])
				this.frm.cscript["custom_" + event_name](this.frm.doc, doctype, name);
		} catch(e) {
			validated = false;

			// show error message
			this.log_error(event_name, e);
		}
	},
	setup: function() {
		var doctype = this.frm.meta;

		// js
		var cs = doctype.__js;
		if(cs) {
			try {
				var tmp = eval(cs);
			} catch(e) {
				this.log_error(caller || "setup_client_js", e);
			}
		}

		// css
		doctype.__css && wn.dom.set_style(doctype.__css);
	},
	log_error: function(e) {
		show_alert("Error in Client Script.");
		console.group && console.group();
		console.log("----- error in client script -----");
		console.log("method: " + caller);
		console.log(e);
		console.log("error message: " + e.message);
		console.trace && console.trace();
		console.log("----- end of error message -----");
		console.group && console.groupEnd();
	}
})