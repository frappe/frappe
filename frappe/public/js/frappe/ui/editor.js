// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

/* Inspired from: http://github.com/mindmup/bootstrap-wysiwyg */

// todo
// make it inline friendly

bsEditor = Class.extend({
	init: function(options) {
		this.options = $.extend({}, this.default_options, options || {});
		this.edit_mode = true;
		if(this.options.editor) {
			this.setup_editor(this.options.editor);
			this.setup_fixed_toolbar();
		} else if(this.options.parent) {
			this.wrapper = $("<div></div>").appendTo(this.options.parent);
			this.setup_editor($("<div class='frappe-list'></div>").appendTo(this.wrapper));
			this.setup_inline_toolbar();
			this.editor.css(this.options.inline_editor_style);
			this.set_editing();
		}
	},
	setup_editor: function(editor) {
		var me = this;
		this.editor = $(editor);
		this.editor.on("click", function() {
			if(me.edit_mode && !me.editing) {
				me.set_editing();
			}
		}).on("mouseup keyup mouseout", function() {
			var html = me.clean_html();
			if(me.editing && html != me.last_html) {
				me.toolbar.save_selection();
				me.toolbar.update();
				me.options.change && me.options.change(html);
				me.last_html = html;
			}
		}).data("object", this);

		this.bind_hotkeys();
		this.init_file_drops();
	},

	set_editing: function() {
		this.editor.attr('contenteditable', true);
		this.toolbar.show();
		if(this.options.editor)
			this.toolbar.editor = this.editor.focus();
		this.editing = true;
	},

	setup_fixed_toolbar: function() {
		if(!window.bs_editor_toolbar) {
			window.bs_editor_toolbar = new bsEditorToolbar(this.options)
		}
		this.toolbar = window.bs_editor_toolbar;
	},
	setup_inline_toolbar: function() {
		this.toolbar = new bsEditorToolbar(this.options, this.wrapper, this.editor);
	},
	onhide: function() {
		this.editing = false;
		this.options.onsave && this.options.onsave(this);
		this.options.change && this.options.change(this.get_value());
	},
	toggle_edit_mode: function(bool) {
		// switch to enter editing mode
		this.edit_mode = bool;
		if(this.edit_mode) {
			this.editor.trigger("click");
		}
	},
	default_options: {
		hotKeys: {
			'ctrl+b meta+b': 'bold',
			'ctrl+i meta+i': 'italic',
			'ctrl+u meta+u': 'underline',
			'ctrl+z meta+z': 'undo',
			'ctrl+y meta+y meta+shift+z': 'redo',
			'ctrl+l meta+l': 'justifyleft',
			'ctrl+e meta+e': 'justifycenter',
			'ctrl+j meta+j': 'justifyfull',
			'shift+tab': 'outdent',
			'tab': 'indent'
	    },
		inline_editor_style: {
			"height": "400px",
			"background-color": "white",
			"border-collapse": "separate",
			"border": "1px solid rgb(204, 204, 204)",
			"padding": "4px",
			"box-sizing": "content-box",
			"-webkit-box-shadow": "rgba(0, 0, 0, 0.0745098) 0px 1px 1px 0px inset",
			"box-shadow": "rgba(0, 0, 0, 0.0745098) 0px 1px 1px 0px inset",
			"border-radius": "3px",
			"overflow": "scroll",
			"outline": "none"
		},
		toolbar_selector: '[data-role=editor-toolbar]',
		command_role: 'edit',
		selection_marker: 'edit-focus-marker',
		selection_color: 'darkgrey',
		remove_typography: false,
		max_file_size: 1,
	},

	bind_hotkeys: function () {
		var me = this;
		$.each(this.options.hotKeys, function (hotkey, command) {
			me.editor.keydown(hotkey, function (e) {
				if (me.editor.attr('contenteditable') && me.editor.is(':visible')) {
					e.preventDefault();
					e.stopPropagation();
					me.toolbar.execCommand(command);
				}
			}).keyup(hotkey, function (e) {
				if (me.editor.attr('contenteditable') && me.editor.is(':visible')) {
					e.preventDefault();
					e.stopPropagation();
				}
			});
		});
	},

	clean_html: function() {

		var html = this.editor.html() || "";

		if(!$.trim(this.editor.text()) && !(this.editor.find("img"))) html = "";

		// remove custom typography (use CSS!)
		if(this.options.remove_typography) {
			var tmp = $("<div></div>").html(html);
			// remove style attributes
			tmp.find("*")
				.removeAttr("style")
				.removeAttr("font");
			html = tmp.html();
		}

		return html;
	},

	init_file_drops: function () {
		var me = this;
		this.editor.on('dragenter dragover', false)
			.on('drop', function (e) {
				var dataTransfer = e.originalEvent.dataTransfer;
				e.stopPropagation();
				e.preventDefault();
				if (dataTransfer && dataTransfer.files && dataTransfer.files.length > 0) {
					me.insert_files(dataTransfer.files);
				}
			});
	},

	insert_files: function (files) {
		var me = this;
		this.editor.focus();
		$.each(files, function (i, file) {
			if (/^image\//.test(file.type)) {
				me.get_image(file, function(image_url) {
					me.toolbar.execCommand('insertImage', image_url);
				})
			}
		});
	},

	get_image: function (fileobj, callback) {
		var freader = new FileReader(),
			me = this;

		freader.onload = function() {
			var dataurl = freader.result;
			// add filename to dataurl
			var parts = dataurl.split(",");
			parts[0] += ";filename=" + fileobj.name;
			dataurl = parts[0] + ',' + parts[1];
			if(me.options.max_file_size) {
				if(dataurl.length > (me.options.max_file_size * 1024 * 1024 * 1.4)) {
					bs_get_modal("Upload Error", "Max file size (" + me.options.max_file_size + "M) exceeded.").modal("show");
					throw "file size exceeded";
				}
			}
			callback(dataurl);
		}
		freader.readAsDataURL(fileobj);
	},

	get_value: function() {
		return this.clean_html()
	},

	set_input: function(value) {
		if(this.options.field && this.options.field.inside_change_event)
			return;
		value = value==null ? "" : value;
		this.last_html = value;
		this.editor.html(value);
	}

})

