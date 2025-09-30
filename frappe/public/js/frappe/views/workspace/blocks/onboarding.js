import get_dialog_constructor from "../../../widgets/widget_dialog.js";
import Block from "./block.js";
export default class Onboarding extends Block {
	static get toolbox() {
		return {
			title: "Onboarding",
			icon: frappe.utils.icon("onboarding", "sm"),
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
			allow_resize: false,
		};
	}

	rendered() {
		let block = this.wrapper.closest(".ce-block");
		if (this.readOnly && !$(this.wrapper).find(".onboarding-widget-box").is(":visible")) {
			$(block).hide();
		}
		this.set_col_class(block, this.get_col());
	}

	new(block, widget_type = block) {
		let me = this;
		const dialog_class = get_dialog_constructor(widget_type);
		let block_name = block + "_name";
		this.dialog = new dialog_class({
			label: this.label,
			type: widget_type,
			primary_action: (widget) => {
				widget.in_customize_mode = 1;
				this.block_widget = frappe.widget.make_widget({
					...widget,
					widget_type: widget_type,
					container: this.wrapper,
					options: {
						...this.options,
						on_delete: () => this.api.blocks.delete(),
						on_edit: () => this.on_edit(this.block_widget),
					},
					new: true,
				});
				this.block_widget.customize(this.options);
				this.wrapper.setAttribute(
					block_name,
					this.block_widget.label || this.block_widget.onboarding_name
				);
				$(this.wrapper).find(".widget").addClass(`${widget_type} edit-mode`);
				this.new_block_widget = this.block_widget.get_config();
				this.add_settings_button();
			},
		});

		if (!this.readOnly && this.data && !this.data[block_name]) {
			this.dialog.make();

			this.dialog.dialog.get_close_btn().click(() => {
				me.wrapper.closest(".ce-block").remove();
			});
		}
	}

	make(block, block_name) {
		let block_data = this.config.page_data["onboardings"].items.find((obj) => {
			return obj.label == __(block_name);
		});
		if (!block_data) return false;
		this.wrapper.innerHTML = "";
		block_data.in_customize_mode = !this.readOnly;
		this.block_widget = frappe.widget.make_widget({
			container: this.wrapper,
			widget_type: "onboarding",
			in_customize_mode: block_data.in_customize_mode,
			options: {
				...this.options,
				on_delete: () => this.api.blocks.delete(),
				on_edit: () => this.on_edit(this.block_widget),
			},
			label: block_data.label,
			title: block_data.title || __("Let's Get Started"),
			subtitle: block_data.subtitle,
			steps: block_data.items,
			success: block_data.success,
			docs_url: block_data.docs_url,
			user_can_dismiss: block_data.user_can_dismiss,
		});
		this.wrapper.setAttribute(block + "_name", block_name);
		if (!this.readOnly) {
			this.block_widget.customize(this.options);
		}
		return true;
	}

	render() {
		this.wrapper = document.createElement("div");
		this.new("onboarding");

		if (this.data && this.data.onboarding_name) {
			let has_data = this.make("onboarding", this.data.onboarding_name);
			if (!has_data) return this.wrapper;
		}

		if (!this.readOnly) {
			$(this.wrapper).find(".widget").addClass("onboarding edit-mode");
			this.add_settings_button();
			this.add_new_block_button();
		}
		return this.wrapper;
	}

	validate(savedData) {
		if (!savedData.onboarding_name) {
			return false;
		}

		return true;
	}

	save() {
		return {
			onboarding_name: this.wrapper.getAttribute("onboarding_name"),
			col: this.get_col(),
			new: this.new_block_widget,
		};
	}
}
