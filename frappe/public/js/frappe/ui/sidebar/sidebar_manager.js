// A module's Sidebar, in the editor every navigation surface shares
// (`frappe.ui.ArrangementEditor`, which holds the layer switch, the sortables, the pool and the
// persistence). This is only what a Sidebar is: what its entries are, where its two layers live,
// and the fields a person may state about an entry -- which the dock has none of.
//
// It arranges the sidebar on screen. A Sidebar belongs to a module, and the module's name is the
// address of everything here: what is read, what is saved, what is reset. There is no picker for
// the same reason the dock has no app switcher -- you arrange the one you are looking at, and you
// reach another module's by going there.
//
// An entry is a `Sidebar Item`, named by its key. Unlike a dock entry it carries things a person
// can have an opinion about, and the overridable set is deliberately short: a label and an icon.
// A reference stores an opinion, never a copy -- store the whole body and one reorder would
// freeze the site's labels and the app's links forever, which is why `Custom Sidebar` narrows
// what it keeps and why this offers exactly the two fields it keeps.
//
// Section *membership* is not here; it is its own ticket. It rides through untouched: a reference
// row says nothing about `child`, so the base's membership is what resolves either way.

// What differs between a Sidebar's two layers, in one place. The extra entry over the dock's is
// `reset`: hiding everything is not how a sidebar layer is emptied, because an empty arrangement
// is a real thing to say here -- so Reset is an endpoint that drops the layer rather than a state
// the panes can be dragged into.
const SIDEBAR_LAYERS = {
	user: {
		read: "frappe.desk.doctype.custom_sidebar.custom_sidebar.get_user_sidebar_layer",
		save: "frappe.desk.doctype.custom_sidebar.custom_sidebar.save_sidebar_customization",
		reset: "frappe.desk.doctype.custom_sidebar.custom_sidebar.reset_user_sidebar",
		saved: () => __("Sidebar updated"),
	},
	site: {
		read: "frappe.desk.doctype.custom_sidebar.custom_sidebar.get_site_sidebar_layer",
		save: "frappe.desk.doctype.custom_sidebar.custom_sidebar.save_site_sidebar",
		reset: "frappe.desk.doctype.custom_sidebar.custom_sidebar.reset_site_sidebar",
		saved: () => __("Sidebar updated for everyone"),
	},
};

