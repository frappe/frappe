import Block from "./block.js";
export default class Shortcut extends Block {
	static get toolbox() {
		return {
			title: 'Shortcut',
			icon: frappe.utils.icon('shortcut', 'md')
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	constructor({ data, api, config, readOnly, block }) {
		super({ data, api, config, readOnly, block });
		this.col = this.data.col ? this.data.col : "4";
		this.allow_customization = !this.readOnly;
		this.options = {
			allow_sorting: this.allow_customization,
			allow_create: this.allow_customization,
			allow_delete: this.allow_customization,
			allow_hiding: false,
			allow_edit: true
		};
	}

	render() {
		this.wrapper = document.createElement('div');
		this.new('shortcut');

		if (this.data && this.data.shortcut_name) {
			let has_data = this.make('shortcut', __(this.data.shortcut_name));
			if (!has_data) return;
		}

		if (!this.readOnly) {
			this.add_tune_button();
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
			shortcut_name: this.wrapper.getAttribute('shortcut_name'),
			col: this.get_col(),
			new: this.new_block_widget
		};
	}
}