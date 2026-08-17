// Dock manager -- arranges the dock (rail) for the app you're currently in: which of that app's
// entries appear on it, and in what order. Two draggable areas: the left is a preview of the dock
// (the chosen entries, reorderable); the right is the rest of the app's entries, ready to drag in.
//
// An entry is a typed pair -- a `Sidebar` (a module) or a `Workspace` (one of the app's own, or
// one a companion app pinned onto it) -- and both kinds are arranged the same way, because a pin
// is an entry on the dock rather than a fixture on it.
//
// It edits one of the dock's two stored layers at a time. Everyone has their own; a Workspace
// Manager can switch to the site's, which everyone sees and which each person's own is then
// applied on top of. That is the only thing the scope switch changes -- both layers are the same
// rows, arranged the same way, saved through endpoints that differ only in where they land.
//
// The two panes mean one thing in every scope and under every button: on the dock, or hidden. An
// untouched layer starts from the layer *below* it as that layer renders, so opening this and
// saving without changing anything can never un-hide what somebody below deliberately hid.
//
// On a developer's site it also authors the layer *below* both of those: "Ship This Order" writes
// the arrangement on screen into the app's own files, as the order it ships with. Not a third
// scope, because it is not a layer being edited -- the two layers rearrange the list an app ships,
// and this is that list. Same arrangement on screen, different place for it to land.
//
// Scoped to one app on purpose -- a dock belongs to an app, so there's nothing to choose between
// here and no app switcher. Modules in other apps are managed from those apps' docks.

// What differs between the two layers, in one place: where the arrangement is read from, where it
// is written back to, and what to say once it lands. Everything else -- the picker, the app slice,
// the shape of a saved row -- is the same work either way.
const DOCK_SCOPES = {
	user: {
		read: "frappe.desk.doctype.dock.dock.get_user_dock_layer",
		save: "frappe.desk.doctype.dock.dock.save_user_dock",
		saved: () => __("Dock updated"),
	},
	site: {
		read: "frappe.desk.doctype.dock.dock.get_site_dock_layer",
		save: "frappe.desk.doctype.dock.dock.save_site_dock",
		saved: () => __("Dock updated for everyone"),
	},
};

