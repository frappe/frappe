import Quill from 'quill/dist/quill';
import { ImageDrop } from 'quill-image-drop-module';

Quill.register('modules/imageDrop', ImageDrop);

frappe.ui.form.ControlTextEditor = frappe.ui.form.ControlCode.extend({
	make_input() {
		this.has_input = true;
		this.make_quill_editor();
	},

	make_quill_editor() {
		if (this.quill) return;
		this.quill_container = $('<div>').appendTo(this.input_area);
		this.quill = new Quill(this.quill_container[0], this.get_quill_options());
		this.bind_events();
	},

	bind_events() {
		this.quill.on('text-change', frappe.utils.debounce(() => {
			const input_value = this.get_input_value();
			if (this.value === input_value) return;

			this.parse_validate_and_set_in_model(input_value);
		}, 300));

		$(this.quill.root).on('keydown', (e) => {
			const key = frappe.ui.keys.get_key(e);
			if (['ctrl+b', 'meta+b'].includes(key)) {
				e.stopPropagation();
			}
		});

		$(this.quill.root).on('drop', (e) => {
			e.stopPropagation();
		});
	},

	get_quill_options() {
		return {
			modules: {
				toolbar: this.get_toolbar_options(),
				imageDrop: true
			},
			theme: 'snow'
		};
	},

	get_toolbar_options() {
		return [
			[{ 'header': [1, 2, 3, false] }],
			['bold', 'italic', 'underline'],
			['blockquote', 'code-block'],
			['link', 'image'],
			[{ 'list': 'ordered' }, { 'list': 'bullet' }],
			[{ 'align': [] }],
			[{ 'indent': '-1'}, { 'indent': '+1' }],
			[{ 'font': [] }],
			['clean']
		];
	},

	parse(value) {
		if (value == null) {
			value = "";
		}
		return frappe.dom.remove_script_and_style(value);
	},

	set_formatted_input(value) {
		if (!this.quill) return;
		if (value === this.get_input_value()) return;
		this.quill.setContents(this.quill.clipboard.convert(value));
	},

	get_input_value() {
		return this.quill ? this.quill.root.innerHTML : '';
	}
});