bsEditorToolbar = Class.extend({
	init: function(options, parent, editor) {
		this.options = options;
		this.editor = editor;
		this.inline = !!parent;
		this.options.toolbar_style = $.extend((this.inline ? this.inline_style : this.fixed_style),
			this.options.toolbar_style || {});
		this.make(parent);
		this.toolbar.css(this.options.toolbar_style);
		this.setup_image_button();
		this.bind_events();
		//this.bind_touch();
	},
	fixed_style: {
		position: "fixed",
		top: "0px",
		padding: "5px",
		width: "100%",
		height: "45px",
		"background-color": "black",
		display: "none"
	},
	inline_style: {
		padding: "5px",
	},
	make: function(parent) {
		if(!parent)
			parent = $("body");
		if(!parent.find(".frappe-list-toolbar").length) {
			this.toolbar = $('<div class="frappe-list-toolbar frappe-ignore-click">\
			<div class="btn-toolbar" data-role="editor-toolbar" style="margin-bottom: 7px;">\
				<div class="btn-group form-group">\
					<a class="btn btn-default btn-small dropdown-toggle" data-toggle="dropdown" \
						title="' + __("Font Size") + '"><i class="icon-text-height"></i> '
						+ '<small style="margin-left: 5px;" class="hidden-xs">' + __("Font Size") + '</small>'
						+ ' <b class="caret"></b></a>\
					<ul class="dropdown-menu" role="menu">\
						<li><a href="#" data-edit="formatBlock &lt;p&gt;"><p>' + __("Paragraph") + '</p></a></li>\
						<li><a href="#" data-edit="formatBlock &lt;h1&gt;"><h1>' + __("Heading") + ' 1</h1></a></li>\
						<li><a href="#" data-edit="formatBlock &lt;h2&gt;"><h2>' + __("Heading") + ' 2</h2></a></li>\
						<li><a href="#" data-edit="formatBlock &lt;h3&gt;"><h3>' + __("Heading") + ' 3</h3></a></li>\
						<li><a href="#" data-edit="formatBlock &lt;h4&gt;"><h4>' + __("Heading") + ' 4</h4></a></li>\
						<li><a href="#" data-edit="formatBlock &lt;h5&gt;"><h5>' + __("Heading") + ' 5</h5></a></li>\
					</ul>\
				</div>\
				<div class="btn-group form-group">\
					<a class="btn btn-default btn-small" data-edit="bold" title="' + __("Bold (Ctrl/Cmd+B)") + '">\
						B</a>\
					<a class="btn btn-default btn-small" data-edit="insertunorderedlist" title="' + __("Bullet list") + '">\
						<i class="octicon octicon-list-unordered"></i></a>\
					<a class="btn btn-default btn-small" data-edit="insertorderedlist" title="' + __("Number list") + '">\
						<i class="octicon octicon-list-ordered"></i></a>\
				</div>\
				<div class="btn-group form-group">\
					<a class="btn btn-default btn-small btn-insert-img" title="' + __("Insert picture (or just drag & drop)") + '">\
						<i class="octicon octicon-file-media"></i></a>\
					<a class="btn btn-default btn-small btn-add-link" title="' + __("Insert Link") + '">\
						<i class="icon-link"></i></a>\
					<a class="btn btn-default btn-small" title="' + __("Remove Link") +'" data-edit="unlink">\
						<i class="icon-unlink"></i></a>\
				</div>\
				<div class="btn-group hidden-xs form-group">\
					<a class="btn btn-default btn-small" data-edit="justifyleft" title="' + __("Align Left (Ctrl/Cmd+L)") + '">\
						<i class="icon-align-left"></i></a>\
					<a class="btn btn-default btn-small" data-edit="justifycenter" title="' + __("Center (Ctrl/Cmd+E)") + '">\
						<i class="icon-align-center"></i></a>\
					<a class="btn btn-default btn-small" data-edit="outdent" title="' + __("Reduce indent (Shift+Tab)") + '">\
						<i class="octicon octicon-move-left"></i></a>\
					<a class="btn btn-default btn-small" data-edit="indent" title="' + __("Indent (Tab)") + '">\
						<i class="octicon octicon-move-right"></i></a>\
					<a class="btn btn-default btn-small" data-edit="insertHorizontalRule" \
						title="' + __("Horizontal Line Break") + '"><i class="octicon octicon-horizontal-rule"></i></a>\
				</div>\
				<div class="btn-group form-group">\
					<a class="btn btn-default btn-small btn-html hidden-xs" title="' + __("HTML") + '">\
						<i class="octicon octicon-code"></i></a>\
					<a class="btn btn-default btn-small btn-success" data-action="Save" title="' + __("Save") + '">\
						<i class="octicon octicon-check"></i></a>\
				</div>\
				<input type="file" data-edit="insertImage" />\
			</div>').prependTo(parent);

			if(this.inline) {
				this.toolbar.find("[data-action]").remove();
			} else {
				this.toolbar.find(".btn-toolbar").addClass("container");
			}
		}
	},

	setup_image_button: function() {
		// magic-overlay
		var me = this;
		this.file_input = this.toolbar.find('input[type="file"]')
			.css({
				'opacity':0,
				'position':'absolute',
				'left':0,
				'width':0,
				'height':0
			});
		this.toolbar.find(".btn-insert-img").on("click", function() {
			me.file_input.trigger("click");
		})
	},

	show: function() {
		var me = this;
		this.toolbar.toggle(true);
		if(!this.inline) {
			$("body").animate({"padding-top": this.toolbar.outerHeight() }, {
				complete: function() { 	me.toolbar.css("z-index", 1001); }
			});
		}
	},

	hide: function() {
		if(!this.editor)
			return;
		var me = this;
		this.toolbar.css("z-index", 0);
		if(!this.inline) {
			$("body").animate({"padding-top": 0 }, {complete: function() {
				me.toolbar.toggle(false);
			}});
		}

		this.editor && this.editor.attr('contenteditable', false).data("object").onhide();
		this.editor = null;
	},

	bind_events: function () {
		var me = this;

		// standard button events
		this.toolbar.find('a[data-' + me.options.command_role + ']').click(function () {
			me.restore_selection();
			me.editor.focus();
			me.execCommand($(this).data(me.options.command_role));
			me.save_selection();
			// close dropdown
			if(me.toolbar.find("ul.dropdown-menu:visible").length)
				me.toolbar.find('[data-toggle="dropdown"]').dropdown("toggle");
			return false;
		});
		this.toolbar.find('[data-toggle=dropdown]').click(function() { me.restore_selection() });

		// link
		this.toolbar.find(".btn-add-link").on("click", function() {
			if(!me.toolbar.bs_link_editor) {
				if(me.inline) {
					me.toolbar.bs_link_editor = new bsLinkEditor(me);
				} else {
					if(!window.bs_link_editor) {
						window.bs_link_editor = new bsLinkEditor(me);
					}
					me.toolbar.bs_link_editor = window.bs_link_editor;
				}
			}
			me.toolbar.bs_link_editor.show();
		});

		// file event
		this.toolbar.find('input[type=file][data-' + me.options.command_role + ']').change(function () {
			me.restore_selection();
			if (this.type === 'file' && this.files && this.files.length > 0) {
				me.editor.data("object").insert_files(this.files);
			}
			me.save_selection();
			this.value = '';

			return false;
		});

		// save
		this.toolbar.find("[data-action='Save']").on("click", function() { me.hide(); });

		// edit html
		this.toolbar.find(".btn-html").on("click", function() {
			new bsHTMLEditor().show(me.editor);
		});
	},

	update: function () {
		var me = this;
		if (this.toolbar) {
			$(this.toolbar).find('.btn[data-' + this.options.command_role + ']').each(function () {
				var command = $(this).data(me.options.command_role);

				// try catch for buggy firefox!
				try {
					var query_command_state = document.queryCommandState(command);
				} catch(e) {
					var query_command_state = false;
				}

				if (query_command_state) {
					$(this).addClass(me.options.active_toolbar_class);
				} else {
					$(this).removeClass(me.options.active_toolbar_class);
				}
			});
		}
	},

	execCommand: function (commandWithArgs, valueArg) {
		var commandArr = commandWithArgs.split(' '),
			command = commandArr.shift(),
			args = commandArr.join(' ') + (valueArg || '');
		document.execCommand(command, 0, args);
		this.update();
	},

	get_current_range: function () {
		var sel = window.getSelection();
		if (sel.getRangeAt && sel.rangeCount) {
			return sel.getRangeAt(0);
		}
	},

	save_selection: function () {
		this.selected_range = this.get_current_range();
	},

	restore_selection: function () {
		var selection = window.getSelection();
		if (this.selected_range) {
			selection.removeAllRanges();
			selection.addRange(this.selected_range);
		}
	},

	mark_selection: function (input, color) {
		this.restore_selection();
		document.execCommand('hiliteColor', 0, color || 'transparent');
		this.save_selection();
		input.data(this.options.selection_marker, color);
	},

	// bind_touch: function() {
	// 	var me = this;
	// 	$(window).bind('touchend', function (e) {
	// 		var isInside = (me.editor.is(e.target) || me.editor.has(e.target).length > 0),
	// 			current_range = me.get_current_range(),
	// 			clear = current_range && (current_range.startContainer === current_range.endContainer && current_range.startOffset === current_range.endOffset);
	// 		if (!clear || isInside) {
	// 			me.save_selection();
	// 			me.update();
	// 		}
	// 	});
	// }
});

