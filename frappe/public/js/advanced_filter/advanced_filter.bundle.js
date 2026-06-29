// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
// License: MIT. See LICENSE

import { createApp } from "vue";
import AdvancedFilterComponent from "./AdvancedFilter.vue";

/**
 * Launches the advanced filter builder inside a Desk dialog.
 *
 * Usage (typically from the filter popover):
 *
 *   frappe.require("advanced_filter.bundle.js").then(() => {
 *     new frappe.ui.AdvancedFilter({
 *       doctype,
 *       parent_doctype,
 *       filters,          // current simple filters [[dt, fn, cond, val], ...]
 *       filter_tree,      // existing advanced tree, if any
 *       on_apply(tree) {},
 *       on_clear() {},
 *     });
 *   });
 */
class AdvancedFilter {
	constructor(opts) {
		this.opts = opts || {};
		this.make_dialog();
		this.mount();
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Advanced Filters"),
			size: "large",
			// `static`: a click on the backdrop must not discard a filter being built.
			static: true,
			// vertically centered
			centered: true,
		});
		// `static` hides the close button by default; keep it so the dialog is still
		// dismissible via the X (and the Cancel action) - only outside-clicks are ignored.
		this.dialog.get_close_btn().show();
		// Let the modal (not an inner container) absorb height so the field picker's
		// autocomplete dropdown is never clipped.
		this.dialog.$wrapper.find(".modal-body").css("overflow", "visible");
		this.dialog.$body.empty();
		this.$root = $('<div class="advanced-filter-root"></div>').appendTo(this.dialog.$body);
		this.dialog.show();
	}

	mount() {
		const app = createApp(AdvancedFilterComponent, {
			doctype: this.opts.doctype,
			parentDoctype: this.opts.parent_doctype,
			filters: this.opts.filters || [],
			filterTree: this.opts.filter_tree || null,
			onApply: (tree) => {
				this.opts.on_apply && this.opts.on_apply(tree);
				this.dialog.hide();
			},
			onClear: () => {
				this.opts.on_clear && this.opts.on_clear();
				this.dialog.hide();
			},
			onClose: () => this.dialog.hide(),
		});

		SetVueGlobals(app);
		this.app = app;
		this.vm = app.mount(this.$root.get(0));

		// Tear the Vue app down when the dialog closes so controls are disposed.
		this.dialog.onhide = () => {
			try {
				this.app.unmount();
			} catch (e) {
				// already unmounted
			}
		};
	}
}

frappe.provide("frappe.ui");
frappe.ui.AdvancedFilter = AdvancedFilter;
export default AdvancedFilter;
