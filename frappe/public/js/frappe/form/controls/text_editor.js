import Quill from 'quill';

const CodeBlockContainer = Quill.import('formats/code-block-container');
CodeBlockContainer.tagName = 'PRE';
Quill.register(CodeBlockContainer, true);

// table
const Table = Quill.import('formats/table-container');
const superCreate = Table.create.bind(Table);
Table.create = (value) => {
	const node = superCreate(value);
	node.classList.add('table');
	node.classList.add('table-bordered');
	return node;
};

Quill.register(Table, true);

// link without href
var Link = Quill.import('formats/link');

class MyLink extends Link {
	static create(value) {
		let node = super.create(value);
		value = this.sanitize(value);
		node.setAttribute('href', value);
		if (value.startsWith('/') || value.indexOf(window.location.host)) {
			// no href if internal link
			node.removeAttribute('target');
		}
		return node;
	}
}

Quill.register(MyLink, true);

// image uploader
const Uploader = Quill.import('modules/uploader');
Uploader.DEFAULTS.mimetypes.push('image/gif');

// inline style
const BackgroundStyle = Quill.import('attributors/style/background');
const ColorStyle = Quill.import('attributors/style/color');
const FontStyle = Quill.import('attributors/style/font');
const AlignStyle = Quill.import('attributors/style/align');
const DirectionStyle = Quill.import('attributors/style/direction');
Quill.register(BackgroundStyle, true);
Quill.register(ColorStyle, true);
Quill.register(FontStyle, true);
Quill.register(AlignStyle, true);
Quill.register(DirectionStyle, true);

// replace font tag with span
const Inline = Quill.import('blots/inline');

class CustomColor extends Inline {
	constructor(domNode, value) {
		super(domNode, value);
		this.domNode.style.color = this.domNode.color;
		domNode.outerHTML = this.domNode.outerHTML.replace(/<font/g, '<span').replace(/<\/font>/g, '</span>');
	}
}

CustomColor.blotName = "customColor";
CustomColor.tagName = "font";

Quill.register(CustomColor, true);

frappe.ui.form.ControlTextEditor = frappe.ui.form.ControlCode.extend({
	make_wrapper() {
		this._super();
	},

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
		this.quill.on('text-change', frappe.utils.debounce((delta, oldDelta, source) => {
			if (!this.is_quill_dirty(source)) return;

			const input_value = this.get_input_value();
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

		// table commands
		this.$wrapper.on('click', '.ql-table .ql-picker-item', (e) => {
			const $target = $(e.currentTarget);
			const action = $target.data().value;
			e.preventDefault();

			const table = this.quill.getModule('table');
			if (action === 'insert-table') {
				table.insertTable(2, 2);
			} else if (action === 'insert-row-above') {
				table.insertRowAbove();
			} else if (action === 'insert-row-below') {
				table.insertRowBelow();
			} else if (action === 'insert-column-left') {
				table.insertColumnLeft();
			} else if (action === 'insert-column-right') {
				table.insertColumnRight();
			} else if (action === 'delete-row') {
				table.deleteRow();
			} else if (action === 'delete-column') {
				table.deleteColumn();
			} else if (action === 'delete-table') {
				table.deleteTable();
			}

			if (action !== 'delete-row') {
				table.balanceTables();
			}

			e.preventDefault();
		});
	},

	is_quill_dirty(source) {
		if (source === 'api') return false;
		let input_value = this.get_input_value();
		return this.value !== input_value;
	},

	get_quill_options() {
		return {
			modules: {
				toolbar: this.get_toolbar_options(),
				table: true
			},
			theme: 'snow'
		};
	},

	get_toolbar_options() {
		return [
			[{ 'header': [1, 2, 3, false] }],
			['bold', 'italic', 'underline'],
			[{ 'color': [] }, { 'background': [] }],
			['blockquote', 'code-block'],
			['link', 'image'],
			[{ 'list': 'ordered' }, { 'list': 'bullet' }, { 'list': 'check' }],
			[{ 'align': [] }],
			[{ 'indent': '-1'}, { 'indent': '+1' }],
			[{'table': [
				'insert-table',
				'insert-row-above',
				'insert-row-below',
				'insert-column-right',
				'insert-column-left',
				'delete-row',
				'delete-column',
				'delete-table',
			]}],
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
		if (!value) {
			// clear contents for falsy values like '', undefined or null
			this.quill.setText('');
			return;
		}

		// set html without triggering a focus
		const delta = this.quill.clipboard.convert({ html: value, text: '' });
		this.quill.setContents(delta);
	},

	get_input_value() {
		let value = this.quill ? this.quill.root.innerHTML : '';
		// hack to retain space sequence.
		value = value.replace(/(\s)(\s)/g, ' &nbsp;');

		try {
			if (!$(value).find('.ql-editor').length) {
				value = `<div class="ql-editor read-mode">${value}</div>`;
			}
		} catch(e) {
			value = `<div class="ql-editor read-mode">${value}</div>`;
		}

		return value;
	},

	set_focus() {
		this.quill.focus();
	}
});
