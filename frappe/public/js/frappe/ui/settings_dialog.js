import "./dialog";

frappe.provide("frappe.ui");

/**
 * Controller for a single settings panel. Both `render(panel)` and every
 * `action.click(panel)` receive the same instance, so actions can drive the
 * rendering — e.g. a "Create" action can swap the header and redraw the body,
 * then `panel.refresh()` returns to the default view.
 *   panel.body                     // jQuery content wrapper (build into this)
 *   panel.set_view({ title, description, actions, fields, render })
 *                                  // atomically swap the whole view (header +
 *                                  // actions + body); the unit a stateful panel
 *                                  // moves between (e.g. list ➜ form ➜ back)
 *   panel.set_header({ title, description, actions })   // header only
 *   panel.add_fields(fields)       // low-level: mount a FieldGroup into the body
 *   panel.refresh()                // reset to the tab's default view (the item)
 *   panel.dialog                   // the SettingsDialog instance
 *
 * When the item declares `fields`, the panel builds a `frappe.ui.FieldGroup`
 * (the same form primitive Dialog uses) into its body, so an action can read
 * inputs with `panel.get_values()` — null if a mandatory field is empty:
 *
 *   panel.get_values()             // validated values dict, or null
 *   panel.get_value(fieldname)     // single field value
 *   panel.set_values({ ... })      // populate fields (returns a Promise)
 *   panel.fieldgroup               // the underlying FieldGroup
 */
frappe.ui.SettingsDialogPanel = class SettingsDialogPanel {
	constructor(dialog, item) {
		this.dialog = dialog;
		this.item = item;
		this.fieldgroup = null;

		this.$el = $('<div class="settings-dialog-panel"></div>');
		this.$header = $(`
			<div class="settings-dialog-panel-header hide">
				<div class="settings-dialog-panel-heading"></div>
				<div class="settings-dialog-panel-actions"></div>
			</div>
		`).appendTo(this.$el);
		this.$body = $('<div class="settings-dialog-panel-body"></div>').appendTo(this.$el);
		// `body` is the public handle consumers render into.
		this.body = this.$body;
	}

	set_header({ title, description, actions } = {}) {
		const $heading = this.$header.find(".settings-dialog-panel-heading").empty();
		const $actions = this.$header.find(".settings-dialog-panel-actions").empty();

		if (title) {
			$('<div class="settings-dialog-panel-title"></div>').text(title).appendTo($heading);
		}
		if (description) {
			$('<div class="settings-dialog-panel-description"></div>')
				.text(description)
				.appendTo($heading);
		}
		(actions || []).forEach((action) => $actions.append(this.make_action(action)));

		const has_header = Boolean(title || description || (actions && actions.length));
		this.$header.toggleClass("hide", !has_header);
		return this;
	}

	make_action(action) {
		return frappe.ui.button({
			label: action.label || "",
			icon: action.icon,
			variant: action.variant,
			css_class: action.class,
			// `this` and the first argument are both the panel, so actions can mutate it.
			onclick: action.click && (() => action.click.call(this, this)),
		});
	}

	add_fields(fields) {
		// Low-level: mount a FieldGroup into the (already-cleared) body.
		this.fieldgroup = new frappe.ui.FieldGroup({
			fields,
			body: this.$body.get(0),
		});
		this.fieldgroup.make();
		return this.fieldgroup;
	}

	set_view({ title, description, actions, fields, render } = {}) {
		// Atomically swap the whole view: header (title/description/actions), then
		// body (fields and/or custom render). Mounting actions + fields together
		// guarantees an action's get_values() reads the form mounted alongside it.
		this.set_header({ title, description, actions });

		this.$body.empty();
		this.fieldgroup = null;
		if (fields && fields.length) this.add_fields(fields);
		render && render(this);

		return this;
	}

	refresh() {
		return this.set_view(this.item);
	}

	get_values(...args) {
		return this.fieldgroup ? this.fieldgroup.get_values(...args) : {};
	}

	get_value(fieldname) {
		return this.fieldgroup ? this.fieldgroup.get_value(fieldname) : undefined;
	}

	set_values(values) {
		return this.fieldgroup ? this.fieldgroup.set_values(values) : Promise.resolve();
	}

	get_field(fieldname) {
		return this.fieldgroup ? this.fieldgroup.get_field(fieldname) : undefined;
	}
};

/**
 * A reusable two-pane settings dialog: a grouped vertical tab rail on the left
 * and lazily-rendered panels on the right. Extends `frappe.ui.Dialog` so it
 * reuses the full modal lifecycle (backdrop, show/hide, ESC, the open-dialog
 * stack) while replacing the standard header/body/footer with the settings
 * layout.
 *
 * The visual design mirrors the banking app's `settings-dialog.tsx` and binds
 * to the framework's existing Espresso tokens (`--surface-*`, `--ink-gray-*`).
 *
 * Usage:
 *
 *   const d = new frappe.ui.SettingsDialog({
 *       title: __("Settings"),
 *       default_tab: "preferences",
 *       tabs: [
 *           {
 *               group: __("Configuration"),
 *               items: [
 *                   {
 *                       id: "preferences",
 *                       label: __("Preferences"),
 *                       icon: "sliders-vertical", // sprite name (resolved via icon util)
 *                       // icon_html: "<svg…>"    // alternative: raw, TRUSTED markup only
 *                       // Declarative header sugar (optional):
 *                       title: __("Preferences"),
 *                       description: __("Manage your preferences"),
 *                       actions: [{ label: __("Save"), primary: true, click(panel) {} }],
 *                       render(panel) {
 *                           // build content into `panel.body`; call
 *                           // panel.set_header(...) / panel.refresh() for
 *                           // stateful, action-driven views.
 *                       },
 *                   },
 *               ],
 *           },
 *       ],
 *   });
 *   d.show();
 */
