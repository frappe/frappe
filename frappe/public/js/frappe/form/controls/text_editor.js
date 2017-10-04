frappe.ui.form.ControlTextEditor = frappe.ui.form.ControlCode.extend({
	make_input: function() {
		this.has_input = true;
		this.make_editor();
		this.hide_elements_on_mobile();
		this.setup_drag_drop();
		this.setup_image_dialog();
		this.setting_count = 0;

		$(document).on('form-refresh', () => {
			// reset last keystroke when a new form is loaded
			this.last_keystroke_on = null;
		})
	},
	render_camera_button: (context) => {
		var ui     = $.summernote.ui;
		var button = ui.button({
			contents: '<i class="fa fa-camera"/>',
			tooltip: 'Camera',
			click: () => {
				const capture = new frappe.ui.Capture();
				capture.open();

				capture.click((data) => {
					context.invoke('editor.insertImage', data);
				});
			}
		});

		return button.render();
	},
	make_editor: function() {
		var me = this;
		this.editor = $("<div>").appendTo(this.input_area);

		// Note: while updating summernote, please make sure all 'p' blocks
		// in the summernote source code are replaced by 'div' blocks.
		// by default summernote, adds <p> blocks for new paragraphs, which adds
		// unexpected whitespaces, esp for email replies.

		this.editor.summernote({
			minHeight: 400,
			toolbar: [
				['magic', ['style']],
				['style', ['bold', 'italic', 'underline', 'clear']],
				['fontsize', ['fontsize']],
				['color', ['color']],
				['para', ['ul', 'ol', 'paragraph', 'hr']],
				//['height', ['height']],
				['media', ['link', 'picture', 'camera', 'video', 'table']],
				['misc', ['fullscreen', 'codeview']]
			],
			buttons: {
				camera: this.render_camera_button,
			},
			keyMap: {
				pc: {
					'CTRL+ENTER': ''
				},
				mac: {
					'CMD+ENTER': ''
				}
			},
			prettifyHtml: true,
			dialogsInBody: true,
			callbacks: {
				onInit: function() {
					// firefox hack that puts the caret in the wrong position
					// when div is empty. To fix, seed with a <br>.
					// See https://bugzilla.mozilla.org/show_bug.cgi?id=550434
					// this function is executed only once
					$(".note-editable[contenteditable='true']").one('focus', function() {
						var $this = $(this);
						if(!$this.html())
							$this.html($this.html() + '<br>');
					});
				},
				onChange: function(value) {
					me.parse_validate_and_set_in_model(value);
				},
				onKeydown: function(e) {
					me.last_keystroke_on = new Date();
					var key = frappe.ui.keys.get_key(e);
					// prevent 'New DocType (Ctrl + B)' shortcut in editor
					if(['ctrl+b', 'meta+b'].indexOf(key) !== -1) {
						e.stopPropagation();
					}
					if(key.indexOf('escape') !== -1) {
						if(me.note_editor.hasClass('fullscreen')) {
							// exit fullscreen on escape key
							me.note_editor
								.find('.note-btn.btn-fullscreen')
								.trigger('click');
						}
					}
				},
			},
			icons: {
				'align': 'fa fa-align',
				'alignCenter': 'fa fa-align-center',
				'alignJustify': 'fa fa-align-justify',
				'alignLeft': 'fa fa-align-left',
				'alignRight': 'fa fa-align-right',
				'indent': 'fa fa-indent',
				'outdent': 'fa fa-outdent',
				'arrowsAlt': 'fa fa-arrows-alt',
				'bold': 'fa fa-bold',
				'camera': 'fa fa-camera',
				'caret': 'caret',
				'circle': 'fa fa-circle',
				'close': 'fa fa-close',
				'code': 'fa fa-code',
				'eraser': 'fa fa-eraser',
				'font': 'fa fa-font',
				'frame': 'fa fa-frame',
				'italic': 'fa fa-italic',
				'link': 'fa fa-link',
				'unlink': 'fa fa-chain-broken',
				'magic': 'fa fa-magic',
				'menuCheck': 'fa fa-check',
				'minus': 'fa fa-minus',
				'orderedlist': 'fa fa-list-ol',
				'pencil': 'fa fa-pencil',
				'picture': 'fa fa-image',
				'question': 'fa fa-question',
				'redo': 'fa fa-redo',
				'square': 'fa fa-square',
				'strikethrough': 'fa fa-strikethrough',
				'subscript': 'fa fa-subscript',
				'superscript': 'fa fa-superscript',
				'table': 'fa fa-table',
				'textHeight': 'fa fa-text-height',
				'trash': 'fa fa-trash',
				'underline': 'fa fa-underline',
				'undo': 'fa fa-undo',
				'unorderedlist': 'fa fa-list-ul',
				'video': 'fa fa-video-camera'
			}
		});
		this.note_editor = $(this.input_area).find('.note-editor');
		// to fix <p> on enter
		//this.set_formatted_input('<div><br></div>');
	},
	setup_drag_drop: function() {
		var me = this;
		this.note_editor.on('dragenter dragover', false)
			.on('drop', function(e) {
				var dataTransfer = e.originalEvent.dataTransfer;

				if (dataTransfer && dataTransfer.files && dataTransfer.files.length) {
					me.note_editor.focus();

					var files = [].slice.call(dataTransfer.files);

					files.forEach(file => {
						me.get_image(file, (url) => {
							me.editor.summernote('insertImage', url, file.name);
						});
					});
				}
				e.preventDefault();
				e.stopPropagation();
			});
	},
	get_image: function (fileobj, callback) {
		var reader = new FileReader();

		reader.onload = function() {
			var dataurl = reader.result;
			// add filename to dataurl
			var parts = dataurl.split(",");
			parts[0] += ";filename=" + fileobj.name;
			dataurl = parts[0] + ',' + parts[1];
			callback(dataurl);
		};
		reader.readAsDataURL(fileobj);
	},
	hide_elements_on_mobile: function() {
		this.note_editor.find('.note-btn-underline,\
			.note-btn-italic, .note-fontsize,\
			.note-color, .note-height, .btn-codeview')
			.addClass('hidden-xs');
		if($('.toggle-sidebar').is(':visible')) {
			// disable tooltips on mobile
			this.note_editor.find('.note-btn')
				.attr('data-original-title', '');
		}
	},
	get_input_value: function() {
		return this.editor? this.editor.summernote('code'): '';
	},
	parse: function(value) {
		if(value == null) value = "";
		return frappe.dom.remove_script_and_style(value);
	},
	set_formatted_input: function(value) {
		if(value !== this.get_input_value()) {
			this.set_in_editor(value);
		}
	},
	set_in_editor: function(value) {
		// set values in editor only if
		// 1. value not be set in the last 500ms
		// 2. user has not typed anything in the last 3seconds
		// ---
		// we will attempt to cleanup the user's DOM, hence if this happens
		// in the middle of the user is typing, it creates a lot of issues
		// also firefox tends to reset the cursor for some reason if the values
		// are reset

		if(this.setting_count > 2) {
			// we don't understand how the internal triggers work,
			// so if someone is setting the value third time in 500ms,
			// then quit
			return;
		}

		this.setting_count += 1;

		let time_since_last_keystroke = moment() - moment(this.last_keystroke_on);

		if(!this.last_keystroke_on || (time_since_last_keystroke > 3000)) {
			// if 3 seconds have passed since the last keystroke and
			// we have not set any value in the last 1 second, do this
			setTimeout(() => this.setting_count = 0, 500);
			this.editor.summernote('code', value || '');
			this.last_keystroke_on = null;
		} else {
			// user is probably still in the middle of typing
			// so lets not mess up the html by re-updating it
			// keep checking every second if our 3 second barrier
			// has been completed, so that we can refresh the html
			this._setting_value = setInterval(() => {
				if(time_since_last_keystroke > 3000) {
					// 3 seconds done! lets refresh
					// safe to update
					if(this.last_value !== this.get_input_value()) {
						// if not already in sync, reset
						this.editor.summernote('code', this.last_value || '');
					}
					clearInterval(this._setting_value);
					this._setting_value = null;
					this.setting_count = 0;

					// clear timestamp of last keystroke
					this.last_keystroke_on = null;
				}
			}, 1000);
		}
	},
	set_focus: function() {
		return this.editor.summernote('focus');
	},
	set_upload_options: function() {
		var me = this;
		this.upload_options = {
			parent: this.image_dialog.get_field("upload_area").$wrapper,
			args: {},
			max_width: this.df.max_width,
			max_height: this.df.max_height,
			options: "Image",
			btn: this.image_dialog.set_primary_action(__("Insert")),
			on_no_attach: function() {
				// if no attachmemts,
				// check if something is selected
				var selected = me.image_dialog.get_field("select").get_value();
				if(selected) {
					me.editor.summernote('insertImage', selected);
					me.image_dialog.hide();
				} else {
					frappe.msgprint(__("Please attach a file or set a URL"));
				}
			},
			callback: function(attachment) {
				me.editor.summernote('insertImage', attachment.file_url, attachment.file_name);
				me.image_dialog.hide();
			},
			onerror: function() {
				me.image_dialog.hide();
			}
		};

		if ("is_private" in this.df) {
			this.upload_options.is_private = this.df.is_private;
		}

		if(this.frm) {
			this.upload_options.args = {
				from_form: 1,
				doctype: this.frm.doctype,
				docname: this.frm.docname
			};
		} else {
			this.upload_options.on_attach = function(fileobj, dataurl) {
				me.editor.summernote('insertImage', dataurl);
				me.image_dialog.hide();
				frappe.hide_progress();
			};
		}
	},

	setup_image_dialog: function() {
		this.note_editor.find('[data-original-title="Image"]').on('click', () => {
			if(!this.image_dialog) {
				this.image_dialog = new frappe.ui.Dialog({
					title: __("Image"),
					fields: [
						{fieldtype:"HTML", fieldname:"upload_area"},
						{fieldtype:"HTML", fieldname:"or_attach", options: __("Or")},
						{fieldtype:"Select", fieldname:"select", label:__("Select from existing attachments") },
					]
				});
			}

			this.image_dialog.show();
			this.image_dialog.get_field("upload_area").$wrapper.empty();

			// select from existing attachments
			var attachments = this.frm && this.frm.attachments.get_attachments() || [];
			var select = this.image_dialog.get_field("select");
			if(attachments.length) {
				attachments = $.map(attachments, function(o) { return o.file_url; });
				select.df.options = [""].concat(attachments);
				select.toggle(true);
				this.image_dialog.get_field("or_attach").toggle(true);
				select.refresh();
			} else {
				this.image_dialog.get_field("or_attach").toggle(false);
				select.toggle(false);
			}
			select.$input.val("");

			this.set_upload_options();
			frappe.upload.make(this.upload_options);
		});
	}
});
