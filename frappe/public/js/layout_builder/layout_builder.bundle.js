import { createApp } from "vue";
import { createPinia } from "pinia";
import { useLayoutBuilderStore } from "./store";
import LayoutBuilderComponent from "./components/LayoutBuilder.vue";

/**
 * DocType Layout visual builder.
 *
 * Usage (from doctype_layout.js):
 *   frappe.require("layout_builder.bundle.js").then(() => {
 *     frappe.layout_builder = new frappe.ui.LayoutBuilder({ wrapper, frm });
 *   });
 */
class LayoutBuilder {
	constructor({ wrapper, frm }) {
		this.$wrapper = $(wrapper);
		this.frm = frm;
		this._app = null;
		this.store = null;
		this._setup();
	}

	_setup() {
		const pinia = createPinia();
		const app = createApp(LayoutBuilderComponent);
		// expose frappe globals inside Vue (same pattern as FormBuilder)
		app.config.globalProperties.__ = window.__;
		app.config.globalProperties.frappe = window.frappe;
		app.config.globalProperties.is_touch_screen_device = () =>
			"ontouchstart" in window || navigator.maxTouchPoints > 0;
		app.use(pinia);
		this._app = app;
		this.store = useLayoutBuilderStore();
		this.store.init(this.frm);
		app.mount(this.$wrapper.get(0));
	}

	/** Call after frm.doc.fields changes (sync / after_save) */
	reload() {
		this.store?.reload();
	}

	destroy() {
		this._app?.unmount();
		this._app = null;
	}
}

frappe.provide("frappe.ui");
frappe.ui.LayoutBuilder = LayoutBuilder;
export default LayoutBuilder;
