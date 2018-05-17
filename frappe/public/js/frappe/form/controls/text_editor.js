frappe.ui.form.ControlTextEditor = frappe.ui.form.ControlCode.extend({
	make_input() {
		this.has_input = true;

		const ckeditor_options = {
			image: {
				toolbar: [ 'imageTextAlternative', '|', 'imageStyle:alignLeft', 'imageStyle:full', 'imageStyle:alignRight' ],

				styles: [
					'full',
					'alignLeft',
					'alignRight'
				]
			}
		};

		this.editor_loaded = frappe.require('/assets/frappe/js/lib/ckeditor/ckeditor.js')
			.then(() => {
				this.editor = $("<div>").appendTo(this.input_area);
				return ClassicEditor.create(this.editor[0], ckeditor_options)
					.then(editor => {
						this.ckeditor = editor;

						this.ckeditor.plugins.get('FileRepository').createUploadAdapter = (loader) => {
							return new FileUploader(loader, this);
						};

						this.ckeditor.model.document.on('change', () => {
							const input_value = this.get_input_value();
							if (this.value === input_value) return;

							this.parse_validate_and_set_in_model(this.get_input_value());
						});
					});
			});

		// disable default form upload handler
		$(this.input_area).on('drop', e => {
			e.stopPropagation();
		});
	},

	parse: function (value) {
		if (value == null) {
			value = "";
		}
		return frappe.dom.remove_script_and_style(value);
	},

	set_formatted_input: function (value) {
		if (value === this.get_input_value()) return;
		this.editor_loaded.then(() => this.ckeditor.setData(this.format_for_input(value)));
	},

	get_input_value() {
		return this.ckeditor ? this.ckeditor.getData() : '';
	}
});

class FileUploader {
	constructor(loader, control) {
		this.loader = loader;
		this.control = control;
	}

	upload() {
		return new Promise(resolve => {
			frappe.dom.file_to_base64(this.loader.file)
				.then(base64 => {
					resolve({
						default: base64
					})
				});
		});
	}

	abort() { }
}
