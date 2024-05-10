import Widget from "./base_widget.js";

export default class CustomBlockWidget extends Widget {
	constructor(opts) {
		opts.shadow = true;
		super(opts);
	}

	get_config() {
		return {
			custom_block_name: this.custom_block_name,
			label: this.custom_block_name,
		};
	}

	refresh() {
		this.set_body();
		this.make_custom_block();
	}

	set_body() {
		this.widget.addClass("custom-block-widget-box");
		this.widget.addClass("full-width");
	}

	async make_custom_block() {
		await this.get_custom_block_data();
		this.body.empty();

		frappe.create_shadow_element(
			this.body[0],
			this.custom_block_doc.html,
			this.custom_block_doc.style,
			this.custom_block_doc.script
		);
	}

	async get_custom_block_data() {
		this.label = this.custom_block_name;
		let custom_block_doc = await frappe.model.with_doc(
			"Custom HTML Block",
			this.custom_block_name
		);
		this.custom_block_doc = custom_block_doc ? custom_block_doc : "";
	}
}
