// One editor over the arrangements a navigation surface has.
//
// Two of them exist, and both are the same thing: an ordered list of entries that more than one
// party gets an opinion about. The dock is an app's, running along the side of the screen; a
// Sidebar is a module's. Each is stored in two writable layers -- everyone has their own, and a
// curator can switch to the site's, which everyone sees and each person's own is then applied on
// top of. That is the only thing the layer switch changes: both layers are the same rows,
// arranged the same way, saved through endpoints that differ only in where they land.
//
// Two draggable panes, meaning one thing on every surface and under every layer: on the surface, or
// hidden. The left is the arrangement, reorderable; the right is the pool of what is not on it,
// ready to drag in.
//
// An untouched layer starts from the layer *below* it as that layer renders. A save writes the
// whole slice, so seeding from anything else would silently un-hide what a lower layer hid --
// which is why the rule is stated here even though each surface reaches it its own way: the dock
// works it out in the client, the sidebar is handed it by its read endpoint.
//
// What a surface supplies is small: what its layers read, save and reset through, what its entries
// are and what keys them, and whatever per-entry fields it lets a person state. The layer switch,
// the sortables, the pool and the persistence are here.
frappe.ui.ArrangementEditor = class ArrangementEditor {
	constructor() {
		this.make();
	}

	// -------------------------------------------------------------------------------------------
	// What a surface supplies. Everything below this block is the same work for either of them.
	// -------------------------------------------------------------------------------------------

	// `{user: {read, save, reset, saved()}, site: {...}}` -- where a layer is read from, where it
	// is written back to, and what to say once it lands.
	get layers() {
		return {};
	}

	// Whatever a surface needs resolved before the dialog is titled: its subject, its own gates.
	prepare() {}

	title() {
		return __("Arrange");
	}

	// Extra `frappe.ui.Dialog` options -- a secondary action one surface offers and the other does not.
	extra_actions() {
		return {};
	}

	// Read the layer named by `this.layer`, leaving `this.entries` (key -> entry) and
	// `this.selection` (the keys on the surface, in order) behind. Throwing is how it says the
	// read failed; nothing is rendered and neither Save nor anything else will act.
	async read() {}

	// The arguments the save endpoint takes, once `this.selection` is the arrangement on screen.
	save_args() {
		return {};
	}

	// Apply what a save or a reset answered with, in place.
	apply() {}

	// What the Reset button in the selection pane's head does. The two surfaces mean different
	// things by it, so neither inherits the other's.
	reset() {}

	// Whether this surface's layers may *add* an entry rather than only order and hide the ones
	// the base gave them. `frappe.desk.layers` states the asymmetry the two ends live by -- the
	// base adds, orders and hides; the layers above order and hide -- and a sidebar is the one
	// exception, because a `Custom Sidebar` row can carry an item of its own. A dock row cannot;
	// it names something the app already put on the fragment.
	can_add() {
		return false;
	}

	// Put a new entry on the arrangement. Only ever reached when `can_add()` says so.
	add() {}

	// The words, one place per surface, so the panes can say what they are actually arranging.
	// The base reads `selection_head`, `selection_sub`, `reset_title`, `selection_empty`,
	// `pool_head`, `pool_sub`, `pool_empty` and `load_error`; a surface may carry more for its
	// own use, which is where the sidebar's Reset keeps its confirmation.
	copy() {
		return {};
	}

	// Extra markup on an entry, on both panes -- a chip saying who hid it, and the like.
	item_extras() {
		return "";
	}

	// Extra classes on an entry, on both panes -- what a surface draws differently about one.
	item_classes() {
		return "";
	}

	// Extra affordances on a selection entry, which need a handler and so are hung on the node.
	decorate_selection_item() {}

	// -------------------------------------------------------------------------------------------
	// The editor itself
	// -------------------------------------------------------------------------------------------

	make() {
		this.layer = "user";
		this.entries = new Map();
		this.selection = [];
		this.can_curate_site = frappe.user.has_role("Workspace Manager");
		this.prepare();

		this.dialog = new frappe.ui.Dialog({
			title: this.title(),
			size: "extra-large",
			fields: [
				...(this.can_curate_site ? [this.layer_field()] : []),
				{ fieldtype: "HTML", fieldname: "picker" },
			],
			primary_action_label: __("Save"),
			primary_action: () => this.save(),
			...this.extra_actions(),
		});

		this.$body = $(this.dialog.fields_dict.picker.$wrapper);
		this.dialog.show();
		// say which layer is being edited in the field too, not just in `this.layer` -- a Select
		// that renders blank reads as "no layer chosen" when one always is
		if (this.can_curate_site) this.dialog.set_value("layer", this.layer);
		this.load();
	}

	// The just-me / everyone switch, and the whole of what the site layer's gate looks like from
	// here: without the right to curate for everyone the field is absent, so there is nothing to
	// fail on save. What that right *is* belongs to the endpoints, which check it again.
	layer_field() {
		return {
			fieldtype: "Select",
			fieldname: "layer",
			label: __("Arranging"),
			default: "user",
			options: [
				{ value: "user", label: __("Just for me") },
				{ value: "site", label: __("For everyone") },
			],
			change: () => this.switch_layer(),
		};
	}

	// The control fires `change` while the dialog is still building its inputs, before the select
	// holds anything -- so a value that isn't a layer is not a switch to it, it is the field
	// telling us it has nothing yet. Taking it at its word left `this.layer` as "" and every read
	// through `layer_config` undefined.
	switch_layer() {
		const layer = this.dialog.get_value("layer");
		if (!this.layers[layer] || layer === this.layer) return;
		this.layer = layer;
		this.load();
	}

	get layer_config() {
		return this.layers[this.layer];
	}

	async load() {
		this.loaded = false;
		this.$body.html(`<div class="text-muted">${__("Loading...")}</div>`);

		try {
			await this.read();
		} catch (e) {
			// Say so rather than sit on "Loading..." forever. `loaded` stays false, so Save and
			// every other action do nothing -- none of them should act on an arrangement we
			// never read.
			console.error("Arrangement editor: could not read the arrangement", e);
			this.$body.html(`<div class="text-muted">${this.copy().load_error}</div>`);
			return;
		}

		this.loaded = true;
		this.render();
	}

	// Every key the pool and the panes work in, in the surface's own order. `this.entries` is
	// built in that order by both of them, so the map is the answer.
	all_keys() {
		return [...this.entries.keys()];
	}

	render() {
		const copy = this.copy();
		this.$body.html(`
			<div class="arrangement-editor">
				<div class="ws-pane ws-pane-selection">
					<div class="ws-pane-head">
						<span>${copy.selection_head}</span>
						<span class="ws-pane-actions">
							${this.can_add() ? `<button class="ws-add btn btn-ghost">${copy.add_label}</button>` : ""}
							<button class="ws-reset btn btn-ghost" title="${copy.reset_title}">${__("Reset")}</button>
						</span>
					</div>
					<div class="ws-pane-sub">${copy.selection_sub}</div>
					<div class="ws-list ws-selection"></div>
				</div>
				<div class="ws-pane ws-pane-pool">
					<div class="ws-pane-head">${copy.pool_head}</div>
					<div class="ws-pane-sub">${copy.pool_sub}</div>
					<div class="ws-list ws-pool"></div>
				</div>
			</div>
		`);

		this.$selection = this.$body.find(".ws-selection");
		this.$pool = this.$body.find(".ws-pool");

		this.$body.find(".ws-add").on("click", () => this.add());
		this.$body.find(".ws-reset").on("click", () => this.reset());

		this.render_panes();
		this.setup_selection_sortable();
		this.setup_pool_sortable();
	}

	render_panes() {
		this.render_selection();
		this.render_pool();
	}

	render_selection() {
		this.$selection.empty();
		if (!this.selection.length) {
			this.$selection.append(
				`<div class="ws-empty text-muted">${this.copy().selection_empty}</div>`
			);
			return;
		}
		this.selection.forEach((key) => this.$selection.append(this.selection_item(key)));
	}

	// The pool is everything the surface offers that is not on it -- one place, with nothing to
	// filter between.
	render_pool() {
		const keys = this.all_keys().filter((key) => !this.selection.includes(key));

		this.$pool.empty();
		if (!keys.length) {
			this.$pool.append(`<div class="ws-empty text-muted">${this.copy().pool_empty}</div>`);
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
		return $(`
			<div class="ws-item ${cls || ""} ${this.item_classes(key)}" data-key="${frappe.utils.escape_html(
			key
		)}">
				<span class="ws-item-icon">${icon}</span>
				<span class="ws-item-label">${frappe.utils.escape_html(label)}</span>
				${this.item_extras(key)}
			</div>
		`);
	}

	selection_item(key) {
		let $el = this.item(key, "ws-selection-item");
		$el.prepend(
			`<span class="ws-item-handle">${frappe.utils.icon("grip-vertical", "sm")}</span>`
		);
		this.decorate_selection_item($el, key);
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
			// an entry dragged in from the pool: capture its key, drop the cloned node, and
			// re-render both lists from `this.selection` (our single source of truth)
			onAdd: (evt) => {
				const key = $(evt.item).attr("data-key");
				$(evt.item).remove();
				if (key && !this.selection.includes(key)) this.selection.push(key);
				this.render_panes();
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

	// The arrangement on screen as stored rows: what is on the surface, in order, then
	// everything else flagged hidden. An entry left out is stored rather than simply omitted --
	// omitted, it would keep whatever the layer below said about it and go on rendering.
	//
	// `row(key, hidden)` is the only part a surface has to supply, because what a stored row
	// looks like is the one thing the two of them do not share.
	arranged_rows(row) {
		return [
			...this.selection.map((key) => row(key, 0)),
			...this.all_keys()
				.filter((key) => !this.selection.includes(key))
				.map((key) => row(key, 1)),
		];
	}

	sync_order() {
		this.selection = $.map(this.$selection.find(".ws-item"), (el) => $(el).attr("data-key"));
	}

	remove_from_selection(key) {
		this.selection = this.selection.filter((k) => k !== key);
		this.render_panes();
	}

	async save() {
		// the layer arrives after the dialog opens; saving before it lands would write an
		// arrangement nobody has seen yet over the one that is there
		if (!this.loaded) return;
		this.sync_order();

		this.apply(await frappe.xcall(this.layer_config.save, this.save_args()));

		this.dialog.hide();
		frappe.show_alert({ message: this.layer_config.saved(), indicator: "green" });
	}
};
