import { createApp } from "vue";
import { createPinia } from "pinia";
import Designer from "./App.vue";
class PrintDesigner {
	constructor({ wrapper, print_format }) {
		this.$wrapper = $(wrapper);
		this.print_format = print_format;
		let appIcon = document.querySelector("a.navbar-brand.navbar-home").outerHTML;
		const app = createApp(Designer, { print_format_name: this.print_format, appIcon });
		app.use(createPinia());
		SetVueGlobals(app);
		app.mount(this.$wrapper.get(0));
	}
}

frappe.provide("frappe.ui");
frappe.ui.PrintDesigner = PrintDesigner;
export default PrintDesigner;
