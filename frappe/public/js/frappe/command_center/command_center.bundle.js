import { createApp } from "vue";
import { createPinia } from "pinia";
import { watch } from "vue";
import CommandCenterComponent from "./CommandCenter.vue";
class CommandCenter {
	constructor() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Command Center"),
			animate: false,
			static: true,
		});
		this.currentAction = null;
		this.wrapper = this.dialog.body;
		this.dialog.show();
		let app = createApp(CommandCenterComponent, {
			dialog: this.dialog,
		});
		SetVueGlobals(app);
		app.use(createPinia());
		app.mount(this.wrapper);
	}
}

frappe.provide("frappe.ui");
frappe.ui.CommandCenter = CommandCenter;
export default CommandCenter;
