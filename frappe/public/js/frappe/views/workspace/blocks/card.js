import Block from "./block.js";
export default class Card extends Block {
	static get toolbox() {
		return {
			title: "Card",
			icon: frappe.utils.icon("card", "sm"),
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	constructor({ data, api, config, readOnly, block }) {
		super({ data, api, config, readOnly, block });
		this.sections = {};
		this.col = this.data.col ? this.data.col : "4";
		this.allow_customization = !this.readOnly;
		this.options = {
			allow_sorting: this.allow_customization,
			allow_create: this.allow_customization,
			allow_delete: this.allow_customization,
			allow_hiding: false,
			allow_edit: true,
			allow_resize: true,
		};
	}

	render() {
		this.wrapper = document.createElement("div");
		this.new("card", "links");

		if (this.data && this.data.card_name) {
			let has_data = this.make("card", this.data.card_name, "links");
			if (!has_data) return;
		}

		if (!this.readOnly) {
			$(this.wrapper).find(".widget").addClass("links edit-mode");
			this.add_settings_button();
			this.add_new_block_button();
		}

		return this.wrapper;
	}

	validate(savedData) {
		if (!savedData.card_name) {
			return false;
		}

		return true;
	}

	save() {
		return {
			card_name: this.wrapper.getAttribute("card_name"),
			col: this.get_col(),
			new: this.new_block_widget,
		};
	}
}
