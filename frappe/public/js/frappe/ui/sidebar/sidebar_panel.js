frappe.provide("frappe.ui");

// Where every panel mounts. A sibling of .body-sidebar rather than a child of it:
// the container's width is the placeholder's width, which is already 220px when the
// sidebar is expanded and 0 when it is collapsed or on mobile. So `left: 100%` puts
// the panel in the right place in all three states with no per-state overrides.
const MOUNT_SELECTOR = ".body-sidebar-container";

/**
 * @typedef {Object} SidebarPanelOpts
 * @property {string} name Key the panel is opened by: frappe.ui.sidebar_panels.toggle(name).
 * @property {string} title Heading shown at the top of the panel.
 * @property {string} [trigger_selector] Matches the button(s) that open it. Clicks inside
 *     one do not count as "outside", and aria-expanded is kept in sync on all of them.
 *     Notifications has two triggers, the sidebar bell and the dock bell, and they share
 *     a class, so one selector covers both.
 * @property {string} [css_class] Extra classes on the panel element.
 * @property {function} [on_open] Called after the panel is shown.
 * @property {function} [on_close] Called after it is hidden.
 */

/**
 * A full-height drawer that slides out beside the body sidebar. Non-modal: the page
 * underneath stays live, which is what separates it from a dialog.
 *
 * The panel owns its own frame (position, size, surface, header, close button) and
 * hands the caller an empty $body to fill. Opening and closing are not the panel's
 * job either, they belong to frappe.ui.sidebar_panels, so that only one panel can be
 * open and every panel dismisses the same way.
 *
 * @example
 * this.panel = new frappe.ui.SidebarPanel({
 *     name: "background-tasks",
 *     title: __("Background Tasks"),
 *     trigger_selector: ".sidebar-background-tasks",
 *     on_open: () => this.update_tasks(),
 * });
 * this.body = this.panel.$body;
 */
frappe.ui.SidebarPanel = class SidebarPanel {
	/** @param {SidebarPanelOpts} opts */
	constructor(opts = {}) {
		if (!opts.name) {
			throw new Error("frappe.ui.SidebarPanel: `name` is required");
		}
		this.name = opts.name;
		this.opts = opts;
		this.is_open = false;

		this.make();
		frappe.ui.sidebar_panels.register(this);
	}

	make() {
		const $mount = $(MOUNT_SELECTOR);
		if (!$mount.length) {
			// Not every desk page draws a body sidebar. Build the element anyway so the
			// caller still has a $body to write into, but leave it detached: an unmounted
			// panel is inert rather than broken.
			console.warn(
				`frappe.ui.SidebarPanel: no ${MOUNT_SELECTOR} to mount "${this.name}" in`
			);
		}

		this.$panel = $(`<div class="sidebar-panel hidden"></div>`)
			.addClass(`sidebar-panel-${this.name}`)
			.addClass(this.opts.css_class || "");

		const header = frappe.ui.panel_header({
			title: this.opts.title,
			on_close: () => this.hide(),
		});
		this.$header = header.$header;
		this.$title = header.$title;
		this.$items = header.$items;
		this.$actions = header.$actions;

		this.$body = $(`<div class="sidebar-panel-body"></div>`);

		this.$panel.append(this.$header).append(this.$body);
		$mount.append(this.$panel);
	}

	show() {
		frappe.ui.sidebar_panels.show(this.name);
	}

	hide() {
		frappe.ui.sidebar_panels.hide(this.name);
	}

	toggle() {
		frappe.ui.sidebar_panels.toggle(this.name);
	}

	/** Called by the registry. Use show()/hide() instead so exclusivity is honoured. */
	_show() {
		if (this.is_open) return;

		// Remember what had focus so close() can hand it back, the way the popover host
		// does. Usually this is the trigger that was just clicked.
		this.previously_focused = document.activeElement;

		this.$panel.removeClass("hidden");
		this.is_open = true;
		this.sync_trigger_state();

		// On mobile the sidebar is an overlay covering the screen, so it has to get out
		// of the way for the panel to be visible at all.
		if (frappe.is_mobile()) {
			$(MOUNT_SELECTOR).removeClass("expanded");
		}

		this.opts.on_open?.();
	}

	/** Called by the registry. Use show()/hide() instead so exclusivity is honoured. */
	_hide() {
		if (!this.is_open) return;

		this.$panel.addClass("hidden");
		this.is_open = false;
		this.sync_trigger_state();

		// Only take focus back if it is still inside the panel we just closed; moving it
		// otherwise would yank the caret out from wherever the user has gone since.
		if (
			this.previously_focused?.isConnected &&
			!document.activeElement?.closest?.(".sidebar-panel")
		) {
			this.previously_focused.focus?.();
		}
		this.previously_focused = null;

		this.opts.on_close?.();
	}

	sync_trigger_state() {
		if (!this.opts.trigger_selector) return;
		$(this.opts.trigger_selector).attr("aria-expanded", String(this.is_open));
	}

	/** True when the click landed on a trigger for this panel, or inside the panel itself. */
	owns_event(e) {
		const $target = $(e.target);
		if ($target.closest(this.$panel).length) return true;
		if (this.opts.trigger_selector && $target.closest(this.opts.trigger_selector).length) {
			return true;
		}
		return false;
	}
};

