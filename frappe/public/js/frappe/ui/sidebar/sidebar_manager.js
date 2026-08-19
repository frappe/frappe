// A module's Sidebar, in the editor every navigation surface shares
// (`frappe.ui.ArrangementEditor`, which holds the layer switch, the list, the eye and the
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
// Section *membership* is here, and it is the drop that states it: an entry dragged out from
// under a section stops being a member, and one dragged back under it is one again. Membership is
// stored as arrangement rather than as an opinion -- every row a layer holds states it, the way
// every row states its order and whether it is hidden -- because a `Check` has no way to spell
// "no opinion" apart from "not a member", and the whole arrangement is written on every save.

// What differs between a Sidebar's two layers, in one place. The extra entry over the dock's is
// `reset`: hiding everything is not how a sidebar layer is emptied, because an empty arrangement
// is a real thing to say here -- so Reset is an endpoint that drops the layer rather than a state
// the list can be put into.
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

// The third reset, which belongs to no layer: it takes every layer off, so the module goes back
// to using the `Sidebar` its app ships. Kept out of `SIDEBAR_LAYERS` because that map answers
// "where does the layer I am editing read, save and reset", and this one is not about a layer.
const RESET_TO_STANDARD = "frappe.desk.doctype.custom_sidebar.custom_sidebar.reset_to_standard";

