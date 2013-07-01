wn.ui.form.ScriptManager = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.setup();		
	},
	trigger: function(event_name, doctype, name) {
		doctype = doctype || this.frm.doctype;
		name = name || this.frm.docname;
		if(this.frm.cscript[event_name])
			this.frm.cscript[event_name](this.frm.doc, doctype, name);
		
		if(this.frm.cscript["custom_" + event_name])
			this.frm.cscript["custom_" + event_name](this.frm.doc, doctype, name);
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
	}
})