/**
 * Keeps the panels and decides which one is open.
 *
 * Dismissal lives here rather than in each panel because every rule it enforces is
 * global: only one panel open at a time, a click outside closes it, Escape closes it,
 * navigating away closes it. Spread across the panels those rules were duplicated and
 * had drifted apart.
 *
 * The document-level listeners are bound only while something is open, so an app with
 * no panel showing pays nothing per click or keystroke.
 */
frappe.ui.sidebar_panels = new (class SidebarPanelRegistry {
	constructor() {
		this.panels = {};
		this.open_panel = null;
		this.dismissal_bound = false;

		this.on_document_click = (e) => {
			if (!this.open_panel?.owns_event(e)) this.close_all();
		};
		// The desk-wide Escape channel (see keyboard.js), not a raw keydown, so an open
		// dialog or grid row still gets first refusal on the key.
		this.on_escape = () => this.close_all();

		$(document).on("page-change", () => this.close_all());
	}

	register(panel) {
		if (this.panels[panel.name]) {
			console.warn(`frappe.ui.sidebar_panels: replacing existing panel "${panel.name}"`);
			this.panels[panel.name].$panel.remove();
		}
		this.panels[panel.name] = panel;
	}

	get(name) {
		return this.panels[name];
	}

	show(name) {
		const panel = this.get(name);
		if (!panel) {
			console.warn(`frappe.ui.sidebar_panels: no panel named "${name}"`);
			return;
		}
		if (this.open_panel && this.open_panel !== panel) {
			this.open_panel._hide();
		}
		this.open_panel = panel;
		panel._show();
		this.bind_dismissal();
	}

	hide(name) {
		const panel = this.get(name);
		if (!panel?.is_open) return;
		panel._hide();
		if (this.open_panel === panel) this.open_panel = null;
		this.unbind_dismissal();
	}

	toggle(name) {
		if (this.get(name)?.is_open) {
			this.hide(name);
		} else {
			this.show(name);
		}
	}

	close_all() {
		if (this.open_panel) this.hide(this.open_panel.name);
	}

	bind_dismissal() {
		if (this.dismissal_bound) return;
		// Capture, not bubble. This binds from inside the trigger's own click handler, and
		// document's bubble phase has not run yet for that click -- a bubble listener would
		// see the opening click and close the panel again straight away. Document's capture
		// phase is already past, so a capturing listener does not.
		document.addEventListener("click", this.on_document_click, true);
		$(document).on("escape", this.on_escape);
		this.dismissal_bound = true;
	}

	unbind_dismissal() {
		if (!this.dismissal_bound) return;
		document.removeEventListener("click", this.on_document_click, true);
		$(document).off("escape", this.on_escape);
		this.dismissal_bound = false;
	}
})();
