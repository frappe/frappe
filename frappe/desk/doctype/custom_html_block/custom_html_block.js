// Copyright (c) 2023, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Custom HTML Block", {
	refresh(frm) {
		render_custom_html_block(frm);
	},
});

function render_custom_html_block(frm) {
	let wrapper = frm.fields_dict["preview"].wrapper;
	wrapper.classList.add("mb-3");

	let random_id = "custom-block-" + frappe.utils.get_random(5).toLowerCase();

	class CustomBlock extends HTMLElement {
		constructor() {
			super();

			// html
			let div = document.createElement("div");
			div.innerHTML = frappe.dom.remove_script_and_style(frm.doc.html);

			// css
			let style = document.createElement("style");
			style.textContent = frm.doc.style;

			// javascript
			let script = document.createElement("script");
			script.textContent = `
				(function() {
					let cname = ${JSON.stringify(random_id)};
					let root_element = document.querySelector(cname).shadowRoot;
					${frm.doc.script}
				})();
			`;

			this.attachShadow({ mode: "open" });
			this.shadowRoot?.appendChild(div);
			this.shadowRoot?.appendChild(style);
			this.shadowRoot?.appendChild(script);
		}
	}

	if (!customElements.get(random_id)) {
		customElements.define(random_id, CustomBlock);
	}
	wrapper.innerHTML = `<${random_id}></${random_id}>`;
}
