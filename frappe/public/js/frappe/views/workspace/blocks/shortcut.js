import Block from "./block.js";
export default class Shortcut extends Block {
	static get toolbox() {
		return {
			title: "Shortcut",
			icon: frappe.utils.icon("shortcut", "sm"),
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	constructor({ data, api, config, readOnly, block }) {
		super({ data, api, config, readOnly, block });
		this.col = this.data.col ? this.data.col : "3";
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

	rendered() {
		super.rendered();

		this.remove_last_divider();
		$(window).resize(() => {
			this.remove_last_divider();
		});
	}

	remove_last_divider() {
		let block = this.wrapper.closest(".ce-block");
		let container_offset_right = $(".layout-main-section")[0].offsetWidth;
		let block_offset_right = block.offsetLeft + block.offsetWidth;

		if (container_offset_right - block_offset_right <= 110) {
			$(block).find(".divider").addClass("hidden");
		} else {
			$(block).find(".divider").removeClass("hidden");
		}
	}

	render() {
		this.wrapper = document.createElement("div");
		this.new("shortcut");

		if (this.data && this.data.shortcut_name) {
			let has_data = this.make("shortcut", this.data.shortcut_name);
			if (!has_data) return this.wrapper;
		}

		if (!this.readOnly) {
			$(this.wrapper).find(".widget").addClass("shortcut edit-mode");
			this.add_settings_button();
			this.add_new_block_button();
		}
		return this.wrapper;
	}

	validate(savedData) {
		if (!savedData.shortcut_name) {
			return false;
		}

		return true;
	}

	save() {
		return {
			shortcut_name: this.wrapper.getAttribute("shortcut_name"),
			col: this.get_col(),
			new: this.new_block_widget,
		};
	}
}