bsHTMLEditor = Class.extend({
	init: function() {
		var me = this;
		this.modal = bs_get_modal("<i class='icon-code'></i> Edit HTML", '<textarea class="form-control" \
			style="height: 400px; width: 100%; font-family: Monaco, \'Courier New\', monospace; font-size: 11px">\
			</textarea>');
			this.modal.addClass("frappe-ignore-click");
		this.modal.find(".btn-primary").removeClass("hide").html(__("Update")).on("click", function() {
			me._html = me.modal.find("textarea").val();

			$.each(me.editor.dataurls, function(key, val) {
				me._html = replace_all(me._html, key, val);
			});

			var editor = me.editor.data("object");
			editor.set_input(me._html);
			editor.options.change && editor.options.change(editor.clean_html());
			me.modal.modal("hide");
		});
	},
	show: function(editor) {
		var me = this;
		this.editor = editor;
		this.modal.modal("show");
		var html = me.editor.html();
		// pack dataurls so that html display is faster
		this.editor.dataurls = {}
		html = html.replace(/<img\s*src=\s*["\'](data:[^,]*),([^"\']*)["\']/g, function(full, g1, g2) {
			var key = g2.slice(0,5) + "..." + g2.slice(-5);
			me.editor.dataurls[key] = g1 + "," + g2;
			return '<img src="'+ key+'"';
		});
		this.modal.find("textarea").val(html_beautify(html));
	}
});