frappe.ui.SettingsDialog = class SettingsDialog extends frappe.ui.Dialog {
	constructor(opts) {
		super(
			Object.assign(
				{
					size: "extra-large",
				},
				opts
			)
		);
	}

	make() {
		// Build the standard modal shell + lifecycle, then repurpose it.
		super.make();

		this.tabs = this.tabs || [];
		// Flat lookup of every tab item by id, and a cache of panel controllers.
		this._items = {};
		this._panels = {};

		this.$wrapper.addClass("settings-dialog-wrapper");

		// Drop the standard title bar; each panel owns its own header (banking design).
		this.header.addClass("hide");

		// Replace the default body with the two-pane layout. Mount directly into
		// `.modal-body` (not `this.$body`, which is an extra unstyled wrapper) so the
		// flex height chain reaches the modal content and the panes fill the dialog.
		this.$body.addClass("hide");
		this.$message.addClass("hide");
		this.modal_body.addClass("settings-dialog-body");

		this.$layout = $(`
			<div class="settings-dialog">
				<div class="settings-dialog-sidebar"></div>
				<div class="settings-dialog-panels"></div>
			</div>
		`).appendTo(this.modal_body);

		this.$sidebar = this.$layout.find(".settings-dialog-sidebar");
		this.$panels = this.$layout.find(".settings-dialog-panels");

		this.render_sidebar();

		const default_tab = this.default_tab || this.first_tab_id();
		if (default_tab) this.activate(default_tab);
	}

	first_tab_id() {
		for (const group of this.tabs) {
			if (group.items && group.items.length) return group.items[0].id;
		}
		return null;
	}

	render_sidebar() {
		this.$sidebar.empty();

		this.tabs.forEach((group) => {
			const $group = $('<div class="settings-dialog-tab-group"></div>').appendTo(
				this.$sidebar
			);

			if (group.group) {
				$(`<div class="settings-dialog-group-header"><span></span></div>`)
					.find("span")
					.text(group.group)
					.end()
					.appendTo($group);
			}

			const $nav = $('<nav class="settings-dialog-tab-list"></nav>').appendTo($group);

			(group.items || []).forEach((item) => {
				this._items[item.id] = item;
				$nav.append(this.make_tab_item(item));
			});
		});
	}

	make_tab_item(item) {
		const $item = $(`
			<button type="button" class="settings-dialog-tab-item" data-tab-id="${frappe.utils.escape_html(
				item.id
			)}">
				<span class="settings-dialog-tab-item-content">
					<span class="settings-dialog-tab-icon"></span>
					<span class="settings-dialog-tab-label"></span>
				</span>
			</button>
		`);

		const $icon = $item.find(".settings-dialog-tab-icon");
		if (item.icon_html) {
			// Raw markup — only ever set developer-authored, trusted HTML here.
			// Never populate `icon_html` from a server response or user input.
			$icon.html(item.icon_html);
		} else if (item.icon) {
			// Sprite icon name, resolved (and escaped) through the icon util.
			$icon.html(frappe.utils.icon(item.icon, "sm"));
		} else {
			$icon.remove();
		}

		$item.find(".settings-dialog-tab-label").text(item.label || item.id);

		$item.on("click", () => this.activate(item.id));
		return $item;
	}

	activate(id) {
		const item = this._items[id];
		if (!item) return;

		this.active_tab = id;

		this.$sidebar.find(".settings-dialog-tab-item").each((i, el) => {
			$(el).toggleClass("active", $(el).data("tab-id") === id);
		});

		// Lazy: build the panel controller on first activation, then just toggle so
		// each panel keeps its own state across tab switches.
		if (!this._panels[id]) {
			const panel = new frappe.ui.SettingsDialogPanel(this, item);
			this._panels[id] = panel;
			this.$panels.append(panel.$el);
			panel.refresh();
		}

		Object.values(this._panels).forEach((p) => p.$el.addClass("hide"));
		this._panels[id].$el.removeClass("hide");

		item.on_activate && item.on_activate(this._panels[id]);
	}

	get_panel(id) {
		return this._panels[id];
	}

	reset(tabs, default_tab) {
		// Swap tabs without destroying the modal shell — clears panel state, rebuilds
		// the sidebar, and activates the new default tab.
		this.$panels.empty();
		this._items = {};
		this._panels = {};
		this.tabs = tabs;
		this.render_sidebar();
		const first = default_tab || this.first_tab_id();
		if (first) this.activate(first);
	}
};
