// Dock manager -- arranges the module dock (rail) for the app you're currently in: which of that
// app's modules appear on it, and in what order. Two draggable areas: the left is a preview of the
// dock (the chosen modules, reorderable); the right is the rest of the app's modules, ready to drag
// in.
//
// It edits one of the dock's two layers at a time. Everyone has their own; a Workspace Manager can
// switch to the site's, which everyone sees and which each person's own is then applied on top of.
// That is the only thing the scope switch changes -- both layers are the same rows, arranged the
// same way, saved through endpoints that differ only in where they land.
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
		read: "frappe.desk.desktop.get_user_dock_layer",
		save: "frappe.desk.desktop.save_dock_preferences",
		saved: () => __("Dock updated"),
	},
	site: {
		read: "frappe.desk.desktop.get_site_dock_layer",
		save: "frappe.desk.desktop.save_dock_order",
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
	// `frappe.boot.user_dock_modules`. A save replaces the layer whole, so it has to be shown
	// what it will overwrite: shown the resolved dock, saving as a user would copy the site's
	// rows into their own layer and freeze them out of every later site change.
	async load() {
		this.loaded = false;
		this.$body.html(`<div class="text-muted">${__("Loading...")}</div>`);
		this.layer = await frappe.xcall(this.layer_scope.read);
		this.selection = this.initial_selection();
		this.loaded = true;
		this.render();
	}

	// Every module this app's dock can show, in the server's order. A module absent from the
	// payload is one the user may see nothing in, so it is not offerable.
	app_modules() {
		return ((this.app && this.app.modules) || []).filter((name) => this.has_meta(name));
	}

	// This layer's picks for this app, in their order. A layer is a single flat list across every
	// app, so this app's picks are the ones naming its modules.
	initial_selection() {
		const app_modules = this.app_modules();
		const arranged = (this.layer || [])
			.filter((row) => !row.hidden && app_modules.includes(row.module))
			.map((row) => row.module);
		return arranged.length ? arranged : this.unarranged_selection();
	}

	// Where an untouched layer starts, so the arrangement is a trim rather than a build from
	// scratch. It has to start from what saving unchanged would produce, because a save writes
	// the whole app slice: seeded with everything the app offers, a user who merely opens this
	// and saves would write `hidden: 0` over every module the *site* hid, un-hiding it for
	// themselves without ever asking to.
	//
	//   - the user's layer starts from the dock as it currently renders -- the site's
	//     arrangement, applied
	//   - the site's starts from the app's own order, never from the dock this manager happens
	//     to see, which carries their personal arrangement and is not theirs to publish
	unarranged_selection() {
		if (this.scope === "site") return this.app_modules();

		const shown = frappe.app.sidebar.collect_dock_modules(this.app).map((s) => s.module);
		return shown.length ? shown : this.app_modules();
	}

	has_meta(name) {
		return !!(frappe.boot.module_sidebars || {})[name];
	}

	get_ws(name) {
		return (frappe.boot.module_sidebars || {})[name] || { module: name, label: name };
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
					<div class="ws-pane-head">${__("Not on the dock")}</div>
					<div class="ws-pane-sub">${__("Drag one over to add it.")}</div>
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
				`<div class="ws-empty text-muted">${__("Drag modules here")}</div>`
			);
			return;
		}
		this.selection.forEach((name) => this.$selection.append(this.selection_item(name)));
	}

	// The pool is the app's modules that aren't on the dock yet -- everything droppable in one
	// place, with nothing to filter between.
	render_pool() {
		const names = this.app_modules().filter((name) => !this.selection.includes(name));

		this.$pool.empty();
		if (!names.length) {
			this.$pool.append(
				`<div class="ws-empty text-muted">${__("Everything is on the dock")}</div>`
			);
			return;
		}
		names.forEach((name) => this.$pool.append(this.pool_item(name)));
	}

	item(name, cls) {
		const sidebar = this.get_ws(name);
		const label = sidebar.label || name;
		const icon = sidebar.header_icon
			? frappe.utils.icon(sidebar.header_icon, "md")
			: frappe.utils.desktop_icon(label, "gray", "sm", "Solid");
		return $(`
			<div class="ws-item ${cls || ""}" data-name="${frappe.utils.escape_html(name)}">
				<span class="ws-item-icon">${icon}</span>
				<span class="ws-item-label">${frappe.utils.escape_html(label)}</span>
			</div>
		`);
	}

	selection_item(name) {
		let $el = this.item(name, "ws-selection-item");
		$el.prepend(
			`<span class="ws-item-handle">${frappe.utils.icon("grip-vertical", "sm")}</span>`
		);
		let $remove = $(
			`<button class="ws-item-remove" title="${__("Remove")}">${frappe.utils.icon(
				"x",
				"sm"
			)}</button>`
		);
		$remove.on("click", () => this.remove_from_selection(name));
		$el.append($remove);
		return $el;
	}

	pool_item(name) {
		return this.item(name, "ws-pool-item");
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
				const name = $(evt.item).attr("data-name");
				$(evt.item).remove();
				if (name && !this.selection.includes(name)) this.selection.push(name);
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
		this.selection = $.map(this.$selection.find(".ws-item"), (el) => $(el).attr("data-name"));
	}

	remove_from_selection(name) {
		this.selection = this.selection.filter((n) => n !== name);
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
		const app_modules = new Set(this.app_modules());
		const others = (this.layer || []).filter((row) => !app_modules.has(row.module));
		// A module this app offers that was left out is stored as an explicit `hidden` row, not
		// simply omitted -- otherwise it would reappear the moment the app adds a module. Nothing
		// selected at all is the exception: that is Reset, and it stores no row for this app so
		// the layer below shows through instead of the app being hidden module by module.
		const hidden = this.selection.length
			? this.app_modules()
					.filter((name) => !this.selection.includes(name))
					.map((name) => ({ module: name, hidden: 1 }))
			: [];

		const modules = [
			...others,
			...this.selection.map((name) => ({ module: name, hidden: 0 })),
			...hidden,
		];

		// Both saves answer with the resolved dock -- the site's arrangement with this user's own
		// on top -- so the rail can be redrawn in place whichever layer was written.
		frappe.boot.user_dock_modules = await frappe.xcall(this.layer_scope.save, {
			modules: JSON.stringify(modules),
		});

		this.dialog.hide();
		frappe.show_alert({ message: this.layer_scope.saved(), indicator: "green" });
		// apply in place -- no reload needed now that the dock reads the returned payload
		frappe.app.sidebar.refresh_dock();
	}

	// Publish the arrangement on screen as the app's own, by writing `sequence_id` into each
	// module's `Module Sidebar` and exporting it. Not a third layer: the two layers rearrange the
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
				// the apps-screen key, which is not always the app a module's files live in
				this.app.modules = await frappe.xcall(
					"frappe.desk.doctype.module_sidebar.module_sidebar.ship_dock_order",
					{ modules: JSON.stringify(this.selection) }
				);

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
