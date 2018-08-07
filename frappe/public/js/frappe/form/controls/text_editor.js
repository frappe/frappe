/* globals ClassicEditor */

frappe.ui.form.ControlTextEditor = frappe.ui.form.ControlCode.extend({
	make_input() {
		this.has_input = true;

		const ckeditor_options = {
			heading: {
				options: [
					{ model: 'paragraph', title: __('Paragraph'), class: 'ck-heading_paragraph' },
					{ model: 'heading1', view: 'h1', title: 'Heading 1', class: 'ck-heading_heading1' },
					{ model: 'heading2', view: 'h2', title: 'Heading 2', class: 'ck-heading_heading2' },
					{ model: 'heading3', view: 'h3', title: 'Heading 3', class: 'ck-heading_heading3' }
				]
			},
			image: {
				toolbar: [ 'imageTextAlternative', '|', 'imageStyle:alignLeft', 'imageStyle:full', 'imageStyle:alignRight' ],

				styles: [
					'full',
					'alignLeft',
					'alignRight'
				]
			}
		};

		this.editor_loaded = frappe.require('/assets/frappe/js/lib/ckeditor/ckeditor.built.js')
			.then(() => {
				this.editor = $("<div>").appendTo(this.input_area);

				let editor_class = ClassicEditor;
				if (this.only_input) {
					editor_class = BalloonEditor;
				}

				return editor_class.create(this.editor[0], ckeditor_options)
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

						this.make_edit_source_dialog();
						this.make_edit_source_btn();
					});
			});

		// disable default form upload handler
		$(this.input_area).on('drop', e => {
			e.stopPropagation();
		});

		// only input

		if (this.only_input) {
			this.$wrapper.addClass('only-input');
		}
	},

	make_edit_source_btn() {
		const edit_source_btn = $(`
			<button class="ck ck-button ck-enabled ck-off" type="button" tabindex="-1"">
				${edit_source_svg}
				<span class="ck ck-tooltip ck-tooltip_s">
					<span class="ck ck-tooltip__text">${__('Edit Source')}</span>
				</span>
				<span class="ck ck-button__label">${__('Edit Source')}</span>
			</button>
		`);

		edit_source_btn.on('click', () => {
			this.edit_source_dialog.set_value('source', this.get_input_value());
			this.edit_source_dialog.show();
		});

		$(this.input_area).find('.ck.ck-toolbar').append(edit_source_btn);
	},

	make_edit_source_dialog() {
		this.edit_source_dialog = new frappe.ui.Dialog({
			title: __('Edit Source'),
			fields: [{
				fieldname: 'source',
				fieldtype: 'Code',
				label: __('HTML')
			}],
			primary_action: ({ source }) => {
				this.set_formatted_input(source);
				this.edit_source_dialog.hide();
			}
		});
	},

	parse(value) {
		if (value == null) {
			value = "";
		}
		return frappe.dom.remove_script_and_style(value);
	},

	set_formatted_input(value) {
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

var edit_source_svg = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-code"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>`;