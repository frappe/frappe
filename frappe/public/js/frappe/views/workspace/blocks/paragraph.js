import Block from "./block.js";
export default class Paragraph extends Block {

	static get DEFAULT_PLACEHOLDER() {
		return '';
	}

	constructor({ data, config, api, readOnly }) {
		super({ config, api, readOnly });

		this._CSS = {
			block: this.api.styles.block,
			wrapper: 'ce-paragraph'
		};

		if (!this.readOnly) {
			this.onKeyUp = this.onKeyUp.bind(this);
		}

		this._placeholder = this.config.placeholder ? this.config.placeholder : Paragraph.DEFAULT_PLACEHOLDER;
		this._data = {};
		this._element = this.drawView();
		this._preserveBlank = this.config.preserveBlank !== undefined ? this.config.preserveBlank : false;

		this.data = data;
		this.col = this.data.col ? this.data.col : "12";
	}

	onKeyUp(e) {
		$(this.wrapper.parentElement).find('.block-list-container.dropdown-list').hide();
		if (e.code !== 'Backspace' && e.code !== 'Delete') {
			return;
		}

		const {textContent} = this._element;

		if (textContent === '') {
			$(this.wrapper.parentElement).find('.block-list-container.dropdown-list').show();
			this._element.innerHTML = '';
		}
	}

	drawView() {
		let div = document.createElement('DIV');

		div.classList.add(this._CSS.wrapper, this._CSS.block, 'widget');
		div.contentEditable = false;

		if (!this.readOnly) {
			div.contentEditable = true;
			div.addEventListener('focus', () => {
				const {textContent} = this._element;
				if (textContent !== '') return;
				let $wrapper = $(this.wrapper).hasClass('ce-paragraph') ? $(this.wrapper.parentElement) : $(this.wrapper);
				let $block_list_container = $wrapper.find('.block-list-container.dropdown-list');
				$block_list_container.show();
			});
			div.addEventListener('blur', () => {
				let $block_list_container = $(this.wrapper.parentElement).find('.block-list-container.dropdown-list');
				setTimeout(() => $block_list_container.hide(), 1);
			});
			div.dataset.placeholder = this.api.i18n.t(this._placeholder);
			div.addEventListener('keyup', this.onKeyUp);
		}
		return div;
	}

	open_block_list() {
		let dropdown_title = 'Templates';
		let $block_list_container = $(`
			<div class="block-list-container dropdown-list">
				<div class="dropdown-title">${dropdown_title.toUpperCase()}</div>
			</div>
		`);

		let all_blocks = frappe.wspace_block.blocks;
		Object.keys(all_blocks).forEach(key => {
			let $block_list_item = $(`
				<div class="block-list-item dropdown-item">
					<span class="dropdown-item-icon">${all_blocks[key].toolbox.icon}</span>
					<span class="dropdown-item-label">${__(all_blocks[key].toolbox.title)}</span>
				</div>
			`);

			$block_list_item.click(event => {
				event.stopPropagation();
				const index = this.api.blocks.getCurrentBlockIndex();
				this.api.blocks.delete();
				this.api.blocks.insert(key, {}, {}, index);
				this.api.caret.setToBlock(index);
			});

			$block_list_container.append($block_list_item);
		});

		$block_list_container.hide();
		$block_list_container.appendTo(this.wrapper);
	}

	render() {
		this.wrapper = document.createElement('div');
		if (!this.readOnly) {
			let $para_control = $(`<div class="widget-control paragraph-control"></div>`);

			this.wrapper.appendChild(this._element);
			this._element.classList.remove('widget');
			$para_control.appendTo(this.wrapper);
			
			this.wrapper.classList.add('widget', 'paragraph');

			this.open_block_list();
			this.add_new_block_button();
			this.add_settings_button();

			frappe.utils.add_custom_button(
				frappe.utils.icon('drag', 'xs'),
				null,
				"drag-handle",
				`${__('Drag')}`,
				null,
				$para_control
			);

			return this.wrapper;
		}
		return this._element;
	}

	merge(data) {
		let newData = {
			text: this.data.text + data.text
		};

		this.data = newData;
	}

	validate(savedData) {
		if (savedData.text.trim() === '' && !this._preserveBlank) {
			return false;
		}

		return true;
	}

	save() {
		this.wrapper = this._element;
		return {
			text: this.wrapper.innerHTML,
			col: this.get_col(),
		};
	}

	rendered() {
		!this.readOnly && this.resizer(this._element);
		var e = this._element.closest('.ce-block');
		e.classList.add("col-" + this.get_col());
	}

	onPaste(event) {
		const data = {
			text: event.detail.data.innerHTML
		};

		this.data = data;
	}

	static get sanitize() {
		return {
			text: {
				br: true,
				b: true,
				i: true,
				a: true,
				span: true
			}
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	get data() {
		let text = this._element.innerHTML;

		this._data.text = text;

		return this._data;
	}

	set data(data) {
		this._data = data || {};

		this._element.innerHTML = __(this._data.text) || '';
	}

	static get pasteConfig() {
		return {
			tags: [ 'P' ]
		};
	}

	static get toolbox() {
		return {
			title: 'Text',
			icon: frappe.utils.icon('text', 'sm')
		};
	}
}