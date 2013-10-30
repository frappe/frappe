// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
// MIT License. See license.txt


// Options
// parent
// change (event)

// Properties
// set_input
// input

wn.provide("wn.editors");

wn.editors.ACE = Class.extend({
	init: function(opts) {
		this.opts = opts;

		// setup ace
		wn.require('lib/js/lib/ace/ace.js');
		this.make();
		this.bind_form_load();
	},
	make: function() {
		$(this.opts.parent).css('border','1px solid #aaa');
		this.pre = $("<pre style='position: relative; height: 400px; \
			width: 100%; padding: 0px; border-radius: 0px;\
			margin: 0px; background-color: #fff;'>").appendTo(this.opts.parent).get(0);

		this.input = {};
		this.myid = wn.dom.set_unique_id(this.pre);
		this.editor = ace.edit(this.myid);

		if(this.opts.field.df.options=='Markdown' || this.opts.field.df.options=='HTML') {
			wn.require('lib/js/lib/ace/mode-html.js');	
			var HTMLMode = require("ace/mode/html").Mode;
		    this.editor.getSession().setMode(new HTMLMode());
		}

		else if(this.opts.field.df.options=='Javascript') {
			wn.require('lib/js/lib/ace/mode-javascript.js');	
			var JavascriptMode = require("ace/mode/javascript").Mode;
		    this.editor.getSession().setMode(new JavascriptMode());
		}

		else if(this.opts.field.df.options=='Python') {
			wn.require('lib/js/lib/ace/mode-python.js');	
			var PythonMode = require("ace/mode/python").Mode;
		    this.editor.getSession().setMode(new PythonMode());
		}
	},
	set_input: function(value) {
		// during field refresh in run trigger, set_input is called
		// if called during on_change, setting doesn't make sense
		// and causes cursor to shift back to first position
		if(this.opts.field.inside_change_event) return;
		
		this.setting_value = true;
		this.editor.getSession().setValue(value==null ? "" : value);
		this.setting_value = false;
	},
	get_value: function() {
		return this.editor.getSession().getValue();
	},
	set_focus: function() {
		this.editor.focus();
	},
	bind_form_load: function() {
		var me = this;
		if(cur_frm) {
			$(cur_frm.wrapper).bind('render_complete', function() {
				me.editor.resize();
				me.editor.getSession().on('change', function() {
					if(me.setting_value) return;
					me.opts.change(me.get_value())
				})
			});
		}
	},
})