// What an added entry may point at. The `Sidebar Item.link_type` set, in full and in its order --
// an entry this offers that the column cannot hold would be offered and then dropped on save.
const LINK_TYPES = ["DocType", "Page", "Report", "Workspace", "Dashboard", "URL"];

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
		return __("Manage {0} Sidebar", [this.title_of_module()]);
	}

	// What this module is called on screen -- its `Sidebar`'s title, which an app or a layer may
	// have relabelled, falling back to the module's own name.
	title_of_module() {
		return (frappe.boot.module_sidebars[this.module] || {}).label || this.module;
	}

	// Offered to whoever may curate for everyone, and to nobody else: it discards the site's
	// arrangement *and* every person's own. Placed on the dialog rather than beside the pane's
	// Reset, because the two are not neighbours -- one drops the layer you are editing, this one
	// ends every claim on the module.
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

	// The layer as it arranges the sidebar, hidden entries kept -- see `layer_arrangement`. This
	// is where the starting-point rule is honoured here: an unarranged layer answers with
	// the layer below it as that layer renders, so opening this and saving unchanged writes back
	// what was already there rather than un-hiding what somebody below hid.
	async read() {
		const items = await frappe.xcall(this.layer_config.read, { module: this.module });

		this.entries = new Map(items.map((item) => [item.key, item]));
		// The layer's own order, hidden entries kept in place: this read answers with every
		// entry, so a hidden one is a row here like any other and sits where it was left rather
		// than at the end.
		this.arrange(
			items.map((item) => item.key),
			items.filter((item) => item.hidden).map((item) => item.key)
		);
	}

	// A `Custom Sidebar` row can carry an item of its own, so a sidebar layer adds as well as
	// orders and hides -- a link, or a section to drop links into. This is the only surface
	// where that is true.
	can_add() {
		return true;
	}

	// The same identity the server works out (`item_key`): a row that leads somewhere is named
	// by the columns it already has, and one that leads nowhere -- a section -- by its type and
	// its label. Worked out here only so an entry has a key between being added and being saved:
	// everything read back carries the server's own, which is a hash of those same two columns.
	item_key(item) {
		if (!this.is_linked(item)) return [item.type || "", item.label || ""].join("|");

		return ["type", "link_type", "link_to", "url"].map((field) => item[field] || "").join("|");
	}

	// Whether an entry leads anywhere. A section does not, which is the whole of what makes it
	// a different kind of row -- see `is_linked` on the server, which asks the same question of
	// the same two columns.
	is_linked(entry) {
		return !!(entry.link_to || entry.url);
	}

	add() {
		if (!this.loaded) return;

		const dialog = new frappe.ui.Dialog({
			title: __("Add to the Sidebar"),
			fields: [
				// A section is the other kind of row a sidebar holds: it leads nowhere and names
				// the run of entries under it. Offered here rather than behind a button of its
				// own, because the two are one decision -- what am I putting on the sidebar --
				// and everything below this field is what a link needs and a section does not.
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
					// store one (`drop_private_workspaces`), so it is not offerable.
					get_query: () =>
						dialog.get_value("link_type") === "Workspace"
							? { filters: { public: 1 } }
							: {},
					// The label is what the entry is called, not what it points at, but the two
					// agree far more often than not -- so it is filled in and left editable.
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
				// A section header draws no icon on the sidebar, so it is not offered one --
				// the same rule the rename dialog keeps.
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

	// Put the entry on the sidebar, or say why it is already there. Answers whether the dialog
	// is done with.
	//
	// An entry the arrangement already holds is not added twice: two rows sharing an identity
	// *are* one item, and the merge would keep the first and drop the second -- so a second one
	// is not a new entry, it is the one that is already there. If it is sitting in Hidden, this
	// is almost certainly what the person meant, so it goes back on.
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
		// It went on the end, so the end is where it landed, and where an entry lands is what
		// says which section it is in. That is what makes "add a section, then add what goes in
		// it" work with nothing else to do: the section goes on last, and the next entry added
		// is dropped directly under it.
		this.on_move(entry.key);
		this.render_panes();
		return true;
	}

	// An entry *this* layer added comes off by being deleted, not hidden. Nothing below holds
	// it, so a row saying "I add this, and I hide it" says nothing at all -- and somebody who
	// adds an entry and changes their mind means gone. An entry a layer below added is a
	// reference from here, so it hides like any other.
	hide(key) {
		if (!this.entries.get(key)?.added) {
			return super.hide(key);
		}

		this.entries.delete(key);
		this.order = this.order.filter((k) => k !== key);
	}

	// Which is why an added entry carries a cross rather than an eye: the control has to say
	// what it does, and there is no showing one again once it is gone.
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

	// A section header is an entry like any other -- it is arranged, hidden and relabelled the
	// same way -- but it leads nowhere, and an editor that let you drag one about without saying
	// so would look like it had lost your links.
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

	// Where an entry lands is what says which section it is in: the row above it is either the
	// section header itself or another of that section's members, and either way the entry has
	// joined them. Dropped under a top-level entry, or at the top of the list, it belongs to no
	// section and stops being a member.
	//
	// Only the entry that moved is re-read. Membership is stored per row, so re-deriving it for
	// rows nobody touched would rewrite what the layers below said about them -- a top-level
	// entry sitting after a section is a real arrangement, and opening this and saving unchanged
	// has to leave it exactly as it was.
	//
	// A section header is never a member of one: the desk draws a single level of nesting, so a
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

	// The sidebar draws a label and nothing beside it -- `sidebar_item.html` renders no leading
	// icon -- so neither does the editor. Drawing one here would put a mark on every row that
	// nobody will ever see on the surface itself, and the preview would be answering wrongly.
	entry_icon() {
		return "";
	}

	// A section header draws as a header in the preview rather than as a link, the way the
	// sidebar itself draws it -- a preview that made one look like an entry would be answering
	// the question wrongly.
	preview_item(key) {
		if (!this.is_section(key)) return super.preview_item(key);

		return $(
			`<div class="ws-preview-section">${frappe.utils.escape_html(
				this.entries.get(key).label
			)}</div>`
		);
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
				if (!this.rename(key, values.label)) {
					frappe.show_alert({
						message: __("There is already a section called {0}.", [
							frappe.utils.escape_html(values.label),
						]),
						indicator: "orange",
					});
					return;
				}

				// asked of the entry rather than of `key`, which a rename may just have changed
				if (entry.type !== "Section Break") entry.icon = values.icon || null;
				dialog.hide();
				this.render_panes();
			},
		});
		dialog.show();
	}

	// Relabel an entry, moving it if the label is what names it.
	//
	// A section this layer added *is* the item rather than a reference to one, and an item that
	// leads nowhere is named by its type and its label -- so renaming one renames its identity,
	// and the list has to carry it across rather than leave it filed under a name it no longer
	// has. A rename onto a name another section already has is refused: two sections of one name
	// are one section to the merge, and the second would silently disappear on save.
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

	// The whole ordered arrangement on screen, which is what this layer's save takes -- not a
	// delta. Each entry goes back as it came, plus its flag. Which of the values it carries is
	// an opinion and which was merely inherited is settled on the server against the layer
	// below, because that is the only place both sides of the comparison are known.
	save_args() {
		const rows = this.arranged_rows((key, hidden) => this.stored_row(key, hidden));

		return { module: this.module, items: JSON.stringify(rows) };
	}

	// One row as it goes back: the entry as it came, plus where the arrangement leaves it.
	//
	// An added row that leads nowhere goes back without its key. A section is named by a hash of
	// its type and its label, and the server is what hashes it (`unlinked_key`) -- sending the
	// editor's own spelling of that identity would store a second name for the same thing, and a
	// base section of the same label would stop being the same section.
	stored_row(key, hidden) {
		const row = { ...this.entries.get(key), hidden };
		if (row.added && !this.is_linked(row)) row.key = null;

		return row;
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
