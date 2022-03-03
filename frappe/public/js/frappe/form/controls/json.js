frappe.ui.form.ControlJson = class ControlCode extends frappe.ui.form.ControlText {
	make_input() {
		if (this.editor) return;
		this.load_lib().then(() => this.make_ace_editor());
	}

	make_ace_editor() {
		if (this.editor) return;
		this.ace_editor_target = $('<div class="ace-editor-target"></div>')
			.appendTo(this.input_area);


		// styling
		this.ace_editor_target.addClass('border rounded');
		this.ace_editor_target.css('height', 300);

		if (this.df.max_height) {
			this.ace_editor_target.css('max-height', this.df.max_height);
		}

		// initialize
		const ace = window.ace;
		this.editor = ace.edit(this.ace_editor_target.get(0));

		if (this.df.max_lines || this.df.min_lines || this.df.max_height) {
			if (this.df.max_lines)
				this.editor.setOption("maxLines", this.df.max_lines);
			if (this.df.min_lines)
				this.editor.setOption("minLines", this.df.min_lines);
		} else {
			this.expanded = false;
			this.$expand_button = $(`<button class="btn btn-xs btn-default">${this.get_button_label()}</button>`).click(() => {
				this.expanded = !this.expanded;
				this.refresh_height();
				this.toggle_label();
			}).appendTo(this.$input_wrapper);
		}

		this.editor.setTheme('ace/theme/tomorrow');
		this.editor.setOption("showPrintMargin", false);
		this.editor.setOption("wrap", this.df.wrap);
		this.set_language();

		// events
		this.editor.session.on('change', frappe.utils.debounce(() => {
			const input_value = this.get_input_value();
			this.parse_validate_and_set_in_model(input_value);
		}, 300));

		// setup autocompletion when it is set the first time
		Object.defineProperty(this.df, 'autocompletions', {
			configurable: true,
			get() {
				return this._autocompletions || [];
			},
			set: (value) => {
				this.setup_autocompletion();
				this.df._autocompletions = value;
			}
		});
	}

	refresh_height() {
		this.ace_editor_target.css('height', this.expanded ? 600 : 300);
		this.editor.resize();
	}

	toggle_label() {
		this.$expand_button && this.$expand_button.text(this.get_button_label());
	}

	get_button_label() {
		return this.expanded ? __('Collapse', null, 'Shrink code field.') : __('Expand', null, 'Enlarge code field.');
	}

	set_language() {
		this.editor.session.setMode('ace/mode/json');
		this.editor.setKeyboardHandler('ace/keyboard/vscode');
	}

	parse(value) {
		if (value == null) {
			value = "";
		}
		return value;
	}

	set_formatted_input(value) {
		return this.load_lib().then(() => {
			if (!this.editor) return;
			if (!value) value = '';
			if (value === this.get_input_value()) return;
			this.editor.session.setValue(value);
		});
	}

	get_input_value() {
		return this.editor ? this.editor.session.getValue() : '';
	}

	load_lib() {
		if (this.library_loaded) return this.library_loaded;

		if (frappe.boot.developer_mode) {
			this.root_lib_path = '/assets/frappe/node_modules/ace-builds/src-noconflict/';
		} else {
			this.root_lib_path = '/assets/frappe/node_modules/ace-builds/src-min-noconflict/';
		}

		this.library_loaded = new Promise(resolve => {
			frappe.require(this.root_lib_path + 'ace.js', () => {
				window.ace.config.set('basePath', this.root_lib_path);
				resolve();
			});
		});

		return this.library_loaded;
	}
};
