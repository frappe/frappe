// A module's Sidebar, in the editor every navigation surface shares
// (`frappe.ui.ArrangementEditor`, which holds the layer switch, the list, the eye and the
// persistence). This file only describes what a Sidebar is: what its entries are, where its two
// layers live, and the fields a user may override on an entry, which the dock has none of.
//
// It arranges the sidebar on screen. A Sidebar belongs to a module, and the module's name
// addresses everything here: what is read, what is saved and what is reset. There is no picker,
// for the same reason the dock has no app switcher: you arrange the one you are looking at, and
// you reach another module's by going there.
//
// An entry is a `Sidebar Item`, named by its key. Unlike a dock entry it carries fields a user can
// override, and that set is short on purpose: a label and an icon. A reference stores overrides,
// never a copy. Storing the whole body would let one reorder freeze the site's labels and the
// app's links forever, which is why `Custom Sidebar` narrows what it keeps and why this offers
// exactly those two fields.
//
// Section membership is set here, by the drop: an entry dragged out from under a section stops
// being a member, and one dragged back under it becomes a member again. Membership is stored as
// arrangement rather than as an override, so every row a layer holds states it, the way every row
// states its order and whether it is hidden. A `Check` cannot express "no opinion" separately
// from "not a member", and the whole arrangement is written on every save.

// What differs between a Sidebar's two layers, in one place. The extra entry compared with the
// dock's is `reset`: hiding everything is not how a sidebar layer is emptied, because an empty
// arrangement is a meaningful state here. So Reset is an endpoint that drops the layer rather
// than a state the list can be put into.
const SIDEBAR_LAYERS = {
	user: {
		read: "frappe.desk.doctype.custom_sidebar.custom_sidebar.get_user_sidebar_layer",
		save: "frappe.desk.doctype.custom_sidebar.custom_sidebar.save_sidebar_customization",
		reset: "frappe.desk.doctype.custom_sidebar.custom_sidebar.reset_user_sidebar",
		label: () => __("Just for me"),
		saved: () => __("Sidebar updated"),
	},
	site: {
		read: "frappe.desk.doctype.custom_sidebar.custom_sidebar.get_site_sidebar_layer",
		save: "frappe.desk.doctype.custom_sidebar.custom_sidebar.save_site_sidebar",
		reset: "frappe.desk.doctype.custom_sidebar.custom_sidebar.reset_site_sidebar",
		label: () => __("For everyone"),
		condition: () => frappe.user.has_role("Workspace Manager"),
		saved: () => __("Sidebar updated for everyone"),
	},
};

// The third reset, which belongs to no layer: it removes every layer, so the module goes back to
// using the `Sidebar` its app ships. It is kept out of `SIDEBAR_LAYERS` because that map says
// where the layer being edited reads, saves and resets, and this is not about one layer.
const RESET_TO_STANDARD = "frappe.desk.doctype.custom_sidebar.custom_sidebar.reset_to_standard";

// What an added entry may point at: the full `Sidebar Item.link_type` set, in its own order. An
// option offered here that the column cannot hold would be dropped on save.
const LINK_TYPES = ["DocType", "Page", "Report", "Workspace", "Dashboard", "URL"];

