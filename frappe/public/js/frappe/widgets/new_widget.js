import get_dialog_constructor from "./widget_dialog.js";

export default class NewWidget {
	constructor(opts) {
		Object.assign(this, opts);
		this.make();
	}

	customize() {
		return;
	}

	make() {
		this.make_widget();
		this.widget.appendTo(this.container);
		this.setup_events();
	}

	get_title() {
		// DO NOT REMOVE: Comment to load translation
		// __("New Chart") __("New Shortcut") __("New Number Card")
		let title = `New ${frappe.model.unscrub(this.type)}`;
		return __(title);
	}

	make_widget() {
		const new_widget_class = `new-${frappe.scrub(
			frappe.model.unscrub(this.type),
			"-"
		)}-widget`;
		this.widget = $(`<div class="widget new-widget ${new_widget_class}">
				+ ${this.get_title()}
			</div>`);
		this.body = this.widget;
	}

	setup_events() {
		this.widget.on("click", () => {
			if (!this.custom_dialog) {
				this.open_dialog();
			} else {
				this.custom_dialog();
			}
		});
	}

	open_dialog() {
		const dialog_class = get_dialog_constructor(this.type);

		this.dialog = new dialog_class({
			label: this.label,
			type: this.type,
			values: false,
			default_values: this.default_values,
			primary_action: this.on_create,
		});

		this.dialog.make();
	}

	delete() {
		this.widget.remove();
	}
}
