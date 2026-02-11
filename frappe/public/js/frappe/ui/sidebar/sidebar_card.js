import { createPopper } from "@popperjs/core";
frappe.provide("frappe.ui");

// icon, title, message, condition, primary_action_label, primary_action
frappe.ui.SidebarCard = class SidebarCard {
	constructor(opts) {
		Object.assign(this, opts);
		this.make(opts);
		this.setup();
		this.display = false;
		this.set_styles();
	}
	make() {
		if (!this.icon) {
			this.icon = "info";
		}
		this.card = $(
			frappe.render_template("sidebar_card", {
				card: this,
			})
		);
		if (this.popper) {
			this.popper = createPopper($(this.trigger).get(0), $(this.parent).get(0), {
				modifiers: [
					{
						name: "offset",
						options: {
							offset: [0, 8],
						},
					},
				],
			});
		}
		this.card.prependTo(this.parent);
	}
	setup() {
		this.setup_primary_action();
	}
	toggle() {
		if (this.display) {
			this.hide();
		} else {
			this.show();
		}
	}
	hide() {
		this.display = false;
		this.parent.removeAttr("data-show");
	}
	show() {
		this.display = true;
		this.parent.attr("data-show", "");
		this.popper.update();
	}
	setup_primary_action() {
		const me = this;
		this.card.find(".sidebar-card-button").on("click", function (event) {
			event.preventDefault();
			me.primary_action(event);
		});
	}
	set_styles() {
		if (this.styles) {
			const $root = $(":root");
			for (const [variable, value] of Object.entries(this.styles)) {
				$root.css(`--${variable}`, value);
			}
		}
	}
};