frappe.ui.SidebarManager = class SidebarManager extends frappe.ui.ArrangementEditor {
	get layers() {
		return SIDEBAR_LAYERS;
	}

	prepare() {
		// The sidebar on screen, which is the only one to arrange. The user menu does not offer
		// this when no module is shown.
		//
		// There are two names, because a `Custom Sidebar` is anchored to a module while the desk
		// shows a shell. `shell` is what is on screen and what the payload is keyed by; `module`
		// is what every endpoint here takes. They are the same string unless the sidebar was
		// renamed, and the entry carries the module where they differ.
		this.shell = frappe.app.sidebar.current_module;
		this.module = frappe.app.sidebar.current_module_def();
	}

	title() {
		return __("Manage {0} Sidebar", [this.title_of_module()]);
	}

	// What the sidebar on screen is called: its `Sidebar`'s title, which an app or a layer may
	// have relabelled, falling back to the shell's own name.
	title_of_module() {
		return (frappe.boot.module_sidebars[this.shell] || {}).label || this.shell;
	}

	// Offered only to users who may curate for everyone, because it discards the site's
	// arrangement and every user's own. It sits on the dialog rather than beside the pane's
	// Reset, because the two do different things: one drops the layer you are editing, this one
	// removes every layer on the module.
	extra_actions() {
		return this.can_curate_site
			? {
					secondary_action_label: __("Reset to Standard"),
					secondary_action: () => this.reset_to_standard(),
			  }
			: {};
	}

	reset_to_standard() {
		if (!this.loaded) return;

		frappe.confirm(
			__(
				"Put <b>{0}</b> back to the sidebar its app ships? This removes the site's arrangement and every person's own, so nobody keeps a customization of this module.",
				[frappe.utils.escape_html(this.title_of_module())]
			),
			async () => {
				this.apply(await frappe.xcall(RESET_TO_STANDARD, { module: this.module }));
				this.dialog.hide();
				frappe.show_alert({
					message: __("{0} is back to standard", [
						frappe.utils.escape_html(this.title_of_module()),
					]),
					indicator: "green",
				});
			}
		);
	}

	copy() {
		const below = this.layer === "site" ? __("what the apps ship") : __("the site's");
		return {
			list_head: __("Entries"),
			add_label: __("Add"),
			list_sub: __(
				"Drag to reorder, and under a section to put an entry in it. The eye takes an entry off the sidebar; the pencil renames it."
			),
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
			list_empty: __("This module has nothing to arrange"),
			preview_head: __("Preview"),
			preview_sub: __("The sidebar as this arrangement leaves it."),
			preview_empty: __("Nothing on the sidebar"),
			load_error: __("Could not load the sidebar. Please try again."),
		};
	}

	// The layer as it arranges the sidebar, keeping hidden entries. See `layer_arrangement`. An
	// unarranged layer answers with the layer below it as that layer renders, so opening this and
	// saving unchanged writes back what was already there rather than un-hiding what a lower
	// layer hid.
	async read() {
		const items = await frappe.xcall(this.layer_config.read, { module: this.module });

		this.entries = new Map(items.map((item) => [item.key, item]));
		// The layer's own order, with hidden entries kept in place. This read returns every
		// entry, so a hidden one is an ordinary row here and stays where it was left rather than
		// moving to the end.
		this.arrange(
			items.map((item) => item.key),
			items.filter((item) => item.hidden).map((item) => item.key)
		);
	}

	// A `Custom Sidebar` row can carry an item of its own, so a sidebar layer can add as well as
	// order and hide: a link, or a section to drop links into. No other surface can do this.
	can_add() {
		return true;
	}

	// The same identity the server computes (`item_key`): a row that leads somewhere is named by
	// the columns it already has, and one that leads nowhere, such as a section, by its type and
	// label. It is computed here only so an entry has a key between being added and being saved.
	// Everything read back carries the server's own key, a hash of those same two columns.
	item_key(item) {
		if (!this.is_linked(item)) return [item.type || "", item.label || ""].join("|");

		return ["type", "link_type", "link_to", "url"].map((field) => item[field] || "").join("|");
	}

	// Whether an entry leads anywhere. A section does not, which is what makes it a different
	// kind of row. See `is_linked` on the server, which tests the same two columns.
	is_linked(entry) {
		return !!(entry.link_to || entry.url);
	}

	add() {
		if (!this.loaded) return;

		const dialog = new frappe.ui.Dialog({
			title: __("Add to the Sidebar"),
			fields: [
				// A section is the other kind of row a sidebar holds: it leads nowhere and names
				// the entries under it. It is offered here rather than behind its own button,
				// because both answer one question, what to put on the sidebar, and everything
				// below this field is what a link needs and a section does not.
				{
					fieldtype: "Select",
					fieldname: "kind",
					label: __("Kind"),
					options: [
						{ value: "Link", label: __("Link") },
						{ value: "Section", label: __("Section") },
					],
					default: "Link",
					reqd: 1,
				},
				{
					fieldtype: "Select",
					fieldname: "link_type",
					label: __("Links To"),
					options: LINK_TYPES,
					default: "DocType",
					depends_on: 'eval:doc.kind == "Link"',
					mandatory_depends_on: 'eval:doc.kind == "Link"',
				},
				{
					fieldtype: "Dynamic Link",
					fieldname: "link_to",
					label: __("Item"),
					options: "link_type",
					depends_on: 'eval:doc.kind == "Link" && doc.link_type != "URL"',
					mandatory_depends_on: 'eval:doc.kind == "Link" && doc.link_type != "URL"',
					// A private page's link is derived from the page itself and no layer may
					// store one (`drop_private_workspaces`), so it cannot be offered.
					get_query: () =>
						dialog.get_value("link_type") === "Workspace"
							? { filters: { public: 1 } }
							: {},
					// The label is what the entry is called rather than what it points at, but
					// the two usually match, so it is prefilled and left editable.
					change: () => {
						if (!dialog.get_value("label")) {
							dialog.set_value("label", dialog.get_value("link_to"));
						}
					},
				},
				{
					fieldtype: "Data",
					fieldname: "url",
					label: __("URL"),
					depends_on: 'eval:doc.kind == "Link" && doc.link_type == "URL"',
					mandatory_depends_on: 'eval:doc.kind == "Link" && doc.link_type == "URL"',
				},
				{ fieldtype: "Data", fieldname: "label", label: __("Label"), reqd: 1 },
				// A section header draws no icon on the sidebar, so it is not offered one. The
				// rename dialog follows the same rule.
				{
					fieldtype: "Icon",
					fieldname: "icon",
					label: __("Icon"),
					depends_on: 'eval:doc.kind == "Link"',
				},
			],
			primary_action_label: __("Add"),
			primary_action: (values) => {
				if (this.place(values)) dialog.hide();
			},
		});

		dialog.show();
	}

	// Put the entry on the sidebar, or report that it is already there. Returns whether the
	// dialog can close.
	//
	// An entry the arrangement already holds is not added twice: two rows sharing an identity are
	// one item, and the merge would keep the first and drop the second. If it is currently
	// hidden, un-hiding it is almost certainly what the user meant, so it goes back on.
	place(values) {
		const entry =
			values.kind === "Section"
				? { added: 1, type: "Section Break", label: values.label }
				: {
						added: 1,
						type: "Link",
						link_type: values.link_type,
						link_to: values.link_type === "URL" ? null : values.link_to,
						url: values.link_type === "URL" ? values.url : null,
						label: values.label,
						icon: values.icon || null,
				  };
		entry.key = this.item_key(entry);

		if (this.entries.has(entry.key)) {
			const shown = !this.hidden.has(entry.key);
			if (!shown) {
				this.hidden.delete(entry.key);
				this.render_panes();
			}
			frappe.show_alert({
				message: shown
					? __("{0} is already on the sidebar", [
							frappe.utils.escape_html(this.entries.get(entry.key).label),
					  ])
					: __("{0} was hidden, and is back on the sidebar", [
							frappe.utils.escape_html(this.entries.get(entry.key).label),
					  ]),
				indicator: "orange",
			});
			return shown ? false : true;
		}

		this.entries.set(entry.key, entry);
		this.order.push(entry.key);
		// It is appended, and where an entry lands is what decides which section it is in. That
		// is what makes "add a section, then add what goes in it" work with no extra step: the
		// section is appended last, and the next entry added lands directly under it.
		this.on_move(entry.key);
		this.render_panes();
		return true;
	}

	// An entry this layer added is removed by deleting it, not by hiding it. Nothing below holds
	// it, so a row that adds an entry and hides it says nothing, and a user who adds an entry and
	// changes their mind wants it gone. An entry added by a lower layer is a reference from here,
	// so it hides like any other.
	hide(key) {
		if (!this.entries.get(key)?.added) {
			return super.hide(key);
		}

		this.entries.delete(key);
		this.order = this.order.filter((k) => k !== key);
	}

	// That is why an added entry carries a cross rather than an eye: the control has to say what
	// it does, and a deleted entry cannot be shown again.
	visibility_button(key) {
		if (!this.entries.get(key)?.added) return super.visibility_button(key);

		let $remove = $(
			`<button class="ws-item-remove" title="${__("Remove")}">${frappe.utils.icon(
				"x",
				"sm"
			)}</button>`
		);
		$remove.on("click", () => this.toggle(key));
		return $remove;
	}

	// A section header is an entry like any other, arranged, hidden and relabelled the same way,
	// but it leads nowhere. An editor that let you drag one around without marking it as a
	// section would look like it had lost your links.
	is_section(key) {
		return this.entries.get(key).type === "Section Break";
	}

	item_extras(key) {
		return this.is_section(key) ? `<span class="ws-item-chip">${__("Section")}</span>` : "";
	}

	// Members of a section sit under it on the sidebar, so they sit under it here.
	item_classes(key) {
		return this.entries.get(key).child ? "ws-item-child" : "";
	}

	// Where an entry lands decides which section it is in: the row above it is either the section
	// header or another member of that section, and either way the entry joins them. Dropped
	// under a top-level entry, or at the top of the list, it belongs to no section.
	//
	// Only the entry that moved is re-read. Membership is stored per row, so re-deriving it for
	// untouched rows would overwrite what the lower layers said about them. A top-level entry
	// sitting after a section is a valid arrangement, and opening this and saving unchanged must
	// leave it as it was.
	//
	// A section header is never a member of a section: the desk draws one level of nesting, so a
	// `Section Break` marked `child` would claim a parent it never gets.
	on_move(key) {
		const entry = this.entries.get(key);
		if (!entry || this.is_section(key)) return;

		const above = this.order[this.order.indexOf(key) - 1];
		entry.child = above && (this.is_section(above) || this.entries.get(above).child) ? 1 : 0;
	}

	decorate_item($el, key) {
		let $edit = $(
			`<button class="ws-item-edit" title="${__("Rename")}">${frappe.utils.icon(
				"pencil",
				"sm"
			)}</button>`
		);
		$edit.on("click", () => this.edit_entry(key));
		$el.append($edit);
	}

	// The sidebar draws a label and nothing beside it, since `sidebar_item.html` renders no
	// leading icon, so the editor does the same. Drawing one here would show a mark on every row
	// that never appears on the sidebar itself, making the preview wrong.
	entry_icon() {
		return "";
	}

	// A section header draws as a header in the preview rather than as a link, the way the
	// sidebar draws it. A preview that made one look like an entry would be wrong.
	preview_item(key) {
		if (!this.is_section(key)) return super.preview_item(key);

		return $(
			`<div class="ws-preview-section">${frappe.utils.escape_html(
				this.entries.get(key).label
			)}</div>`
		);
	}

	// The per-entry fields, which are what this editor has and the dock's does not. There are two
	// and no more: a label and an icon are what a `Custom Sidebar` reference row may carry, so
	// anything else offered here would be dropped on save.
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
								// An empty field means no override, not "no icon" (see
								// `overrides()`). Say so, or clearing it looks broken.
								description: __("Leave it empty to keep the one it inherits."),
							},
					  ]),
			],
			primary_action_label: __("Done"),
			primary_action: (values) => {
				if (!this.rename(key, values.label)) {
					frappe.show_alert({
						message: __("There is already a section called {0}.", [
							frappe.utils.escape_html(values.label),
						]),
						indicator: "orange",
					});
					return;
				}

				// Read from the entry rather than `key`, which a rename may have just changed.
				if (entry.type !== "Section Break") entry.icon = values.icon || null;
				dialog.hide();
				this.render_panes();
			},
		});
		dialog.show();
	}

	// Relabel an entry, re-keying it if the label is what names it.
	//
	// A section this layer added is the item rather than a reference to one, and an item that
	// leads nowhere is named by its type and label, so renaming one changes its identity and the
	// list has to move it to the new key. Renaming onto a name another section already has is
	// refused, because the merge treats two sections of one name as one section and the second
	// would disappear on save.
	//
	// Everything else is named by where it points, so a relabel there is only a relabel.
	rename(key, label) {
		const entry = this.entries.get(key);
		const was = entry.label;
		entry.label = label;

		const fresh = this.item_key(entry);
		if (!entry.added || this.is_linked(entry) || fresh === key) return true;

		if (this.entries.has(fresh)) {
			entry.label = was;
			return false;
		}

		entry.key = fresh;
		this.entries.delete(key);
		this.entries.set(fresh, entry);
		this.order = this.order.map((k) => (k === key ? fresh : k));
		if (this.hidden.delete(key)) this.hidden.add(fresh);
		return true;
	}

	// The whole ordered arrangement on screen, which is what this layer's save takes, not a
	// delta. Each entry goes back as it came, plus its flag. Which values are overrides and which
	// were inherited is settled on the server against the layer below, which is the only place
	// both sides of the comparison are known.
	save_args() {
		const rows = this.arranged_rows((key, hidden) => this.stored_row(key, hidden));

		return { module: this.module, items: JSON.stringify(rows) };
	}

	// One row as it goes back: the entry as it came, plus where the arrangement leaves it.
	//
	// An added row that leads nowhere goes back without its key. A section is named by a hash of
	// its type and label, and the server computes that hash (`unlinked_key`). Sending the
	// editor's own version of that identity would store a second name for the same thing, and a
	// base section with the same label would no longer match it.
	stored_row(key, hidden) {
		const row = { ...this.entries.get(key), hidden };
		if (row.added && !this.is_linked(row)) row.key = null;

		return row;
	}

	// A sidebar with nothing navigable left locks the user out: the module is dropped from the
	// payload, and the dock entry, the desktop tile and the menu item that opens this editor go
	// with it, so the Reset that would undo it is unreachable. Section headers do not count,
	// which is the rule `resolve_sidebar` uses to drop a module.
	//
	// This is reported rather than prevented by disabling Save, because a Save that silently does
	// nothing is worse than a refusal, and Reset is next to it and is probably what the user
	// wanted.
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

	// Reset drops this layer outright: a user goes back to the site's arrangement, and the site
	// goes back to what the apps ship. It is its own write rather than a state of the panes, and
	// it is confirmed because it discards work rather than replacing it.
	reset() {
		if (!this.loaded) return;
		const copy = this.copy();

		frappe.confirm(copy.reset_confirm, async () => {
			this.apply(await frappe.xcall(this.layer_config.reset, { module: this.module }));
			this.dialog.hide();
			frappe.show_alert({ message: copy.reset_done, indicator: "green" });
		});
	}

	// Every write here returns the desk state it invalidated, so the shell is redrawn in place
	// rather than reloaded.
	apply(payload) {
		if (payload.module_sidebars) frappe.boot.module_sidebars = payload.module_sidebars;
		if (payload.entity_module) frappe.boot.entity_module = payload.entity_module;

		const sidebar = frappe.app.sidebar;
		sidebar.all_sidebar_items = frappe.boot.module_sidebars;

		// A module can disappear between opening this and saving, if someone deleted its last
		// report or the site layer hid it while this was open. `save` refuses to cause that, but
		// it is not the only way it happens. There is no shell left to redraw and the rest of the
		// boot is stale in ways this payload does not carry, so reload rather than render a
		// module that is gone.
		if (!frappe.boot.module_sidebars[this.shell]) {
			window.location.reload();
			return;
		}

		sidebar.setup(sidebar.current_module);
		sidebar.refresh();
	}
};
