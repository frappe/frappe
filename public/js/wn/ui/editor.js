// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
// MIT License. See license.txt 

/* Inspired from: http://github.com/mindmup/bootstrap-wysiwyg */

// todo 
// html editing
// image
// links
// onsave, oncancel

wn.provide("wn.ui");
wn.ui.Editor = Class.extend({
	init: function(editor, options) {
		var me = this;
		this.editor = $(editor);
		this.options = $.extend(options || {}, this.default_options);
		this.files = [];
		
		this.editor.on("click", function() {
			if(!this.editing) {
				me.make();
				me.editor.attr('contenteditable', true);
				me.original_html =  me.editor.html();
				wn._editor_toolbar.show();
				wn._current_editor = me.editor.focus();
				me.editing = true;
			}
		}).on("mouseup keyup mouseout", function() {
			if(me.editing) {
				wn._editor_toolbar.saveSelection();
				wn._editor_toolbar.update();
			}
		}).on("blur", function() {
			if(wn._editor_toolbar.clicked.parents(".wn-editor-toolbar").length)
				return;
			wn._editor_toolbar.toolbar.find("[data-action='Save']").trigger("click");
		}).data("object", this);

		this.bind_hotkeys();
		this.init_file_drops();
	},
	make: function() {
		if(!wn._editor_toolbar) {
			wn._editor_toolbar = new wn.ui.EditorToolbar(this.options)
		}
	},
	onhide: function(action) {
		this.editing = false;
		if(action==="Cancel") {
			this.editor.html(this.original_html);
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
		toolbarSelector: '[data-role=editor-toolbar]',
		commandRole: 'edit',
		activeToolbarClass: 'btn-info',
		selectionMarker: 'edit-focus-marker',
		selectionColor: 'darkgrey',
		remove_typography: true,
	},
	
	show: function() {
	},

	bind_hotkeys: function () {
		var me = this;
		$.each(this.options.hotKeys, function (hotkey, command) {
			me.editor.keydown(hotkey, function (e) {
				if (me.editor.attr('contenteditable') && me.editor.is(':visible')) {
					e.preventDefault();
					e.stopPropagation();
					wn._editor_toolbar.execCommand(command);
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
		html = html.replace(/(<br>|\s|<div><br><\/div>|&nbsp;)*$/, '');

		// remove custom typography (use CSS!)
		if(this.options.remove_typography) {
			html = html.replace(/(font-family|font-size|line-height):[^;]*;/g, '');
			html = html.replace(/<[^>]*(font=['"][^'"]*['"])>/g, function(a,b) { return a.replace(b, ''); });
			html = html.replace(/\s*style\s*=\s*["']\s*["']/g, '');
			return html;
		}
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
					wn._editor_toolbar.execCommand('insertimage', image_url);
				})
			}
		});
	},

	get_image: function (fileobj, callback) {
		var freader = new FileReader(),
			me = this;

		freader.onload = function() {
			var dataurl = freader.result;
			me.files.push(dataurl);
			callback(dataurl);
		}
		freader.readAsDataURL(fileobj);
	}
	
})

wn.ui.EditorToolbar = Class.extend({
	init: function(options) {
		this.options = options;
		this.options.toolbar_style = $.extend(this.options.toolbar_style || {}, this.style);
		this.make();
		this.toolbar = $(".wn-editor-toolbar").css(this.options.toolbar_style);
		this.overlay_image_button();
		this.bind_events();
		this.bind_touch();

		var me = this;
		$(document).mousedown(function(e) {
			me.clicked = $(e.target);
	    });
	},
	style: {
		position: "fixed",
		top: "0px",
		padding: "5px",
		width: "100%",
		height: "45px",
		"background-color": "#ddd",
		"z-index": "1001" // more than navbar
	},
	make: function() {
		if(!$(".wn-editor-toolbar").length) {
			$('<div class="wn-editor-toolbar for-rich-text text-center">\
			<div class="btn-toolbar" data-role="editor-toolbar" style="margin-bottom: 7px;">\
				<div class="btn-group form-group">\
					<a class="btn btn-default btn-small dropdown-toggle" data-toggle="dropdown" \
						title="Font Size"><i class="icon-text-height"></i> <b class="caret"></b></a>\
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
					<a class="btn btn-default btn-small" data-edit="bold" title="Bold (Ctrl/Cmd+B)">\
						<i class="icon-bold"></i></a>\
					<a class="btn btn-default btn-small" data-edit="insertunorderedlist" title="Bullet list">\
						<i class="icon-list-ul"></i></a>\
					<a class="btn btn-default btn-small" data-edit="insertorderedlist" title="Number list">\
						<i class="icon-list-ol"></i></a>\
					<a class="btn btn-default btn-small" data-edit="outdent" title="Reduce indent (Shift+Tab)">\
						<i class="icon-indent-left"></i></a>\
					<a class="btn btn-default btn-small" data-edit="indent" title="Indent (Tab)">\
						<i class="icon-indent-right"></i></a>\
				</div>\
				<div class="btn-group hidden-xs form-group">\
					<a class="btn btn-default btn-small" data-edit="justifyleft" title="Align Left (Ctrl/Cmd+L)">\
						<i class="icon-align-left"></i></a>\
					<a class="btn btn-default btn-small" data-edit="justifycenter" title="Center (Ctrl/Cmd+E)">\
						<i class="icon-align-center"></i></a>\
					<a class="btn btn-default btn-small btn-add-link" title="Insert Link">\
						<i class="icon-link"></i></a>\
					<a class="btn btn-default btn-small" title="Remove Link" data-edit="unlink">\
						<i class="icon-unlink"></i></a>\
					<a class="btn btn-default btn-small" title="Insert picture (or just drag & drop)">\
						<i class="icon-picture"></i></a>\
					<input type="file" data-role="magic-overlay" data-edit="insertImage" />\
					<a class="btn btn-default btn-small" data-edit="insertHorizontalRule" \
						title="Horizontal Line Break">-</a>\
				</div>\
				<div class="btn-group hidden-xs form-group">\
					<a class="btn btn-default btn-small btn-info btn-rich-text" title="Rich Text" disabled="disabled">\
						<i class="icon-reorder"></i></a>\
					<a class="btn btn-default btn-small btn-html" title="HTML">\
						<i class="icon-wrench"></i></a>\
				</div>\
				<div class="btn-group form-group">\
					<a class="btn btn-default btn-small btn-primary" data-action="Save" title="Save">\
						<i class="icon-save"></i></a>\
					<a class="btn btn-default btn-small btn-html" data-action="Cancel" title="Cancel">\
						<i class="icon-remove"></i></a>\
				</div>\
			</div>').prependTo("body");
		}
	},
	
	overlay_image_button: function() {
		// magic-overlay
		this.toolbar.find('[data-role=magic-overlay]').each(function () { 
			var overlay = $(this), target=overlay.prev();
			overlay.css('opacity', 0).css('position', 'absolute')
				.css("left", 155)
				.width(38).height(33);
		});
	},
	
	show: function() {
		$("body").animate({"padding-top": this.toolbar.outerHeight() });
		this.toolbar.toggle(true);
	},

	hide: function(action) {
		$("body").animate({"padding-top": 0 });
		this.toolbar.toggle(false);
		wn._current_editor.attr('contenteditable', false).data("object").onhide(action);
		wn._current_editor = null;
	},
	
	bind_events: function () {
		var me = this;
				
		// standard button events
		this.toolbar.find('a[data-' + me.options.commandRole + ']').click(function () {
			me.restoreSelection();
			wn._current_editor.focus();
			me.execCommand($(this).data(me.options.commandRole));
			me.saveSelection();
			return false;
		});
		this.toolbar.find('[data-toggle=dropdown]').click(function() { me.restoreSelection() });

		// link
		this.toolbar.find('input[type=text][data-' + this.options.commandRole + ']')
			.on('webkitspeechchange change', function () {
			var newValue = this.value; /* ugly but prevents fake double-calls due to selection restoration */
			this.value = '';
			me.restoreSelection();
			if (newValue) {
				wn._current_editor.focus();
				me.execCommand($(this).data(me.options.commandRole), newValue);
			}
			me.saveSelection();
			return false;
		}).on('focus', function () {
			var input = $(this);
			if (!input.data(me.options.selectionMarker)) {
				me.markSelection(input, me.options.selectionColor);
				input.focus();
			}
		}).on('blur', function () {
			var input = $(this);
			if (input.data(me.options.selectionMarker)) {
				me.markSelection(input, false);
			}
		});
		
		// file event
		this.toolbar.find('input[type=file][data-' + me.options.commandRole + ']').change(function () {
			me.restoreSelection();
			if (this.type === 'file' && this.files && this.files.length > 0) {
				wn._current_editor.data("object").insert_files(this.files);
			}
			me.saveSelection();
			this.value = '';
			return false;
		});
		
		// cancel
		this.toolbar.find("[data-action='Save']").on("click", function() {
			me.hide("Save");
		})

		this.toolbar.find("[data-action='Cancel']").on("click", function() {
			me.hide("Cancel");
		})
	},

	update: function () {
		var me = this;
		if (this.options.activeToolbarClass) {
			$(this.options.toolbarSelector).find('.btn[data-' + this.options.commandRole + ']').each(function () {
				var command = $(this).data(me.options.commandRole);
				if (document.queryCommandState(command)) {
					$(this).addClass(me.options.activeToolbarClass);
				} else {
					$(this).removeClass(me.options.activeToolbarClass);
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
	
	getCurrentRange: function () {
		var sel = window.getSelection();
		if (sel.getRangeAt && sel.rangeCount) {
			return sel.getRangeAt(0);
		}
	},
	
	saveSelection: function () {
		this.selectedRange = this.getCurrentRange();
	},
	
	restoreSelection: function () {
		var selection = window.getSelection();
		if (this.selectedRange) {
			selection.removeAllRanges();
			selection.addRange(this.selectedRange);
		}
	},
	
	markSelection: function (input, color) {
		this.restoreSelection();
		document.execCommand('hiliteColor', 0, color || 'transparent');
		this.saveSelection();
		input.data(this.options.selectionMarker, color);
	},
	
	bind_touch: function() {
		var me = this;
		$(window).bind('touchend', function (e) {
			var isInside = (wn._current_editor.is(e.target) || wn._current_editor.has(e.target).length > 0),
				currentRange = me.getCurrentRange(),
				clear = currentRange && (currentRange.startContainer === currentRange.endContainer && currentRange.startOffset === currentRange.endOffset);
			if (!clear || isInside) {
				me.saveSelection();
				me.update();
			}
		});
	}	
})