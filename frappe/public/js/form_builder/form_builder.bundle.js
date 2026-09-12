import { createApp, watchEffect } from "vue";
import { createPinia } from "pinia";
import { useStore } from "./store";
import FormBuilderComponent from "./FormBuilder.vue";
import { registerGlobalComponents } from "./globals.js";

class FormBuilder {
	constructor({ wrapper, frm, doctype, customize, is_layout, is_web_form, tab_fieldname }) {
		this.$wrapper = $(wrapper);
		this.frm = frm;
		this.page = frm.page;
		this.doctype = doctype;
		this.customize = customize;
		this.is_layout = is_layout || false;
		this.is_web_form = is_web_form || false;
		// tab hosting the builder, older callers rely on the label fallback below
		this.tab_fieldname = tab_fieldname;
		this.read_only = false;

		this.init();
	}

	init(refresh) {
		// set page title (the frm already has one in layout/web form mode)
		if (!this.is_layout && !this.is_web_form) {
			this.page.set_title(__(this.doctype));
		}

		this.setup_page_actions();
		!refresh && this.setup_app();
		refresh && this.update_store();
		this.watch_changes();
	}

	get_host_tab() {
		return this.store.frm.layout?.tabs?.find((tab) =>
			this.tab_fieldname ? tab.df.fieldname === this.tab_fieldname : tab.label === "Form"
		);
	}

	setup_page_actions() {
		this.preview_btn?.remove();
		// web forms preview through the sidebar's "See on Website" link
		if (this.is_web_form) return;

		this.preview_btn = this.page.add_button(__("Show Preview"), () => {
			this.get_host_tab()?.set_active();
			this.store.preview = !this.store.preview;

			if (this.store.read_only && !this.read_only) {
				return;
			}

			this.store.read_only = this.store.preview;
			this.read_only = true;

			// toggle preview btn text
			this.preview_btn.text(this.store.preview ? __("Hide Preview") : __("Show Preview"));
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
		this.store.is_layout_form = this.is_layout;
		this.store.is_web_form = this.is_web_form;
		this.store.tab_fieldname = this.tab_fieldname;
		this.store.page = this.page;
		this.store.frm = this.frm;
	}

	watch_changes() {
		watchEffect(() => {
			if (this.store.dirty || this.frm.is_dirty()) {
				this.frm.dirty();
			} else {
				// redraw rather than clear, or the doc's own status (Published) goes too
				this.frm.toolbar.set_indicator();
			}

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