frappe.ui.SidebarManager = class SidebarManager extends frappe.ui.ArrangementEditor {
	get layers() {
		return SIDEBAR_LAYERS;
	}

	prepare() {
		// The sidebar on screen, which is the only one there is to arrange. The user menu doesn't
		// offer this when there is no module shown.
		this.module = frappe.app.sidebar.current_module;
	}

	title() {
		const sidebar = frappe.boot.module_sidebars[this.module] || {};
		return __("Manage {0} Sidebar", [sidebar.label || this.module]);
	}

	copy() {
		const below = this.layer === "site" ? __("what the apps ship") : __("the site's");
		return {
			selection_head: __("On the sidebar"),
			selection_sub: __("Drag to reorder. Use the pencil to rename or re-icon an entry."),
			reset_title: __("Drop this arrangement and go back to {0}.", [below]),
			reset_confirm:
				this.layer === "site"
					? __(
							"Put this sidebar back to what the apps ship? Everything the site has arranged here is dropped, for everyone."
					  )
					: __(
							"Put this sidebar back to the site's arrangement? Everything you have arranged here is dropped."
					  ),
			reset_done:
				this.layer === "site"
					? __("Sidebar reset for everyone")
					: __("Sidebar reset to the site's"),
			selection_empty: __("Drag entries here"),
			pool_head: __("Hidden"),
			pool_sub: __("Drag one over to put it back on the sidebar."),
			pool_empty: __("Nothing is hidden"),
			load_error: __("Could not load the sidebar. Please try again."),
		};
	}

	// The layer as it arranges the sidebar, hidden entries kept -- see `layer_arrangement`. This
	// is where the starting-point rule is honoured here: an unarranged layer answers with
	// the layer below it as that layer renders, so opening this and saving unchanged writes back
	// what was already there rather than un-hiding what somebody below hid.
	async read() {
		const items = await frappe.xcall(this.layer_config.read, { module: this.module });

		this.entries = new Map(items.map((item) => [item.key, item]));
		this.selection = items.filter((item) => !item.hidden).map((item) => item.key);
	}

	// A section header is an entry like any other -- it is arranged, hidden and relabelled the
	// same way -- but it leads nowhere, and an editor that let you drag one about without saying
	// so would look like it had lost your links.
	is_section(key) {
		return this.entries.get(key).type === "Section Break";
	}

	item_extras(key) {
		return this.is_section(key) ? `<span class="ws-item-chip">${__("section")}</span>` : "";
	}

	// Members of a section sit under it on the sidebar, so they sit under it here.
	item_classes(key) {
		return this.entries.get(key).child ? "ws-item-child" : "";
	}

	decorate_selection_item($el, key) {
		let $edit = $(
			`<button class="ws-item-edit" title="${__("Rename")}">${frappe.utils.icon(
				"pencil",
				"sm"
			)}</button>`
		);
		$edit.on("click", () => this.edit_entry(key));
		$el.append($edit);
	}

	// The per-entry fields, which are the whole of what this editor has that the dock's does not.
	// Two of them, and no more: a label and an icon are what a `Custom Sidebar` reference row may
	// carry, so anything else offered here would be offered and then dropped on save.
	edit_entry(key) {
		const entry = this.entries.get(key);
		const dialog = new frappe.ui.Dialog({
			title: __("Rename Entry"),
			fields: [
				{
					fieldtype: "Data",
					fieldname: "label",
					label: __("Label"),
					default: entry.label,
					reqd: 1,
				},
				// A section header draws no icon on the sidebar, so it is not offered one here.
				...(this.is_section(key)
					? []
					: [
							{
								fieldtype: "Icon",
								fieldname: "icon",
								label: __("Icon"),
								default: entry.icon,
								// An empty field is no opinion, not "no icon" -- see
								// `overrides()`. Say so, or clearing it reads as broken.
								description: __("Leave it empty to keep the one it inherits."),
							},
					  ]),
			],
			primary_action_label: __("Done"),
			primary_action: (values) => {
				entry.label = values.label;
				if (!this.is_section(key)) entry.icon = values.icon || null;
				dialog.hide();
				this.render_panes();
			},
		});
		dialog.show();
	}

	// The whole ordered arrangement on screen, which is what this layer's save takes -- not a
	// delta. Each entry goes back as it came, plus its flag. Which of the values it carries is
	// an opinion and which was merely inherited is settled on the server against the layer
	// below, because that is the only place both sides of the comparison are known.
	save_args() {
		const rows = this.arranged_rows((key, hidden) => ({ ...this.entries.get(key), hidden }));

		return { module: this.module, items: JSON.stringify(rows) };
	}

	// A sidebar with nothing navigable left is not an arrangement, it is a locked door: the
	// module is dropped from the payload, and the dock entry, the desktop tile and the menu item
	// that opens this editor all go with it -- so the Reset that would undo it is out of reach.
	// Section headers do not count, which is the same rule `resolve_sidebar` drops a module by.
	//
	// Said rather than prevented by disabling Save, because "Save does nothing" is the one thing
	// worse than a refusal, and Reset is right there and is what this person probably meant.
	async save() {
		if (!this.loaded) return;
		this.sync_order();

		if (!this.selection.some((key) => !this.is_section(key))) {
			frappe.msgprint({
				title: __("Nothing left to navigate to"),
				message: __(
					"A sidebar needs at least one entry that leads somewhere. Put one back, or use Reset to drop this arrangement."
				),
				indicator: "orange",
			});
			return;
		}

		await super.save();
	}

	// Reset drops this layer outright -- a person back to the site's arrangement, a site back to
	// what the apps ship. It is a write of its own rather than a state of the panes, and it is
	// confirmed because it discards work rather than replacing it.
	reset() {
		if (!this.loaded) return;
		const copy = this.copy();

		frappe.confirm(copy.reset_confirm, async () => {
			this.apply(await frappe.xcall(this.layer_config.reset, { module: this.module }));
			this.dialog.hide();
			frappe.show_alert({ message: copy.reset_done, indicator: "green" });
		});
	}

	// Every write here answers with the desk state it invalidated, so the shell is redrawn in
	// place rather than reloaded.
	apply(payload) {
		if (payload.module_sidebars) frappe.boot.module_sidebars = payload.module_sidebars;
		if (payload.entity_module) frappe.boot.entity_module = payload.entity_module;

		const sidebar = frappe.app.sidebar;
		sidebar.all_sidebar_items = frappe.boot.module_sidebars;

		// A module can still go missing between opening this and saving -- somebody deleted its
		// last report, or the site layer hid it while this was open. `save` refuses to be the
		// cause of it, but it cannot be the only way it happens. There is no shell left to
		// redraw and the rest of the boot is stale in ways this payload does not carry, so
		// reload rather than render a module that is no longer there.
		if (!frappe.boot.module_sidebars[this.module]) {
			window.location.reload();
			return;
		}

		sidebar.setup(sidebar.current_module);
		sidebar.refresh();
	}
};
