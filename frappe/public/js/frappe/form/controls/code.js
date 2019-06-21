frappe.ui.form.ControlCode = frappe.ui.form.ControlText.extend({
	make_input() {
		if (this.editor) return;
		this.load_lib().then(() => this.make_ace_editor());
	},

	make_ace_editor() {
		if (this.editor) return;
		this.ace_editor_target = $('<div class="ace-editor-target"></div>')
			.appendTo(this.input_area);

		// styling
		this.ace_editor_target.addClass('border rounded');
		this.ace_editor_target.css('height', 300);

		// initialize
		const ace = window.ace;
		this.editor = ace.edit(this.ace_editor_target.get(0));
		this.editor.setTheme('ace/theme/tomorrow');
		this.set_language();

		// events
		this.editor.session.on('change', frappe.utils.debounce(() => {
			const input_value = this.get_input_value();
			this.parse_validate_and_set_in_model(input_value);
		}, 300));
	},

	set_language() {
		const language_map = {
			'Javascript': 'ace/mode/javascript',
			'JS': 'ace/mode/javascript',
			'HTML': 'ace/mode/html',
			'CSS': 'ace/mode/css',
			'Markdown': 'ace/mode/markdown',
			'SCSS': 'ace/mode/scss',
			'JSON': 'ace/mode/json'
		};
		const language = this.df.options;

		const valid_languages = Object.keys(language_map);
		if (!valid_languages.includes(language)) {
			// eslint-disable-next-line
			console.warn(`Invalid language option provided for field "${this.df.label}". Valid options are ${valid_languages.join(', ')}.`);
		}

		const ace_language_mode = language_map[language] || '';
		this.editor.session.setMode(ace_language_mode);
	},

	parse(value) {
		if (value == null) {
			value = "";
		}
		return value;
	},

	set_formatted_input(value) {
		return this.load_lib().then(() => {
			if (!this.editor) return;
			if (!value) value = '';
			if (value === this.get_input_value()) return;
			this.editor.session.setValue(value);
		});
	},

	get_input_value() {
		return this.editor ? this.editor.session.getValue() : '';
	},

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
});
