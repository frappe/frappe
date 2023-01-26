import Block from "./block.js";
export default class Chart extends Block {
	static get toolbox() {
		return {
			title: "Chart",
			icon: frappe.utils.icon("chart", "sm"),
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
			min_width: 6,
			max_widget_count: 2,
		};
	}

	render() {
		this.wrapper = document.createElement("div");
		this.new("chart");

		if (this.data && this.data.chart_name) {
			let has_data = this.make("chart", this.data.chart_name);
			if (!has_data) return;
		}

		if (!this.readOnly) {
			$(this.wrapper).find(".widget").addClass("chart edit-mode");
			this.add_settings_button();
			this.add_new_block_button();
		}

		return this.wrapper;
	}

	validate(savedData) {
		if (!savedData.chart_name) {
			return false;
		}

		return true;
	}

	save() {
		return {
			chart_name: this.wrapper.getAttribute("chart_name"),
			col: this.get_col(),
			new: this.new_block_widget,
		};
	}
}
