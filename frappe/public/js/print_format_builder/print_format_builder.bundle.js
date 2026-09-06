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
		this.page.set_primary_action(__("Save & Apply"), () => {
			this.$component.$store.save_changes();
		});

		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+s",
			action: () => this.$component.$store.save_changes(),
			description: __("Save & Apply Print Format"),
			page: this.page,
		});
		// shown only while a draft exists — see the has_draft watch below
		let $discard_btn = this.page.add_button(__("Discard Draft"), () => {
			frappe.confirm(
				__("Discard your unapplied changes and go back to what this format prints?"),
				() => this.$component.$store.discard_draft()
			);
		});
		let $preview_btn = this.page.add_action_icon(
			"eye",
			() => this.$component.toggle_preview(),
			"",
			__("Show Preview")
		);
		this.page.add_action_icon(
			"settings",
			() => this.$component.open_print_settings(),
			"",
			__("Print Settings")
		);
		this.page.add_action_icon(
			"file-pen",
			() => frappe.set_route("Form", "Print Format", this.print_format),
			"",
			__("Edit Print Format")
		);
		// Every menu entry left is a mobile-only mirror of a custom action button, so on
		// wide screens the ⋯ would open an empty dropdown
		this.page.menu_btn_group.addClass("hidden-xl");

		let app = createApp(PrintFormatBuilderComponent, { print_format_name: print_format });
		SetVueGlobals(app);
		this.app = app;
		this.$component = app.mount(this.$wrapper.get(0));

		// the indicator only speaks up when something is pending — a format whose
		// edits are live needs no badge
		watch(
			() => this.$component.$store.save_status,
			(status) => {
				if (status.value === "saving") this.page.set_indicator(__("Saving…"), "gray");
				else if (status.value === "failed")
					this.page.set_indicator(__("Save failed"), "red");
				else if (status.value === "draft") this.page.set_indicator(__("Draft"), "orange");
				else this.page.clear_indicator();
			},
			{ deep: true, immediate: true }
		);

		watch(
			() => this.$component.$store.has_draft,
			(has_draft) => $discard_btn.toggle(!!has_draft.value),
			{ deep: true, immediate: true }
		);

		watch(
			() => this.$component.show_preview,
			(value) => {
				// the icon is the only affordance, so its tooltip carries the state.
				// bootstrap caches the initial title in data-original-title, so set both
				const label = value ? __("Hide Preview") : __("Show Preview");
				$preview_btn.attr("title", label).attr("data-original-title", label);
			}
		);
	}

	destroy() {
		this.app?.unmount();
	}
}

frappe.provide("frappe.ui");
frappe.ui.PrintFormatBuilder = PrintFormatBuilder;
export default PrintFormatBuilder;
