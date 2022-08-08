import PrintFormatBuilderComponent from "./PrintFormatBuilder.vue";
import { getStore } from "./store";

class PrintFormatBuilder {
	constructor({ wrapper, page, print_format }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.print_format = print_format;

		this.page.clear_actions();
		this.page.clear_icons();
		this.page.clear_custom_actions();

		this.page.set_title(__("Editing {0}", [this.print_format]));
		this.page.set_primary_action(__("Save"), () => {
			this.$component.$store.save_changes();
		});
		let $toggle_preview_btn = this.page.add_button(__("Show Preview"), () => {
			this.$component.toggle_preview();
		});
		let $reset_changes_btn = this.page.add_button(__("Reset Changes"), () =>
			this.$component.$store.reset_changes()
		);
		this.page.add_menu_item(__("Edit Print Format"), () => {
			frappe.set_route("Form", "Print Format", this.print_format);
		});
		this.page.add_menu_item(__("Change Print Format"), () => {
			frappe.set_route("print-format-builder-beta");
		});

		let $vm = new Vue({
			el: this.$wrapper.get(0),
			render: (h) =>
				h(PrintFormatBuilderComponent, {
					props: {
						print_format_name: print_format,
					},
				}),
		});
		this.$component = $vm.$children[0];
		let store = getStore(print_format);
		store.$watch("dirty", (value) => {
			if (value) {
				this.page.set_indicator("Not Saved", "orange");
				$toggle_preview_btn.hide();
				$reset_changes_btn.show();
			} else {
				this.page.clear_indicator();
				$toggle_preview_btn.show();
				$reset_changes_btn.hide();
			}
		});
		this.$component.$watch("show_preview", (value) => {
			$toggle_preview_btn.text(value ? __("Hide Preview") : __("Show Preview"));
		});
	}
}

frappe.provide("frappe.ui");
frappe.ui.PrintFormatBuilder = PrintFormatBuilder;
export default PrintFormatBuilder;
