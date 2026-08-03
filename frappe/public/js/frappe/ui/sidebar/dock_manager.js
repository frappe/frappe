// Dock manager -- lets the user curate the module dock (rail) for the app they're currently in:
// which of that app's modules appear on it, and in what order. Two draggable areas: the left is a
// preview of the dock (their chosen modules, reorderable); the right is the rest of the app's
// modules, ready to drag in.
//
// Scoped to one app on purpose -- a dock belongs to an app, so there's nothing to choose between
// here and no app switcher. Modules in other apps are managed from those apps' docks.
//
// All data comes from `frappe.boot`; only the selection is saved.
frappe.ui.DockManager = class DockManager {
	constructor() {
		this.make();
	}

	make() {
		// The dock renders for `get_sidebar_app()` (the shown sidebar's app), so curate that one.
		// Reading `frappe.current_app` here let the picker edit a different app's dock than the
		// one on screen whenever the two diverged.
		this.app = frappe.app.sidebar.get_sidebar_app() || frappe.current_app;
		this.selection = this.initial_selection();

		this.dialog = new frappe.ui.Dialog({
			title: this.app ? __("Manage {0} Dock", [__(this.app.app_title)]) : __("Manage Dock"),
			size: "extra-large",
			fields: [{ fieldtype: "HTML", fieldname: "picker" }],
			primary_action_label: __("Save"),
			primary_action: () => this.save(),
		});

		this.$body = $(this.dialog.fields_dict.picker.$wrapper);
		this.render();
		this.dialog.show();
	}

	// Every module this app's dock can show, in the server's order. A module absent from the
	// payload is one the user may see nothing in, so it is not offerable.
	app_modules() {
		return ((this.app && this.app.modules) || []).filter((name) => this.has_meta(name));
	}

	// The user's curated picks for this app, in their order. `User.workspaces` is a single flat
	// list across every app, so this app's picks are the ones naming its workspaces. Nothing
	// curated for this app yet -> start from everything it offers (what the dock shows by
	// default), so the user trims rather than builds from scratch.
	// The user's curated picks for this app, in their order. `User.dock_modules` is a single
	// flat list across every app, so this app's picks are the ones naming its modules. Nothing
	// curated for this app yet -> start from everything it offers (what the dock shows by
	// default), so the user trims rather than builds from scratch.
	initial_selection() {
		const app_modules = this.app_modules();
		const curated = (frappe.boot.user_dock_modules || [])
			.filter((row) => !row.hidden && app_modules.includes(row.module))
			.map((row) => row.module);
		return curated.length ? curated : app_modules;
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

	// An empty selection isn't stored as "an empty dock": the dock falls back to the app's full
	// list when the user has curated nothing for it, so clearing is a reset to default.
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

	// The pool is the app's workspaces that aren't on the dock yet -- everything droppable in one
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
		this.sync_order();

		// `User.dock_modules` is one flat list across every app, but a dock belongs to an app --
		// so replace only this app's entries and leave every other app's curation untouched.
		const app_modules = new Set(this.app_modules());
		const others = (frappe.boot.user_dock_modules || []).filter(
			(row) => !app_modules.has(row.module)
		);
		// A module this app offers that the user left out is stored as an explicit `hidden` row,
		// not simply omitted -- otherwise it would reappear the moment the app adds a module.
		const hidden = this.app_modules()
			.filter((name) => !this.selection.includes(name))
			.map((name) => ({ module: name, hidden: 1 }));

		const modules = [
			...others,
			...this.selection.map((name) => ({ module: name, hidden: 0 })),
			...hidden,
		];

		frappe.boot.user_dock_modules = await frappe.xcall(
			"frappe.desk.desktop.save_dock_preferences",
			{ modules: JSON.stringify(modules) }
		);

		this.dialog.hide();
		frappe.show_alert({ message: __("Dock updated"), indicator: "green" });
		// apply in place -- no reload needed now that the dock reads the returned payload
		frappe.app.sidebar.refresh_dock();
	}
};
