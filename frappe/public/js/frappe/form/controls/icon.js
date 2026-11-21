import Picker from "../../icon_picker/icon_picker";

frappe.ui.form.ControlIcon = class ControlIcon extends frappe.ui.form.ControlData {
	make_input() {
		this.df.placeholder = __(this.df.placeholder) || __("Choose an icon");
		super.make_input();
		this.get_all_icons();
		this.make_icon_input();
	}

	get_all_icons() {
		frappe.symbols = [];
		$("#all-symbols > svg > symbol[id]").each(function () {
			this.id.includes("icon-") && frappe.symbols.push(this.id.replace("icon-", ""));
		});
	}

	get_icon_sections() {
		// Custom Icons live in the same sprite, so split them back out by name
		let custom_names = new Set((frappe.boot.custom_icons || []).map((icon) => icon.name));
		let custom = frappe.symbols.filter((icon) => custom_names.has(icon));
		if (!custom.length) {
			return [{ icons: frappe.symbols }];
		}

		return [
			{ label: __("Custom"), icons: custom },
			{
				// the bundled set is named, not called "Icons", since every section holds icons
				label: "Lucide",
				icons: frappe.symbols.filter((icon) => !custom_names.has(icon)),
			},
		];
	}

	make_icon_input() {
		let picker_wrapper = $("<div>");
		this.picker = new Picker({
			parent: picker_wrapper,
			icon: this.get_icon(),
			sections: this.get_icon_sections(),
			include_emoji: this.df.options == "Emojis",
		});

		this.picker.on_change = (icon) => {
			this.set_value(icon);
		};

		if (!this.selected_icon) {
			this.selected_icon = $(
				`<div class="selected-icon">${frappe.utils.icon("folder", "sm")}</div>`
			);
			this.selected_icon.insertAfter(this.$input);
		}

		let namespace = `icon-popover-${frappe.dom.get_unique_id()}`;
		const $trigger = this.$wrapper.find(".selected-icon").parent();
		this.popover = new frappe.ui.Popover({
			trigger: $trigger,
			content: () => picker_wrapper[0],
			css_class: "icon-picker-popover",
			on_open: () => {
				this.$input.trigger("focus");
				this.picker.refresh();
				$(window).on(`hashchange.${namespace}`, () => this.popover.close());
			},
			on_close: () => $(window).off(`hashchange.${namespace}`),
		});
		$trigger.on("click", (e) => e.stopPropagation());
	}

	refresh() {
		super.refresh();
		let icon = this.get_icon();
		if (this.picker && this.picker.icon !== icon) {
			this.picker.icon = icon;
			this.picker.refresh();
		}
	}

	set_formatted_input(value) {
		super.set_formatted_input(value);
		this.$input.val(value);
		this.selected_icon.find("use").attr("href", "#icon-" + (value || "folder"));
		this.selected_icon.toggleClass("no-value", !value);
	}

	get_icon() {
		return this.get_value() || "folder";
	}
};
