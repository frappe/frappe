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
		if (e.code !== 'Backspace' && e.code !== 'Delete') {
			return;
		}

		const {textContent} = this._element;

		if (textContent === '') {
			this._element.innerHTML = '';
		}
	}

	drawView() {
		let div = document.createElement('DIV');

		div.classList.add(this._CSS.wrapper, this._CSS.block, 'widget');
		div.contentEditable = false;
		div.dataset.placeholder = this.api.i18n.t(this._placeholder);

		if (!this.readOnly) {
			div.contentEditable = true;
			div.addEventListener('keyup', this.onKeyUp);
		}
		return div;
	}

	render() {
		this.wrapper = document.createElement('div');
		this.wrapper.contentEditable = this.readOnly ? 'false' : 'true';
		if (!this.readOnly) {
			let $para_control = $(`<div class="paragraph-control"></div>`);

			this.wrapper.appendChild(this._element);
			this._element.classList.remove('widget');
			$para_control.appendTo(this.wrapper);
			
			this.wrapper.classList.add('widget');

			frappe.utils.add_custom_button(
				frappe.utils.icon('dot-horizontal', 'xs'),
				(event) => {
					let evn = event;
					!$('.ce-settings.ce-settings--opened').length &&
					setTimeout(() => {
						this.api.toolbar.toggleBlockSettings();
						var position = $(evn.target).offset();
						$('.ce-settings.ce-settings--opened').offset({
							top: position.top + 25,
							left: position.left - 77
						});
					}, 50);
				},
				"tune-btn",
				`${__('Tune')}`,
				null,
				$para_control
			);

			frappe.utils.add_custom_button(
				frappe.utils.icon('drag', 'xs'),
				null,
				"drag-handle",
				`${__('Drag')}`,
				null,
				$para_control
			);

			frappe.utils.add_custom_button(
				frappe.utils.icon('delete', 'xs'),
				() => this.api.blocks.delete(),
				"delete-paragraph",
				`${__('Delete')}`,
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
		var e = this._element.closest('.ce-block');
		e.classList.add("col-" + this.get_col());
	}

	onPaste(event) {
		const data = {
			text: event.detail.data.innerHTML
		};

		this.data = data;
	}

	static get conversionConfig() {
		return {
			export: 'text', // to convert Paragraph to other block, use 'text' property of saved data
			import: 'text' // to covert other block's exported string to Paragraph, fill 'text' property of tool data
		};
	}

	static get sanitize() {
		return {
			text: {
				br: true,
				b: true,
				i: true,
				a: true
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
			icon: '<svg viewBox="0.2 -0.3 9 11.4" width="12" height="14"><path d="M0 2.77V.92A1 1 0 01.2.28C.35.1.56 0 .83 0h7.66c.28.01.48.1.63.28.14.17.21.38.21.64v1.85c0 .26-.08.48-.23.66-.15.17-.37.26-.66.26-.28 0-.5-.09-.64-.26a1 1 0 01-.21-.66V1.69H5.6v7.58h.5c.25 0 .45.08.6.23.17.16.25.35.25.6s-.08.45-.24.6a.87.87 0 01-.62.22H3.21a.87.87 0 01-.61-.22.78.78 0 01-.24-.6c0-.25.08-.44.24-.6a.85.85 0 01.61-.23h.5V1.7H1.73v1.08c0 .26-.08.48-.23.66-.15.17-.37.26-.66.26-.28 0-.5-.09-.64-.26A1 1 0 010 2.77z"/></svg>',
			title: 'Text'
		};
	}
}