import FormBuilderComponent from "./FormBuilder.vue";
import { getStore } from "./store";

class FormBuilder {
	constructor({ wrapper, page, doctype }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.doctype = frappe.router.routes[doctype].doctype;

		this.page.clear_actions();
		this.page.clear_custom_actions();
		this.page.set_title(__("Form Builder: {0}", [this.doctype]));

		let $reset_changes_btn = this.page.add_button(__("Reset Changes"), () =>
			this.$component.$store.reset_changes()
		);

		this.page.add_menu_item(__("Go to {0} Doctype", [this.doctype]), () => {
			frappe.set_route("Form", "DocType", this.doctype);
		});

		let $vm = new Vue({
			el: this.$wrapper.get(0),
			render: (h) =>
				h(FormBuilderComponent, {
					props: {
						doctype: this.doctype,
					},
				}),
		});
		this.$component = $vm.$children[0];
		let store = getStore(this.doctype);
		store.$watch("dirty", (value) => {
			if (value) {
				this.page.set_indicator("Not Saved", "orange");
				$reset_changes_btn.show();
			} else {
				this.page.clear_indicator();
				$reset_changes_btn.hide();
			}
		});
	}
}

frappe.provide("frappe.ui");
frappe.ui.FormBuilder = FormBuilder;
export default FormBuilder;
