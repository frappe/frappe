import Block from "./block.js";
export default class NumberCard extends Block {
	static get toolbox() {
		return {
			title: "Number Card",
			icon: frappe.utils.icon("number-card", "sm"),
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
			for_workspace: true,
		};
	}

	render() {
		this.wrapper = document.createElement("div");
		this.new("number_card");

		if (this.data && this.data.number_card_name) {
			let has_data = this.make("number_card", this.data.number_card_name);
			if (!has_data) return;
		}

		if (!this.readOnly) {
			$(this.wrapper).find(".widget").addClass("number_card edit-mode");
			this.add_settings_button();
			this.add_new_block_button();
		}

		return this.wrapper;
	}

	validate(savedData) {
		if (!savedData.number_card_name) {
			return false;
		}

		return true;
	}

	save() {
		return {
			number_card_name: this.wrapper.getAttribute("number_card_name"),
			col: this.get_col(),
			new: this.new_block_widget,
		};
	}
}
