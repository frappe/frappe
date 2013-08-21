// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
// MIT License. See license.txt


// Options
// parent
// change (event)

// Properties
// set_input
// input

wn.provide("wn.editors");

wn.editors.BootstrapWYSIWYG = Class.extend({
	init: function(opts) {
		wn.require("lib/js/lib/bootstrap-wysiwyg.js");
		this.opts = opts;
		this.make_body();
		this.make_bindings();
	},
	make_body: function() {
		var me = this;
		this.myid = "editor-" + wn.dom.set_unique_id();
		$('<div class="for-rich-text">\
			<div class="btn-toolbar" data-role="editor-toolbar" style="margin-bottom: 7px;"\
				data-target="#'+ this.myid +'">\
				<div class="btn-group hidden-xs form-group">\
					<a class="btn btn-default btn-small dropdown-toggle" data-toggle="dropdown" title="Font"><i class="icon-font"></i><b class="caret"></b></a>\
					<ul class="dropdown-menu"></ul>\
				</div>\
				<div class="btn-group form-group">\
					<a class="btn btn-default btn-small dropdown-toggle" data-toggle="dropdown" title="Font Size"><i class="icon-text-height"></i> <b class="caret"></b></a>\
					<ul class="dropdown-menu">\
						<li><a data-edit="formatBlock &lt;p&gt;"><p>Paragraph</p></a></li>\
						<li><a data-edit="formatBlock &lt;h1&gt;"><h1>Heading 1</h1></a></li>\
						<li><a data-edit="formatBlock &lt;h2&gt;"><h2>Heading 2</h2></a></li>\
						<li><a data-edit="formatBlock &lt;h3&gt;"><h3>Heading 3</h3></a></li>\
						<li><a data-edit="formatBlock &lt;h4&gt;"><h4>Heading 4</h4></a></li>\
						<li><a data-edit="formatBlock &lt;h5&gt;"><h5>Heading 5</h5></a></li>\
					</ul>\
				</div>\
				<div class="btn-group form-group">\
					<a class="btn btn-default btn-small" data-edit="bold" title="Bold (Ctrl/Cmd+B)"><i class="icon-bold"></i></a>\
					<a class="btn btn-default btn-small" data-edit="insertunorderedlist" title="Bullet list"><i class="icon-list-ul"></i></a>\
					<a class="btn btn-default btn-small" data-edit="insertorderedlist" title="Number list"><i class="icon-list-ol"></i></a>\
					<a class="btn btn-default btn-small" data-edit="outdent" title="Reduce indent (Shift+Tab)"><i class="icon-indent-left"></i></a>\
					<a class="btn btn-default btn-small" data-edit="indent" title="Indent (Tab)"><i class="icon-indent-right"></i></a>\
				</div>\
				<div class="btn-group hidden-xs form-group">\
					<a class="btn btn-default btn-small" data-edit="justifyleft" title="Align Left (Ctrl/Cmd+L)"><i class="icon-align-left"></i></a>\
					<a class="btn btn-default btn-small" data-edit="justifycenter" title="Center (Ctrl/Cmd+E)"><i class="icon-align-center"></i></a>\
					<a class="btn btn-default btn-small btn-add-link" title="Insert Link">\
						<i class="icon-link"></i></a>\
					<a class="btn btn-default btn-small" title="Remove Link" data-edit="unlink">\
						<i class="icon-unlink"></i></a>\
					<a class="btn btn-default btn-small" title="Insert picture (or just drag & drop)" id="pictureBtn-'+this.myid+'"><i class="icon-picture"></i></a>\
					<input type="file" data-role="magic-overlay" data-target="#pictureBtn-'+this.myid+'" data-edit="insertImage" />\
					<a class="btn btn-default btn-small" data-edit="insertHorizontalRule" title="Horizontal Line Break">-</a>\
				</div>\
			</div>\
			<div id="'+this.myid+'" class="wysiwyg-editor">\
			</div>\
		</div>\
		<div class="for-html" style="display:none">\
			<textarea class="html-editor" style="width:95%; height: 440px;\
				font-family: Monaco, Menlo, Consolas, Courier, monospace;\
				font-size: 11px;"></textarea>\
		</div>\
		<div class="btn-toolbar pull-right" style="margin-top: 7px;">\
			<div class="btn-group">\
				<a class="btn btn-default btn-small btn-info btn-rich-text" title="Rich Text" disabled="disabled"><i class="icon-reorder"></i></a>\
				<a class="btn btn-default btn-small btn-html" title="HTML"><i class="icon-wrench"></i></a>\
			</div>\
		</div><div class="clearfix"></div>').appendTo(this.opts.parent);
		this.$parent = $(this.opts.parent);
		this.$editor = $("#" + this.myid);
		this.$parent.find(".btn-add-link").click(function() {
			me.show_link_dialog();
			return false;
		})
		this.$editor.on("keyup", function() { me.save_selection() });
		this.$editor.on("mouseup", function() { me.save_selection() });
		this.$textarea = this.$parent.find(".html-editor");
		this.input = this.$editor.get(0);
	},
	set_focus: function() {
		this.$editor.focus();
	},
	save_selection: function() {
		this.saved_selection = wn.dom.save_selection();
	},
	show_link_dialog: function() {
		var me = this;
		var d = new wn.ui.Dialog({
				title: "Add Link",
				fields: [
					{fieldtype: "Data", label:"Link", fieldname: "link", reqd: 1,
						description:"example: http://example.com"},
					{fieldtype: "Button", label:"Add", fieldname: "add"},
				]
			});
		d.show();
		d.fields_dict.link.set_input("http://");
		$(d.fields_dict.add.input).click(function() {
			var values = d.get_values();
			if(values) {
				d.hide();
				wn.dom.restore_selection(me.saved_selection);
				document.execCommand("CreateLink", false, values.link);
			}
		});
		d.onhide = function() {
			wn.dom.restore_selection(me.saved_selection);
		}
	},
	make_bindings: function() {
		var me = this;
		var fonts = ['Serif', 'Sans', 'Arial', 'Arial Black', 'Courier', 
		'Courier New', 'Comic Sans MS', 'Helvetica', 'Impact', 'Lucida Grande', 
		'Lucida Sans', 'Tahoma', 'Times', 'Times New Roman', 'Verdana'],
		fontTarget = this.$parent.find('[title=Font]').siblings('.dropdown-menu');
		
		$.each(fonts, function (idx, fontName) {
			fontTarget.append($('<li><a data-edit="fontName ' + 
				fontName +'" style="font-family:\''+ fontName +'\'">'+
				fontName + '</a></li>'));
		});
		
		// magic-overlay
		this.$parent.find('[data-role=magic-overlay]').each(function () { 
			var overlay = $(this), target = $(overlay.data('target'));
			overlay.css('opacity', 0).css('position', 'absolute')
				//.offset(target.offset())
				.css("left", 157) // use this because in dialogs, can't find the offset
				.width(38).height(33);
		});
		
		this.$editor
			.wysiwyg()
			.on("mouseup keyup mouseout", function() {
				var value = $(this).html();
				if(value==null) value="";
				me.opts.change(value);
			})
		this.$textarea
			.on("change", function() {
				var value = $(this).val();
				if(value==null) value="";
				me.opts.change(value);
			});
		
		this.current_editor = this.$editor;
		this.$parent.find(".btn-html").click(function() {
			if($(this).attr("disabled")=="disabled") return;
			wn.require("lib/js/lib/beautify-html.js");
			me.$textarea.val(html_beautify(me.$editor.cleanHtml()));
			me.$parent.find(".for-rich-text").toggle(false);
			me.$parent.find(".for-html").toggle(true);
			me.$parent.find(".btn-html").addClass("btn-info").attr("disabled", "disabled");
			me.$parent.find(".btn-rich-text").removeClass("btn-info").attr("disabled", false);
			me.current_editor = me.$textarea;
		});

		this.$parent.find(".btn-rich-text").click(function() {
			if($(this).attr("disabled")=="disabled") return;
			me.$editor.html(me.$textarea.val());
			me.$parent.find(".for-rich-text").toggle(true);
			me.$parent.find(".for-html").toggle(false);
			me.$parent.find(".btn-html").removeClass("btn-info").attr("disabled", false);
			me.$parent.find(".btn-rich-text").addClass("btn-info").attr("disabled", "disabled");
			me.current_editor = me.$editor;
		});

	},
	set_input: function(value) {
		if(this.opts.field.inside_change_event)
			return;
			
		if(this.value!=value) {
			this.value = value==null ? "" : value;
			this.$editor.html(this.value);
			this.$textarea.val(this.value);
		}
	},
	get_value: function() {
		if(this.current_editor==this.$editor)
			return this.$editor.cleanHtml();
		else
			return this.$textarea.val();
	}
})


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
	set_focus: function() {
		this.$editor.focus();
	},
})