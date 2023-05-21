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

		this.random_id = "custom-block-" + frappe.utils.get_random(5).toLowerCase();

		let me = this;

		class CustomBlock extends HTMLElement {
			constructor() {
				super();

				// html
				let div = document.createElement("div");
				div.innerHTML = frappe.dom.remove_script_and_style(me.custom_block_doc.html);

				// css
				let style = document.createElement("style");
				style.textContent = me.custom_block_doc.style;

				// js
				let script = document.createElement("script");
				script.textContent = `
					(function() {
						let cname = ${JSON.stringify(me.random_id)};
						let root_element = document.querySelector(cname).shadowRoot;
						${me.custom_block_doc.script}
					})();
				`;

				this.attachShadow({ mode: "open" });
				this.shadowRoot?.appendChild(div);
				this.shadowRoot?.appendChild(style);
				this.shadowRoot?.appendChild(script);
			}
		}

		if (!customElements.get(this.random_id)) {
			customElements.define(this.random_id, CustomBlock);
		}

		this.body.append(`<${this.random_id}></${this.random_id}>`);
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
