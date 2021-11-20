import Block from "./block.js";
export default class Chart extends Block {
	static get toolbox() {
		return {
			title: 'Chart',
			icon: '<svg height="18" width="18" viewBox="0 0 512 512"><path d="M117.547 234.667H10.88c-5.888 0-10.667 4.779-10.667 10.667v256C.213 507.221 4.992 512 10.88 512h106.667c5.888 0 10.667-4.779 10.667-10.667v-256a10.657 10.657 0 00-10.667-10.666zM309.12 0H202.453c-5.888 0-10.667 4.779-10.667 10.667v490.667c0 5.888 4.779 10.667 10.667 10.667H309.12c5.888 0 10.667-4.779 10.667-10.667V10.667C319.787 4.779 315.008 0 309.12 0zM501.12 106.667H394.453c-5.888 0-10.667 4.779-10.667 10.667v384c0 5.888 4.779 10.667 10.667 10.667H501.12c5.888 0 10.667-4.779 10.667-10.667v-384c0-5.889-4.779-10.667-10.667-10.667z"/></svg>'
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
			max_widget_count: 2,
		};
	}

	render() {
		this.wrapper = document.createElement('div');
		this.new('chart');

		if (this.data && this.data.chart_name) {
			let has_data = this.make('chart', __(this.data.chart_name));
			if (!has_data) return;
		}

		if (!this.readOnly) {
			this.add_tune_button();
		}

		return this.wrapper;
	}

	validate(savedData) {
		if (!savedData.chart_name) {
			return false;
		}

		return true;
	}

	save(blockContent) {
		return {
			chart_name: blockContent.getAttribute('chart_name'),
			col: this.get_col(),
			new: this.new_block_widget
		};
	}
}