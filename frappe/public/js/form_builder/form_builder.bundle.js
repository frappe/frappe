import { createApp, watchEffect } from "vue";
import { createPinia } from "pinia";
import { useStore } from "./store";
import FormBuilderComponent from "./FormBuilder.vue";
import { registerGlobalComponents } from "./globals.js";

class FormBuilder {
	constructor({ wrapper, frm, doctype, customize }) {
		this.$wrapper = $(wrapper);
		this.frm = frm;
		this.page = frm.page;
		this.doctype = doctype;
		this.customize = customize;
		this.read_only = false;

		this.init();
	}

	init(refresh) {
		// set page title
		this.page.set_title(__(this.doctype));

		this.setup_page_actions();
		!refresh && this.setup_app();
		refresh && this.update_store();
		this.watch_changes();
	}

	async setup_page_actions() {
		this.preview_btn = this.page.add_button(__("Show Preview"), () => {
			this.store.preview = !this.store.preview;

			if (this.store.read_only && !this.read_only) {
				return;
			}

			this.store.read_only = this.store.preview;
			this.read_only = true;
		});

		this.reset_changes_btn = this.page.add_button(__("Reset Changes"), () => {
			this.store.reset_changes();
		});
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
		this.update_store();

		// register global components
		registerGlobalComponents(app);

		// mount the app
		this.$form_builder = app.mount(this.$wrapper.get(0));
	}

	update_store() {
		this.store.doctype = this.doctype;
		this.store.is_customize_form = this.customize;
		this.store.page = this.page;
		this.store.frm = this.frm;
	}

	watch_changes() {
		watchEffect(() => {
			if (this.store.dirty) {
				this.reset_changes_btn.show();
				this.frm.dirty();
			} else {
				this.reset_changes_btn.hide();
			}

			// toggle preview btn text
			this.preview_btn.text(this.store.preview ? __("Hide Preview") : __("Show Preview"));
			if (this.store.read_only) {
				let message = this.store.preview ? __("Preview Mode") : __("Read Only");
				this.page.set_indicator(message, "orange");
			}
		});
	}
}

frappe.provide("frappe.ui");
frappe.ui.FormBuilder = FormBuilder;
export default FormBuilder;
