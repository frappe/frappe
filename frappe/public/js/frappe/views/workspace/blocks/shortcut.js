import Block from "./block.js";
export default class Shortcut extends Block {
	static get toolbox() {
		return {
			title: 'Shortcut',
			icon: '<svg height="18" width="18" viewBox="0 0 122.88 115.71"><path d="M116.56 3.69l-3.84 53.76-17.69-15c-19.5 8.72-29.96 23.99-30.51 43.77-17.95-26.98-7.46-50.4 12.46-65.97L64.96 3l51.6.69zM28.3 0h14.56v19.67H32.67c-4.17 0-7.96 1.71-10.72 4.47-2.75 2.75-4.46 6.55-4.46 10.72l-.03 46c.03 4.16 1.75 7.95 4.5 10.71 2.76 2.76 6.56 4.48 10.71 4.48h58.02c4.15 0 7.95-1.72 10.71-4.48 2.76-2.76 4.48-6.55 4.48-10.71V73.9h17.01v11.33c0 7.77-3.2 17.04-8.32 22.16-5.12 5.12-12.21 8.32-19.98 8.32H28.3c-7.77 0-14.86-3.2-19.98-8.32C3.19 102.26 0 95.18 0 87.41l.03-59.1c-.03-7.79 3.16-14.88 8.28-20C13.43 3.19 20.51 0 28.3 0z" fill-rule="evenodd" clip-rule="evenodd"/></svg>'
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

	save(blockContent) {
		return {
			shortcut_name: blockContent.getAttribute('shortcut_name'),
			col: this.get_col(),
			new: this.new_block_widget
		};
	}
}