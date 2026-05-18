import { createPopper } from "@popperjs/core";
frappe.provide("frappe.ui");
/**
 * Sidebar Card is used to render a card with a close button. It is used to show cards in the sidebar, tooltip on form descriptions and billing banners etc.
 *
 * @param {string} title - Title of the card
 * @param {string} message - Message to be shown in the card
 * @param {HTMLElement} parent - Parent element to which the card will be appended
 * @param {HTMLElement} trigger - Element on which the card will be triggered
 * @param {string} [icon="info"] - Icon to be shown in the card
 * @param {boolean} [hide_icon] - If true, does not show the icon in the card
 * @param {boolean} [close_button] - Whether to show the close button or not
 * @param {boolean} [popper] - Whether to use popper for positioning the card
 * @param {boolean} [outline] - Whether to show the card with outline or not
 * @param {string} [primary_action_label] - Label for the primary action button
 * @param {Function} [primary_action] - Function to be called when the primary action button is clicked
 * @param {string} [primary_button_alignment] - Alignment for the primary action button (left or right)
 * @param {string} [dismiss_it_for] - If set, it will dismiss the card for the specified duration (minute, hour, day, week) when the close button is clicked
 * @param {string} [dismiss_key="card_next_show_time"] - Key to be used in localStorage for storing the dismiss time
 * @param {Object} [styles] - Custom styles to be applied to the card, passed as an object with CSS variable names as keys and their values as values
 */
frappe.ui.SidebarCard = class SidebarCard {
	constructor(opts) {
		Object.assign(this, opts);
		this.alignment_style_map = {
			right: "flex-end",
			left: "flex-start",
		};
		this.dismiss_intervals = {
			minute: 60 * 1000,
			hour: 60 * 60 * 1000,
			day: 24 * 60 * 60 * 1000,
			week: 7 * 24 * 60 * 60 * 1000,
		};
		this.make(opts);
		this.setup();
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
		if (!this.primary_action_label) {
			this.card.css("gap", "0px");
		}
		if (this.dismiss_it_for) {
			const next_time_for_show = localStorage.getItem(this.get_dismiss_key());
			if (next_time_for_show && Date.now() < Number(next_time_for_show)) {
				this.hide();
				return;
			}
		}
		if (this.popper) {
			this.popper = createPopper($(this.trigger).get(0), $(this.parent).get(0), {
				placement: "auto",
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
		if (this.outline) {
			this.card.addClass("card-outline");
			this.card.removeClass("px-2 py-2");
		}
		this.card.prependTo(this.parent);
		this.set_button_alignment();
		if (!this.popper) this.show();
	}
	setup() {
		this.setup_primary_action();
		this.setup_close_button();
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
		this.card.removeClass("d-inline-flex");
		this.card.addClass("hidden");
	}
	show() {
		this.display = true;
		this.parent.attr("data-show", "");
		this.popper && this.popper.update();
		this.card.addClass("d-inline-flex");
		this.card.removeClass("hidden");
	}
	get_dismiss_key() {
		return this.dismiss_key || "card_next_show_time";
	}
	setup_primary_action() {
		const me = this;
		this.card.find(".sidebar-card-button").on("click", function (event) {
			event.preventDefault();
			me.primary_action(event);
		});
	}
	setup_close_button() {
		const me = this;
		if (this.close_button) {
			this.card.find(".close-button").on("click", function (event) {
				event.preventDefault();
				if (me.dismiss_it_for) {
					let next_show_time = Date.now() + me.dismiss_intervals[me.dismiss_it_for];

					localStorage.setItem(me.get_dismiss_key(), next_show_time);
				}
				me.toggle();
			});
		}
	}
	set_styles() {
		if (this.styles) {
			const $root = $(":root");
			for (const [variable, value] of Object.entries(this.styles)) {
				$root.css(`--${variable}`, value);
			}
		}
	}
	set_button_alignment() {
		if (this.primary_button_alignment) {
			this.card
				.find(".sidebar-card-actions")
				.css("justifyContent", this.alignment_style_map[this.primary_button_alignment]);
		}
	}
};
