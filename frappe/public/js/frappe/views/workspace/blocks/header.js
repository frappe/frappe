import Block from "./block.js";
export default class Header extends Block {
	constructor({ data, config, api, readOnly }) {
		super({ config, api, readOnly });

		this._settings = this.config;
		this._data = this.normalizeData(data);
		this._element = this.getTag();

		this.data = data;
		this.col = this.data.col ? this.data.col : "12";
	}

	normalizeData(data) {
		const newData = {};

		if (typeof data !== "object") {
			data = {};
		}

		newData.text = data.text || "";
		newData.col = parseInt(data.col) || 12;

		return newData;
	}

	render() {
		this.wrapper = document.createElement("div");
		if (!this.readOnly) {
			let $widget_head = $(`<div class="widget-head"></div>`);
			let $widget_control = $(`<div class="widget-control"></div>`);

			$widget_head[0].appendChild(this._element);
			$widget_control.appendTo($widget_head);
			$widget_head.appendTo(this.wrapper);

			this.wrapper.classList.add("widget", "header", "edit-mode");

			this.add_settings_button();
			this.add_new_block_button();

			frappe.utils.add_custom_button(
				frappe.utils.icon("drag", "xs"),
				null,
				"drag-handle",
				__("Drag"),
				null,
				$widget_control
			);

			return this.wrapper;
		}
		return this._element;
	}

	merge(data) {
		const newData = {
			text: this.data.text + data.text,
		};

		this.data = newData;
	}

	validate(blockData) {
		return blockData.text.trim() !== "";
	}

	save() {
		this.wrapper = this._element;
		return {
			text: this.wrapper.innerHTML.replace(/&nbsp;/gi, ""),
			col: this.get_col(),
		};
	}

	rendered() {
		super.rendered(this._element);
	}

	static get sanitize() {
		return {
			level: false,
			text: {
				br: true,
				b: true,
				i: true,
				a: true,
				span: true,
			},
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	get data() {
		this._data.text = this._element.innerHTML;

		return this._data;
	}

	set data(data) {
		this._data = this.normalizeData(data);

		if (data.text !== undefined) {
			let text = __(this._data.text) || "";
			const contains_html_tag = /<[a-z][\s\S]*>/i.test(text);

			// apply translation to header text
			let div = document.createElement("div");
			div.innerHTML = text;
			let only_text = div.innerText;
			only_text = frappe.utils.escape_html(only_text);
			text = text.replace(only_text, __(only_text));

			this._element.innerHTML = contains_html_tag
				? text
				: `<span class="h${this._settings.default_size}">${text}</span>`;
		}

		if (!this.readOnly && this.wrapper) {
			this.wrapper.classList.add("widget", "header");
		}
	}

	getTag() {
		const tag = document.createElement("DIV");

		let text = this._data.text || "&nbsp";
		tag.innerHTML = `<span class="h${this._settings.default_size}"><b>${text}</b></span>`;

		tag.classList.add("ce-header");

		if (!this.readOnly) {
			tag.contentEditable = true;
		}

		tag.dataset.placeholder = this.api.i18n.t(this._settings.placeholder || "");

		return tag;
	}

	static get toolbox() {
		return {
			title: "Heading",
			icon: frappe.utils.icon("header", "sm"),
		};
	}
}
