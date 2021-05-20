export default class Paragraph {

	static get DEFAULT_PLACEHOLDER() {
		return '';
	}

	constructor({data, config, api, readOnly}) {
		this.api = api;
		this.readOnly = readOnly;

		this._CSS = {
			block: this.api.styles.block,
			wrapper: 'ce-paragraph'
		};

		if (!this.readOnly) {
			this.onKeyUp = this.onKeyUp.bind(this);
		}

		this._placeholder = config.placeholder ? config.placeholder : Paragraph.DEFAULT_PLACEHOLDER;
		this._data = {};
		this._element = this.drawView();
		this._preserveBlank = config.preserveBlank !== undefined ? config.preserveBlank : false;

		this.data = data;
		this.col = this.data.col ? this.data.col : "12";
		this.pt = this.data.pt ? this.data.pt : "0";
		this.pr = this.data.pr ? this.data.pr : "0";
		this.pb = this.data.pb ? this.data.pb : "0";
		this.pl = this.data.pl ? this.data.pl : "0";
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

			this.add_custom_button(
				frappe.utils.icon('delete', 'xs'),
				() => this.api.blocks.delete(),
				"delete-paragraph",
				`${__('Delete')}`,
				null,
				$para_control
			);

			this.add_custom_button(
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

	add_custom_button(html, action, class_name = "", title="", btn_type, wrapper) {
		if (!btn_type) btn_type = 'btn-secondary';
		let button = $(
			`<button class="btn ${btn_type} btn-xs ${class_name}" title="${title}">${html}</button>`
		);
		button.click(event => {
			event.stopPropagation();
			action && action();
		});
		button.appendTo(wrapper);
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

	save(toolsContent) {
		return {
			text: toolsContent.innerText,
			col: this._getCol(),
			pt: this._getPadding("t"),
			pr: this._getPadding("r"),
			pb: this._getPadding("b"),
			pl: this._getPadding("l")
		};
	}

	rendered() {
		var e = this._element.closest('.ce-block');
		e.classList.add("col-" + this.col);
		e.classList.add("pt-" + this.pt);
		e.classList.add("pr-" + this.pr);
		e.classList.add("pb-" + this.pb);
		e.classList.add("pl-" + this.pl);
	}

	_getCol() {
		var e = 12;
		var t = "col-12";
		var n = this._element.closest('.ce-block');
		var r = new RegExp(/\bcol-.+?\b/, "g");
		if (n.className.match(r)) {
			n.classList.forEach(function (e) {
				e.match(r) && (t = e);
			});
			var a = t.split("-");
			e = parseInt(a[1]);
		}
		return e;
	}

	_getPadding() {
		var e = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : "l";
		var t = 0;
		var n = "p" + e + "-0";
		var r = this._element.closest('.ce-block');
		var a = new RegExp(/\pl-.+?\b/, "g");
		var i = new RegExp(/\pr-.+?\b/, "g");
		var o = new RegExp(/\pt-.+?\b/, "g");
		var c = new RegExp(/\pb-.+?\b/, "g");
		if ("l" == e) {
			if (r.className.match(a)) {
				r.classList.forEach(function (e) {
					e.match(a) && (n = e);
				});
				var s = n.split("-");
				t = parseInt(s[1]);
			}
		} else if ("r" == e) {
			if (r.className.match(i)) {
				r.classList.forEach(function (e) {
					e.match(i) && (n = e);
				});
				var l = n.split("-");
				t = parseInt(l[1]);
			}
		} else if ("t" == e) {
			if (r.className.match(o)) {
				r.classList.forEach(function (e) {
					e.match(o) && (n = e);
				});
				var u = n.split("-");
				t = parseInt(u[1]);
			}
		} else if ("b" == e && r.className.match(c)) {
			r.classList.forEach(function (e) {
				e.match(c) && (n = e);
			});
			var p = n.split("-");
			t = parseInt(p[1]);
		}
		return t;
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

		this._element.innerHTML = this._data.text || '';
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