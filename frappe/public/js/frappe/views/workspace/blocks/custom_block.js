import Block from "./block.js";
export default class CustomBlock extends Block {
	static get toolbox() {
		return {
			title: "Custom Block",
			icon: frappe.utils.icon("edit", "sm"),
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	constructor({ data, api, config, readOnly, block }) {
		super({ data, api, config, readOnly, block });
		this.col = this.data.col ? this.data.col : "12";
		this.allow_customization = !this.readOnly;
		this.options = {
			allow_sorting: this.allow_customization,
			allow_create: this.allow_customization,
			allow_delete: this.allow_customization,
			allow_hiding: false,
			allow_edit: true,
			allow_resize: true,
			min_width: 2,
		};
	}

	render() {
		this.wrapper = document.createElement("div");
		this.new("custom_block");

		if (this.data && this.data.custom_block_name) {
			let has_data = this.make("custom_block", this.data.custom_block_name);
			if (!has_data) return;
		}

		if (!this.readOnly) {
			$(this.wrapper).find(".widget").addClass("custom_block edit-mode");
			this.add_settings_button();
			this.add_new_block_button();
		}

		return this.wrapper;
	}

	validate(savedData) {
		if (!savedData.custom_block_name) {
			return false;
		}

		return true;
	}

	save() {
		return {
			custom_block_name: this.wrapper.getAttribute("custom_block_name"),
			col: this.get_col(),
			new: this.new_block_widget,
		};
	}
}