bsLinkEditor = Class.extend({
	init: function(toolbar) {
		var me = this;
		this.toolbar = toolbar;
		this.modal = bs_get_modal("<i class='icon-globe'></i> Insert Link", '<div class="form-group">\
				<input type="text" class="form-control" placeholder="http://example.com" />\
			</div>\
			<div class="checkbox" style="position: static;">\
				<label>\
				    <input type="checkbox"> <span>' + __("Open Link in a new Window") + '</span>\
				</label>\
			</div>\
			<button class="btn btn-primary" style="margin-top: 7px;">' + __("Insert") + '</button>');

		this.modal.addClass("frappe-ignore-click");
		this.modal.find(".btn-primary").on("click", function() {
			me.toolbar.restore_selection();
			var url = me.modal.find("input[type=text]").val();
			var selection = me.toolbar.selected_range.toString();
			if(url) {
				if(me.modal.find("input[type=checkbox]:checked").length) {
					var html = "<a href='" + url + "' target='_blank'>" + selection + "</a>";
					document.execCommand("insertHTML", false, html);
				} else {
					document.execCommand("CreateLink", false, url);
				}
			}
			me.modal.modal("hide");
			return false;
		});
	},
	show: function() {
		this.modal.find("input[type=text]").val("");
		this.modal.modal("show");
	}
});

bs_get_modal = frappe.get_modal;
