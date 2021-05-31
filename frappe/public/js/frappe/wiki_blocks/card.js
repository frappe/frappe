import Block from "./block.js";
export default class Card extends Block {
	static get toolbox() {
		return {
			title: 'Card',
			icon: '<svg height="24" width="24" viewBox="0 0 24 24"><path d="M7 15h3a1 1 0 000-2H7a1 1 0 000 2zM19 5H5a3 3 0 00-3 3v9a3 3 0 003 3h14a3 3 0 003-3V8a3 3 0 00-3-3zm1 12a1 1 0 01-1 1H5a1 1 0 01-1-1v-6h16zm0-8H4V8a1 1 0 011-1h14a1 1 0 011 1z"/></svg>'
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	constructor(opts = {data, api, config, readOnly, block}) {
		super(opts)
		this.sections = {};
		this.col = this.data.col ? this.data.col : "12";
		this.pt = this.data.pt ? this.data.pt : "0";
		this.pr = this.data.pr ? this.data.pr : "0";
		this.pb = this.data.pb ? this.data.pb : "0";
		this.pl = this.data.pl ? this.data.pl : "0";
		this.allow_customization = !this.readOnly;
		this.options = {
			allow_sorting: this.allow_customization,
			allow_create: this.allow_customization,
			allow_delete: this.allow_customization,
			allow_hiding: false,
			allow_edit: true,
		};
	}

	render() {
		this.wrapper = document.createElement('div');
		this.new('card', 'links');

		if (this.data && this.data.card_name) {
			this.make('card', this.data.card_name, 'links');
		}

		if (!this.readOnly) {
			this.add_tune_button();
		}

		return this.wrapper;
	}

	validate(savedData) {
		if (!savedData.card_name) {
			return false;
		}

		return true;
	}

	save(blockContent) {
		return {
			card_name: blockContent.getAttribute('card_name'),
			col: this.get_col(),
			pt: this.get_padding("t"),
			pr: this.get_padding("r"),
			pb: this.get_padding("b"),
			pl: this.get_padding("l"),
			new: this.new_block_widget
		};
	}
}