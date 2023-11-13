import { createApp } from "vue";
import { createPinia } from "pinia";
import { useStore } from "./store";
import WorkflowBuilderComponent from "./WorkflowBuilder.vue";
import { registerGlobalComponents } from "./globals.js";

class WorkflowBuilder {
	constructor({ wrapper, page, workflow }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.workflow = workflow;

		this.page.set_indicator("Beta", "orange");

		this.init();
	}

	init() {
		// set page title
		this.page.set_title(__("Editing {0}", [this.workflow]));

		this.setup_page_actions();
		this.setup_app();
	}

	setup_page_actions() {
		// clear actions
		this.page.clear_actions();
		this.page.clear_menu();
		this.page.clear_custom_actions();

		// setup page actions
		this.primary_btn = this.page.set_primary_action(__("Save"), () =>
			this.store.save_changes()
		);

		this.reset_changes_btn = this.page.add_button(__("Reset Changes"), () => {
			this.store.reset_changes();
		});

		this.go_to_doctype_btn = this.page.add_menu_item(__("Go to Workflow"), () =>
			frappe.set_route("Form", "Workflow", this.workflow)
		);
	}

	setup_app() {
		// create a pinia instance
		let pinia = createPinia();

		// create a vue instance
		let app = createApp(WorkflowBuilderComponent, { workflow: this.workflow });
		SetVueGlobals(app);
		app.use(pinia);

		// create a store
		this.store = useStore();
		this.store.workflow_name = this.workflow;

		// register global components
		registerGlobalComponents(app);

		// mount the app
		this.$workflow_builder = app.mount(this.$wrapper.get(0));
	}
}

frappe.provide("frappe.ui");
frappe.ui.WorkflowBuilder = WorkflowBuilder;
export default WorkflowBuilder;
