import get_dialog_constructor from "../../../widgets/widget_dialog.js";
import Block from "./block.js";
export default class Onboarding extends Block {
	static get toolbox() {
		return {
			title: 'Onboarding',
			icon: '<svg width="24" height="24" viewBox="2 0 20 24" fill="none"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 11.09v5.455" stroke="#1F272E" fill="none"/><path d="M12.41 7.455a.41.41 0 11-.82 0 .41.41 0 01.82 0z" stroke="#1F272E"/></svg>'
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
			allow_edit: true
		};
	}

	rendered() {
		var e = this.wrapper.closest('.ce-block');
		if (this.readOnly && !$(this.wrapper).find('.onboarding-widget-box').is(':visible')) {
			$(e).hide();
		}
		e.classList.add("col-" + this.get_col());
	}

	new(block, widget_type = block) {
		const dialog_class = get_dialog_constructor(widget_type);
		let block_name = block+'_name';
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
						on_edit: () => this.on_edit(this.block_widget)
					},
					new: true
				});
				this.block_widget.customize(this.options);
				this.wrapper.setAttribute(block_name, this.block_widget.label || this.block_widget.onboarding_name);
				this.new_block_widget = this.block_widget.get_config();
				this.add_tune_button();
			},
		});

		if (!this.readOnly && this.data && !this.data[block_name]) {
			this.dialog.make();
		}
	}

	make(block, block_name) {
		let block_data = this.config.page_data['onboardings'].items.find(obj => {
			return obj.label == block_name;
		});
		if (!block_data) return false;
		this.wrapper.innerHTML = '';
		block_data.in_customize_mode = !this.readOnly;
		this.block_widget = frappe.widget.make_widget({
			container: this.wrapper,
			widget_type: 'onboarding',
			in_customize_mode: block_data.in_customize_mode,
			options: {
				...this.options,
				on_delete: () => this.api.blocks.delete(),
				on_edit: () => this.on_edit(this.block_widget)
			},
			label: block_data.label,
			title: block_data.title || __("Let's Get Started"),
			subtitle: block_data.subtitle,
			steps: block_data.items,
			success: block_data.success,
			docs_url: block_data.docs_url,
			user_can_dismiss: block_data.user_can_dismiss,
		});
		this.wrapper.setAttribute(block+'_name', block_name);
		if (!this.readOnly) {
			this.block_widget.customize(this.options);
		}
		return true;
	}

	render() {
		this.wrapper = document.createElement('div');
		this.new('onboarding');

		if (this.data && this.data.onboarding_name) {
			let has_data = this.make('onboarding', this.data.onboarding_name);
			if (!has_data) return;
		}

		if (!this.readOnly) {
			this.add_tune_button();
		}
		$(this.wrapper).css("padding-bottom", "20px");
		return this.wrapper;
	}

	validate(savedData) {
		if (!savedData.onboarding_name) {
			return false;
		}

		return true;
	}

	save(blockContent) {
		return {
			onboarding_name: blockContent.getAttribute('onboarding_name'),
			col: this.get_col(),
			new: this.new_block_widget
		};
	}
}