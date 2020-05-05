import Quill from 'quill';

// replace <p> tag with <div>
const Block = Quill.import('blots/block');
Block.tagName = 'DIV';
Quill.register(Block, true);

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
}
Quill.register(Table, true);

// link without href
var Link = Quill.import('formats/link');

class MyLink extends Link {
	static create(value) {
		let node = super.create(value);
		value = this.sanitize(value);
		node.setAttribute('href', value);
		if(value.startsWith('/') || value.indexOf(window.location.host)) {
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

frappe.ui.form.ControlTextEditor = frappe.ui.form.ControlCode.extend({
	make_wrapper() {
		this._super();
		this.$wrapper.find(".like-disabled-input").addClass('text-editor-print');
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
		// quill keeps ol as a common container for both type of lists
		// and uses css for appearances, this is not semantic
		// so we convert ol to ul if it is unordered
		const $value = $(`<div>${value}</div>`);
		$value.find('ol li[data-list=bullet]:first-child').each((i, li) => {
			let $li = $(li);
			let $parent = $li.parent();
			let $children = $parent.children();
			let $ul = $('<ul>').append($children);
			$parent.replaceWith($ul);
		});
		value = this.convertLists($value.html());
		return value;
	},

	// hack
	// https://github.com/quilljs/quill/issues/979
	convertLists(richtext) {
		const tempEl = window.document.createElement('div');
		tempEl.setAttribute('style', 'display: none;');
		tempEl.innerHTML = richtext;
		const startLi = '::startli::';
		const endLi = '::endli::';

		['ul','ol'].forEach((type) => {
			const startTag = `::start${type}::`;
			const endTag = `::end${type}::`;

			// Grab each list, and work on it in turn
			Array.from(tempEl.querySelectorAll(type)).forEach((outerListEl) => {
				const listChildren = Array.from(outerListEl.children).filter((el) => el.tagName === 'LI');

				let lastLiLevel = 0;
				let currentLiLevel = 0;
				let difference = 0;

				// Now work through each li in this list
				for (let i = 0; i < listChildren.length; i++) {
					const currentLi = listChildren[i];
					lastLiLevel = currentLiLevel;
					currentLiLevel = this.getListLevel(currentLi);
					difference = currentLiLevel - lastLiLevel;

					// we only need to add tags if the level is changing
					if (difference > 0) {
						currentLi.before((startLi + startTag).repeat(difference));
					} else if (difference < 0) {
						currentLi.before((endTag + endLi).repeat(-difference));
					}

					if (i === listChildren.length - 1) {
						// last li, account for the fact that it might not be at level 0
						currentLi.after((endTag + endLi).repeat(currentLiLevel));
					}
				}
			});
		});

		//  Get the content in the element and replace the temporary tags with new ones
		let newContent = tempEl.innerHTML;

		newContent = newContent.replace(/::startul::/g, '<ul>');
		newContent = newContent.replace(/::endul::/g, '</ul>');
		newContent = newContent.replace(/::startol::/g, '<ol>');
		newContent = newContent.replace(/::endol::/g, '</ol>');
		newContent = newContent.replace(/::startli::/g, '<li>');
		newContent = newContent.replace(/::endli::/g, '</li>');

		// remove quill classes
		newContent = newContent.replace(/data-list=.bullet./g, '');
		newContent = newContent.replace(/class=.ql-indent-../g, '');

		// ul/ol should not be inside another li
		newContent = newContent.replace(/<\/li><li><ul>/g, '<ul>');
		newContent = newContent.replace(/<\/li><li><ol>/g, '<ol>');
		tempEl.remove();

		return newContent;
	},

	getListLevel(el) {
		const className = el.className || '0';
		return +className.replace(/[^\d]/g, '');
	},

	set_focus() {
		this.quill.focus();
	}
});
