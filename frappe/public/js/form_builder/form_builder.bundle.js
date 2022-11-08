import { createApp, watchEffect } from "vue";
import { createPinia } from "pinia";
import { useStore } from "./store";
import FormBuilderComponent from "./components/FormBuilder.vue";

class FormBuilder {
	constructor({ wrapper, page, doctype, customize }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.doctype = doctype;
		this.customize = customize;

		// set page title
		this.page.set_title(__("Form Builder: {0}", [this.doctype]));

		this.setup_page_actions();
		this.setup_app();
		this.watch_changes();
	}

	async setup_page_actions() {
		// clear actions
		this.page.clear_actions();
		this.page.clear_menu();
		this.page.clear_custom_actions();

		// setup page actions
		this.primary_btn = this.page.set_primary_action(__("Save"), () =>
			this.store.save_changes()
		);

		this.customize_form_btn = this.page.add_button(__("Switch to Customize Form"), () => {
			frappe.set_route("form-builder", this.doctype, "customize");
		});
		this.doctype_form_btn = this.page.add_button(__("Switch to Doctype Form"), () => {
			frappe.set_route("form-builder", this.doctype);
		});

		this.reset_changes_btn = this.page.add_button(__("Reset Changes"), () => {
			this.store.reset_changes();
		});

		this.go_to_doctype_btn = this.page.add_menu_item(__("Go to Doctype"), () =>
			frappe.set_route("Form", "DocType", this.doctype)
		);
		this.go_to_customize_form_btn = this.page.add_menu_item(__("Go to Customize Form"), () =>
			frappe.set_route("Form", "Customize Form", {
				doc_type: this.doctype,
			})
		);
	}

	setup_app() {
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
	}

	watch_changes() {
		watchEffect(() => {
			if (this.store.dirty) {
				this.page.set_indicator(__("Not Saved"), "orange");
				this.reset_changes_btn.show();
			} else {
				this.page.clear_indicator();
				this.reset_changes_btn.hide();
			}

			// toggle doctype / customize form btn based on url
			this.customize_form_btn.toggle(!this.store.is_customize_form);
			this.doctype_form_btn.toggle(this.store.is_customize_form);

			// hide customize form & Go to customize form btn
			if (
				this.store.doc &&
				(this.store.doc.custom || this.store.doc.issingle,
				in_list(frappe.model.core_doctypes_list, this.doctype) ||
					!in_list(frappe.boot.active_domains, this.store.doc.restrict_to_domain))
			) {
				this.customize_form_btn.hide();
				this.go_to_customize_form_btn.hide();
			}

			// toggle primary btn and show indicator based on read_only state
			this.primary_btn.toggle(!this.store.read_only);
			this.store.read_only && this.page.set_indicator(__("Read Only"), "orange");
		});
	}
}

frappe.provide("frappe.ui");
frappe.ui.FormBuilder = FormBuilder;
export default FormBuilder;
