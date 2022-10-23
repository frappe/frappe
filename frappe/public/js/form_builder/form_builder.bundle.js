import { createApp, watch } from "vue";
import { createPinia } from "pinia";
import { useStore } from "./store";
import FormBuilderComponent from "./components/FormBuilder.vue";

class FormBuilder {
	constructor({ wrapper, page, doctype, customize }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.doctype = doctype;
		this.customize = customize;

		// clear actions
		this.page.clear_actions();
		this.page.clear_menu();
		this.page.clear_custom_actions();

		// set page title
		this.page.set_title(__("Form Builder: {0}", [this.doctype]));

		// setup page actions
		this.page.set_primary_action(__("Save"), () => this.store.save_changes());

		this.customize_form_btn = this.page.add_button(__("Switch to Customize Form"), () => {
			frappe.set_route("form-builder", this.doctype, "customize");
		});
		this.doctype_form_btn = this.page.add_button(__("Switch to Doctype Form"), () => {
			frappe.set_route("form-builder", this.doctype);
		});

		this.reset_changes_btn = this.page.add_button(__("Reset Changes"), () => {
			this.store.reset_changes();
		});

		this.page.add_menu_item(__("Go to Doctype"), () =>
			frappe.set_route("Form", "DocType", this.doctype)
		);
		this.page.add_menu_item(__("Go to Customize Form"), () =>
			frappe.set_route("Form", "Customize Form", {
				doc_type: this.doctype,
			})
		);

		// create a pinia instance
		let pinia = createPinia();

		// create a vue instance
		let app = createApp(FormBuilderComponent);
		SetVueGlobals(app);
		app.use(pinia);

		// create a store
		this.store = useStore();
		this.store.doctype = this.doctype;
		this.store.is_customize_form = this.customize;

		// mount the app
		this.$form_builder = app.mount(this.$wrapper.get(0));

		// watch for changes
		watch(
			() => this.store.dirty,
			(dirty) => {
				if (dirty) {
					this.page.set_indicator("Not Saved", "orange");
					this.reset_changes_btn.show();
				} else {
					this.page.clear_indicator();
					this.reset_changes_btn.hide();
				}
			},
			{ immediate: true }
		);

		watch(
			() => this.store.is_customize_form,
			(value) => {
				this.customize_form_btn.toggle(!value);
				this.doctype_form_btn.toggle(value);
			},
			{ immediate: true }
		);
	}
}

frappe.provide("frappe.ui");
frappe.ui.FormBuilder = FormBuilder;
export default FormBuilder;
