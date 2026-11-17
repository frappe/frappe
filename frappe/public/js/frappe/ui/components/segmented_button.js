frappe.provide("frappe.ui");

/**
 * @typedef {Object} SegmentedButtonOpts
 * @property {string} [label] Text of the main button.
 * @property {string} [icon] Lucide icon name shown before the main label.
 * @property {"solid"|"subtle"|"outline"|"ghost"} [variant="subtle"] Shared by both segments.
 * @property {"xs"|"sm"|"md"|"lg"} [size="sm"] Shared by both segments.
 * @property {"gray"|"red"} [theme="gray"] Shared by both segments.
 * @property {function} [onclick] The main button's action — the same contract as frappe.ui.button.
 * @property {Array|function} options Rows of the menu the chevron opens — see MenuItem in menu.js.
 * @property {string} [menu_title] Accessible name of the chevron. Defaults to "More Options".
 * @property {"start"|"center"|"end"} [align="end"] How the menu lines up under the button.
 * @property {boolean} [sheet_on_mobile=false] On a phone, open the rows in a frappe.ui.BottomSheet instead.
 */

/**
 * A main button with a chevron segment beside it that opens a menu of related
 * actions (a split button). The main button works exactly like
 * frappe.ui.button; the chevron is a frappe.ui.Dropdown trigger.
 * @example
 * new frappe.ui.SegmentedButton({
 *     label: __("Add Invoice"),
 *     icon: "plus",
 *     variant: "solid",
 *     onclick: () => frappe.new_doc("Sales Invoice"),
 *     options: [
 *         { label: __("Import"), icon: "import", onclick: () => import_invoices() },
 *     ],
 * });
 */
frappe.ui.SegmentedButton = class SegmentedButton {
	/** @param {SegmentedButtonOpts} opts */
	constructor(opts = {}) {
		this.opts = opts;
		const shared = { variant: opts.variant, size: opts.size, theme: opts.theme };

		this.$wrapper = $('<div class="es-segmented-button" role="group"></div>');
		this.$button = frappe.ui
			.button({ ...shared, label: opts.label, icon: opts.icon, onclick: opts.onclick })
			.appendTo(this.$wrapper);
		this.$menu_button = frappe.ui
			.button({
				...shared,
				icon: "chevron-down",
				title: opts.menu_title || __("More Options"),
			})
			.appendTo(this.$wrapper);

		this.dropdown = new frappe.ui.Dropdown({
			trigger: this.$menu_button,
			options: opts.options,
			align: opts.align || "end",
			sheet_on_mobile: opts.sheet_on_mobile,
		});

		this.$wrapper.data("es-segmented-button", this);
	}

	/** Swap the menu rows; takes effect on the next open. */
	set_options(options) {
		this.dropdown.set_options(options);
	}

	destroy() {
		this.dropdown.destroy();
	}
};

/**
 * Convenience form: build a SegmentedButton and return its element. The
 * instance is on `.data("es-segmented-button")`.
 * @param {SegmentedButtonOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.segmented_button = function (opts = {}) {
	return new frappe.ui.SegmentedButton(opts).$wrapper;
};

export default frappe.ui.SegmentedButton;
