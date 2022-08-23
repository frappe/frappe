import Block from "./block.js";
export default class Embed extends Block {
	  /**
   * @param {{data: EmbedData, config: EmbedConfig, api: object}}
   *   data — previously saved data
   *   config - user config for Tool
   *   api - Editor.js API
   *   readOnly - read-only mode flag
   */

	static get toolbox() {
		return {
			title: 'Embed',
			icon: frappe.utils.icon('list', 'sm')
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
			allow_edit: true,
			allow_resize: true,
			min_width: 4,
			max_widget_count: 2
		};
	}



	render() {
		this.wrapper = document.createElement('div');
		this.new('embed');

		if (this.data && this.data.embed_name) {
			let has_data = this.make('embed', this.data.embed_name);
			if (!has_data) return;
		}

		if (!this.readOnly) {
			$(this.wrapper).find('.widget').addClass('embed edit-mode');
			this.add_settings_button();
			this.add_new_block_button();
		}

		return this.wrapper;
	}

	validate(savedData) {
		if (!savedData.embed_name) {
			return false;
		}

		return true;
	}

	save() {
		return {
			embed_name: this.wrapper.getAttribute('embed_name'),
			col: this.get_col(),
			new: this.new_block_widget
		};
	}
}