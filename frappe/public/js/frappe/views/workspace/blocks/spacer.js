import Block from "./block.js";
export default class Spacer extends Block {
	static get toolbox() {
		return {
			title: "Spacer",
			icon: frappe.utils.icon("spacer", "sm"),
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	constructor({ data, api, config, readOnly }) {
		super({ data, api, config, readOnly });
		this.col = this.data.col ? this.data.col : "12";
	}

	render() {
		this.wrapper = document.createElement("div");
		this.wrapper.classList.add("widget", "spacer");
		if (!this.readOnly) {
			let $spacer = $(`
				<div class="widget-head">
					<div class="spacer-left"></div>
					<div>${__("Spacer")}</div>
					<div class="widget-control"></div>
				</div>
			`);
			$spacer.appendTo(this.wrapper);

			this.wrapper.classList.add("edit-mode");
			this.wrapper.style.minHeight = 40 + "px";

			let $widget_control = $spacer.find(".widget-control");

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
		}
		return this.wrapper;
	}

	save() {
		return {
			col: this.get_col(),
		};
	}
}
