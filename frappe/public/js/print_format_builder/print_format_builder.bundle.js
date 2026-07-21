import { createApp, watch } from "vue";
import PrintFormatBuilderComponent from "./PrintFormatBuilder.vue";
import "./inspector.css";
import "../../../templates/print_format/print_format_doc.css";

class PrintFormatBuilder {
	constructor({ wrapper, page, print_format }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.print_format = print_format;

		this.page.clear_actions();
		this.page.clear_icons();
		this.page.clear_custom_actions();

		this.page.set_title(this.print_format);
		this.page.set_primary_action(__("Save"), () => {
			this.$component.$store.save_changes();
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+s",
			action: () => this.$component.$store.save_changes(),
			description: __("Save Print Format"),
			page: this.page,
		});
		let $reset_changes_btn = this.page.add_button(__("Reset Changes"), () =>
			this.$component.$store.reset_changes()
		);
		this.page.add_menu_item(__("Print Settings"), () => {
			this.$component.open_print_settings();
		});
		this.page.add_menu_item(__("Edit Print Format"), () => {
			frappe.set_route("Form", "Print Format", this.print_format);
		});
		this.page.add_menu_item(__("Change Print Format"), () => {
			frappe.set_route("print-format-builder");
		});

		let app = createApp(PrintFormatBuilderComponent, { print_format_name: print_format });
		SetVueGlobals(app);
		this.app = app;
		this.$component = app.mount(this.$wrapper.get(0));

		watch(
			() => this.$component.$store.dirty,
			(dirty) => {
				if (dirty.value) {
					this.page.set_indicator(__("Not Saved"), "orange");
					$reset_changes_btn.show();
				} else {
					this.page.clear_indicator();
					$reset_changes_btn.hide();
				}
			},
			{ deep: true }
		);
	}

	destroy() {
		this.app?.unmount();
	}
}

frappe.provide("frappe.ui");
frappe.ui.PrintFormatBuilder = PrintFormatBuilder;
export default PrintFormatBuilder;