frappe.ui.DockManager = class DockManager {
	constructor() {
		this.make();
	}

	make() {
		// The dock renders for `get_sidebar_app()` (the shown sidebar's app), so curate that one.
		// It is also the only app context there is -- a module belonging to no app has no dock to
		// arrange, which is why the user menu doesn't offer this there.
		this.app = frappe.app.sidebar.get_sidebar_app();
		this.scope = "user";
		this.layer = [];
		this.selection = [];
		this.can_curate_site = frappe.user.has_role("Workspace Manager");
		// Shipping writes files inside the app, so it is offered where app content is authored at
		// all -- a developer's site -- and nowhere else. Not a role: the two layers above are what
		// a site rearranges, and neither of them needs this.
		this.can_ship = !!(frappe.boot.developer_mode && this.app);

		this.dialog = new frappe.ui.Dialog({
			title: this.app ? __("Manage {0} Dock", [__(this.app.app_title)]) : __("Manage Dock"),
			size: "extra-large",
			fields: [
				...(this.can_curate_site ? [this.scope_field()] : []),
				{ fieldtype: "HTML", fieldname: "picker" },
			],
			primary_action_label: __("Save"),
			primary_action: () => this.save(),
			...(this.can_ship
				? {
						secondary_action_label: __("Ship This Order"),
						secondary_action: () => this.ship(),
				  }
				: {}),
		});

		this.$body = $(this.dialog.fields_dict.picker.$wrapper);
		this.dialog.show();
		// say which layer is being edited in the field too, not just in `this.scope` -- a Select
		// that renders blank reads as "no layer chosen" when one always is
		if (this.can_curate_site) this.dialog.set_value("scope", this.scope);
		this.load();
	}

	scope_field() {
		return {
			fieldtype: "Select",
			fieldname: "scope",
			label: __("Arranging"),
			default: "user",
			options: [
				{ value: "user", label: __("Just for me") },
				{ value: "site", label: __("For everyone") },
			],
			change: () => this.switch_scope(),
		};
	}

	// The control fires `change` while the dialog is still building its inputs, before the select
	// holds anything -- so a value that isn't a layer is not a switch to it, it is the field
	// telling us it has nothing yet. Taking it at its word left `this.scope` as "" and every read
	// through `layer_scope` undefined.
	switch_scope() {
		const scope = this.dialog.get_value("scope");
		if (!DOCK_SCOPES[scope] || scope === this.scope) return;
		this.scope = scope;
		this.load();
	}

	get layer_scope() {
		return DOCK_SCOPES[this.scope];
	}

	// Load the layer being edited -- its own stored rows, not the resolved dock in
	// `frappe.boot.dock`. A save replaces the layer whole, so it has to be shown
	// what it will overwrite: shown the resolved dock, saving as a user would copy the site's
	// rows into their own layer and freeze them out of every later site change.
	async load() {
		this.loaded = false;
		this.$body.html(`<div class="text-muted">${__("Loading...")}</div>`);
		this.load_entries();
		const [layer, base] = await Promise.all([
			frappe.xcall(this.layer_scope.read),
			frappe.xcall("frappe.desk.doctype.dock.dock.get_app_dock_layer"),
		]);
		this.layer = layer;
		// What the apps ship, so a row the app itself hid can say so. "Hidden" is otherwise
		// silent about who hid it, and un-hiding an app's deliberate default should be a choice
		// rather than an accident.
		this.base_hidden = new Set(
			(base || []).filter((row) => row.hidden).map((row) => this.key(row))
		);
		this.selection = this.initial_selection();
		this.loaded = true;
		this.render();
	}

	// Every entry this app's dock can show, in the server's order, each resolved to the label and
	// icon it renders as. An entry the boot payload doesn't carry is one the user may see nothing
	// in -- a module whose every item is blocked, a workspace they may not open -- so it is not
	// offerable. Keyed by the typed pair, which is also what a layer row names.
	load_entries() {
		this.entries = new Map();
		((this.app && this.app.dock) || []).forEach((row) => {
			const entry = frappe.app.sidebar.dock_entry(row);
			if (entry) this.entries.set(this.key(entry), entry);
		});
	}

	// This app's entries, as keys in the server's order.
	app_keys() {
		return [...this.entries.keys()];
	}

	// What identifies an entry here, on the server and on the rail: the typed pair. Both halves,
	// because a `Sidebar` and a `Workspace` of one name are two entries.
	key(row) {
		return frappe.app.sidebar.dock_key(row.type, row.name);
	}

	// This layer's picks for this app, in their order. A layer is a single flat list across every
	// app and across both kinds of entry, so this app's picks are the rows naming entries it
	// offers.
	initial_selection() {
		const mine = new Set(this.app_keys());
		const arranged = (this.layer || [])
			.filter((row) => !row.hidden && mine.has(this.key(row)))
			.map((row) => this.key(row));
		return arranged.length ? arranged : this.unarranged_selection();
	}

	// One row as a layer stores it, from the key the panes work in.
	stored_row(key, hidden) {
		const entry = this.entries.get(key);
		return { type: entry.type, name: entry.name, hidden };
	}

	// Where an untouched layer starts, so the arrangement is a trim rather than a build from
	// scratch. It has to start from what saving unchanged would produce, because a save writes
	// the whole app slice: seeded with everything the app offers, whoever merely opens this and
	// saves would write `hidden: 0` over what a layer below deliberately hid, un-hiding it
	// without ever asking to.
	//
	// Both scopes therefore start from the layer *below* them, as that layer renders:
	//
	//   - the user's starts from the dock on screen -- the app's order with the site's
	//     arrangement applied
	//   - the site's starts from the base as it renders -- the app's entries minus the ones the
	//     app ships off. Never from the dock this manager happens to see, which carries their
	//     personal arrangement and is not theirs to publish.
	unarranged_selection() {
		if (this.scope === "site") {
			return this.app_keys().filter((key) => !this.base_hidden.has(key));
		}

		const shown = frappe.app.sidebar
			.collect_dock_entries(this.app)
			.map((entry) => this.key(entry));
		return shown.length ? shown : this.app_keys();
	}

	render() {
		this.$body.html(`
			<div class="dock-manager">
				<div class="ws-pane ws-pane-selection">
					<div class="ws-pane-head">
						<span>${__("On the dock")}</span>
						<button class="ws-clear-all btn btn-ghost">${__("Reset")}</button>
					</div>
					<div class="ws-pane-sub">${__("Drag to reorder. Reset brings all of them back.")}</div>
					<div class="ws-list ws-selection"></div>
				</div>
				<div class="ws-pane ws-pane-pool">
					<div class="ws-pane-head">${__("Hidden")}</div>
					<div class="ws-pane-sub">${__("Drag one over to put it back on the dock.")}</div>
					<div class="ws-list ws-pool"></div>
				</div>
			</div>
		`);

		this.$selection = this.$body.find(".ws-selection");
		this.$pool = this.$body.find(".ws-pool");

		this.$body.find(".ws-clear-all").on("click", () => this.clear_all());

		this.render_selection();
		this.render_pool();
		this.setup_selection_sortable();
		this.setup_pool_sortable();
	}

	// An empty selection isn't stored as "an empty dock": it is saved as no rows for this app at
	// all, which is what this layer says when it has nothing to say about it -- so clearing is a
	// reset to the layer below (the site's, or the app's own order).
	clear_all() {
		if (!this.selection.length) return;
		this.selection = [];
		this.render_selection();
		this.render_pool();
	}

	render_selection() {
		this.$selection.empty();
		if (!this.selection.length) {
			this.$selection.append(
				`<div class="ws-empty text-muted">${__("Drag entries here")}</div>`
			);
			return;
		}
		this.selection.forEach((key) => this.$selection.append(this.selection_item(key)));
	}

	// The pool is the app's entries that aren't on the dock yet -- everything droppable in one
	// place, with nothing to filter between.
	render_pool() {
		const keys = this.app_keys().filter((key) => !this.selection.includes(key));

		this.$pool.empty();
		if (!keys.length) {
			this.$pool.append(`<div class="ws-empty text-muted">${__("Nothing is hidden")}</div>`);
			return;
		}
		keys.forEach((key) => this.$pool.append(this.pool_item(key)));
	}

	item(key, cls) {
		const entry = this.entries.get(key);
		const label = entry.label;
		const icon = entry.icon
			? frappe.utils.icon(entry.icon, "md")
			: frappe.utils.desktop_icon(label, "gray", "sm", "Solid");
		// A row the app itself ships off says so. Dragging it over is still all it takes to
		// bring it back -- an off-by-default is a default, not a decision made for you.
		const chip = this.base_hidden.has(key)
			? `<span class="ws-item-chip">${__("app ships this off")}</span>`
			: "";
		return $(`
			<div class="ws-item ${cls || ""}" data-key="${frappe.utils.escape_html(key)}">
				<span class="ws-item-icon">${icon}</span>
				<span class="ws-item-label">${frappe.utils.escape_html(label)}</span>
				${chip}
			</div>
		`);
	}

	selection_item(key) {
		let $el = this.item(key, "ws-selection-item");
		$el.prepend(
			`<span class="ws-item-handle">${frappe.utils.icon("grip-vertical", "sm")}</span>`
		);
		let $remove = $(
			`<button class="ws-item-remove" title="${__("Remove")}">${frappe.utils.icon(
				"x",
				"sm"
			)}</button>`
		);
		$remove.on("click", () => this.remove_from_selection(key));
		$el.append($remove);
		return $el;
	}

	pool_item(key) {
		return this.item(key, "ws-pool-item");
	}

	setup_selection_sortable() {
		this.selection_sortable = new Sortable(this.$selection[0], {
			group: { name: "ws", pull: false, put: true },
			handle: ".ws-item-handle",
			animation: 150,
			ghostClass: "ws-item-ghost",
			// a workspace dragged in from the pool: capture its name, drop the cloned node, and
			// re-render both lists from `this.selection` (our single source of truth)
			onAdd: (evt) => {
				const key = $(evt.item).attr("data-key");
				$(evt.item).remove();
				if (key && !this.selection.includes(key)) this.selection.push(key);
				this.render_selection();
				this.render_pool();
			},
			onUpdate: () => this.sync_order(),
		});
	}

	setup_pool_sortable() {
		if (this.pool_sortable) this.pool_sortable.destroy();
		this.pool_sortable = new Sortable(this.$pool[0], {
			group: { name: "ws", pull: "clone", put: false },
			sort: false,
			animation: 150,
		});
	}

	sync_order() {
		this.selection = $.map(this.$selection.find(".ws-item"), (el) => $(el).attr("data-key"));
	}

	remove_from_selection(key) {
		this.selection = this.selection.filter((k) => k !== key);
		this.render_selection();
		this.render_pool();
	}

	async save() {
		// the layer arrives after the dialog opens; saving before it lands would write an
		// arrangement nobody has seen yet over the one that is there
		if (!this.loaded) return;
		this.sync_order();

		// A layer is one flat list across every app, but a dock belongs to an app -- so replace
		// only this app's entries and leave every other app's arrangement in this layer untouched.
		// Rows are typed pairs, so an entry of another kind that happens to share a module's name
		// is one of the ones left alone.
		const app_keys = this.app_keys();
		const mine = new Set(app_keys);
		const others = (this.layer || []).filter((row) => !mine.has(this.key(row)));
		// An entry this app offers that was left out is stored as an explicit `hidden` row, not
		// simply omitted -- otherwise it would reappear the moment the app adds an entry. Nothing
		// selected at all is the exception: that is Reset, and it stores no row for this app so
		// the layer below shows through instead of the app being hidden entry by entry.
		const hidden = this.selection.length
			? app_keys
					.filter((key) => !this.selection.includes(key))
					.map((key) => this.stored_row(key, 1))
			: [];

		const rows = [
			...others,
			...this.selection.map((key) => this.stored_row(key, 0)),
			...hidden,
		];

		// Both saves answer with the resolved dock -- every app's fragment with the site's
		// arrangement and this user's own on top -- so the rail can be redrawn in place
		// whichever layer was written.
		frappe.boot.dock = await frappe.xcall(this.layer_scope.save, {
			items: JSON.stringify(rows),
		});

		this.dialog.hide();
		frappe.show_alert({ message: this.layer_scope.saved(), indicator: "green" });
		// apply in place -- no reload needed now that the dock reads the returned payload
		frappe.app.sidebar.refresh_dock();
	}

	// Publish the arrangement on screen as the app's own, by writing `sequence_id` into each
	// module's `Sidebar` and exporting it. Not a third layer: the two layers rearrange the
	// list the app ships, and this is that list, so the same dialog authors both.
	//
	// Confirmed first because it is the one action here that leaves the site -- it writes JSON
	// into the app's source tree, which is a commit somebody makes rather than a preference they
	// set. Order only: what is left out of the selection is not hidden, it simply states no
	// sequence and follows the ones that do.
	ship() {
		if (!this.loaded) return;
		this.sync_order();
		if (!this.selection.length) {
			frappe.show_alert({ message: __("Nothing to ship"), indicator: "orange" });
			return;
		}

		frappe.confirm(
			__(
				"Write this order into {0} as the order it ships with? This edits files in the app.",
				[frappe.utils.bold(__(this.app.app_title))]
			),
			async () => {
				// the app is derived server-side from the modules themselves -- `app_name` here is
				// the apps-screen key, which is not always the app a module's files live in. Only
				// the `Sidebar` entries: a pinned workspace is declared in the companion's own
				// files and is not this app's to write.
				const ordered = await frappe.xcall(
					"frappe.desk.doctype.sidebar.sidebar.ship_dock_order",
					{
						modules: JSON.stringify(
							this.selection
								.map((key) => this.entries.get(key))
								.filter((entry) => entry.type === "Sidebar")
								.map((entry) => entry.name)
						),
					}
				);
				this.app.dock = [
					...ordered.map((name) => ({ type: "Sidebar", name })),
					...(this.app.dock || []).filter((row) => row.type !== "Sidebar"),
				];

				this.dialog.hide();
				frappe.show_alert({
					message: __("Shipped. {0} now ships this dock order.", [
						__(this.app.app_title),
					]),
					indicator: "green",
				});
				frappe.app.sidebar.refresh_dock();
			}
		);
	}
};
