import Block from "./block.js";
export default class Paragraph extends Block {
	static get DEFAULT_PLACEHOLDER() {
		return "";
	}

	constructor({ data, config, api, readOnly }) {
		super({ config, api, readOnly });

		this._CSS = {
			block: this.api.styles.block,
			wrapper: "ce-paragraph",
		};

		if (!this.readOnly) {
			this.onKeyUp = this.onKeyUp.bind(this);
		}

		this._placeholder = this.config.placeholder
			? this.config.placeholder
			: Paragraph.DEFAULT_PLACEHOLDER;
		this._data = {};
		this._element = this.drawView();
		this._preserveBlank =
			this.config.preserveBlank !== undefined ? this.config.preserveBlank : false;

		this.data = data;
		this.col = this.data.col ? this.data.col : "12";
	}

	onKeyUp(e) {
		if (!this.wrapper) return;
		this.show_hide_block_list(true);
		if (e.code !== "Backspace" && e.code !== "Delete") {
			return;
		}

		const { textContent } = this._element;

		if (textContent === "") {
			this.show_hide_block_list();
			this._element.innerHTML = "";
		}
	}

	show_hide_block_list(hide) {
		let $wrapper = $(this.wrapper).hasClass("ce-paragraph")
			? $(this.wrapper.parentElement)
			: $(this.wrapper);
		let $block_list_container = $wrapper.find(".block-list-container.dropdown-list");
		$block_list_container.removeClass("hidden");
		hide && $block_list_container.addClass("hidden");
	}

	drawView() {
		let div = document.createElement("DIV");

		div.classList.add(this._CSS.wrapper, this._CSS.block, "widget");
		div.contentEditable = false;

		if (!this.readOnly) {
			div.contentEditable = true;
			div.addEventListener("focus", () => {
				const { textContent } = this._element;
				if (textContent !== "") return;
				this.show_hide_block_list();
			});
			div.addEventListener("blur", () => {
				!this.over_block_list_item && this.show_hide_block_list(true);
			});
			div.dataset.placeholder = this.api.i18n.t(this._placeholder);
			div.addEventListener("keyup", this.onKeyUp);
		}
		return div;
	}

	open_block_list() {
		let dropdown_title = __("Templates");
		let $block_list_container = $(`
			<div class="block-list-container dropdown-list">
				<div class="dropdown-title">${dropdown_title.toUpperCase()}</div>
			</div>
		`);

		let all_blocks = frappe.workspace_block.blocks;
		Object.keys(all_blocks).forEach((key) => {
			let $block_list_item = $(`
				<div class="block-list-item dropdown-item">
					<span class="dropdown-item-icon">${all_blocks[key].toolbox.icon}</span>
					<span class="dropdown-item-label">${__(all_blocks[key].toolbox.title)}</span>
				</div>
			`);

			$block_list_item.click((event) => {
				event.stopPropagation();
				const index = this.api.blocks.getCurrentBlockIndex();
				this.api.blocks.delete();
				this.api.blocks.insert(key, {}, {}, index);
				this.api.caret.setToBlock(index);
			});

			$block_list_item
				.mouseenter(() => {
					this.over_block_list_item = true;
				})
				.mouseleave(() => {
					this.over_block_list_item = false;
				});

			$block_list_container.append($block_list_item);
		});

		$block_list_container.addClass("hidden");
		$block_list_container.appendTo(this.wrapper);
	}

	render() {
		this.wrapper = document.createElement("div");
		if (!this.readOnly) {
			let $para_control = $(`<div class="widget-control paragraph-control"></div>`);

			this.wrapper.appendChild(this._element);
			this._element.classList.remove("widget");
			$para_control.appendTo(this.wrapper);

			this.wrapper.classList.add("widget", "paragraph", "edit-mode");

			this.open_block_list();
			this.add_new_block_button();
			this.add_settings_button();

			frappe.utils.add_custom_button(
				frappe.utils.icon("drag", "xs"),
				null,
				"drag-handle",
				__("Drag"),
				null,
				$para_control
			);

			return this.wrapper;
		}
		return this._element;
	}

	merge(data) {
		let newData = {
			text: this.data.text + data.text,
		};

		this.data = newData;
	}

	validate(savedData) {
		if (savedData.text.trim() === "" && !this._preserveBlank) {
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
		super.rendered(this._element);
	}

	onPaste(event) {
		const data = {
			text: event.detail.data.innerHTML,
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
				span: true,
			},
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

		this._element.innerHTML = __(this._data.text) || "";
	}

	static get pasteConfig() {
		return {
			tags: ["P"],
		};
	}

	static get toolbox() {
		return {
			title: "Text",
			icon: frappe.utils.icon("text", "sm"),
		};
	}
}
