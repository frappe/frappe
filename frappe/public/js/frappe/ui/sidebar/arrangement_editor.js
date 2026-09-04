// One editor over the arrangements a navigation surface has.
//
// There are two surfaces, and both are the same thing: an ordered list of entries that more than
// one party can arrange. The dock belongs to an app and runs along the side of the screen; a
// Sidebar belongs to a module. Each is stored in two writable layers: every user has their own,
// and a curator can switch to the site's, which everyone sees and on top of which each user's own
// layer is applied. That is all the layer switch changes: both layers hold the same rows, arranged
// the same way, saved through endpoints that differ only in where they write.
//
// The dialog is one list with a preview beside it. The list holds every entry the surface offers,
// in one order, and the eye on a row is all there is to being on the surface or hidden, so a
// hidden entry keeps its place instead of moving to a pool at the end. The preview draws the
// arrangement the way the surface will render it, which is the question a user has while dragging:
// not which rows they picked, but what it will look like.
//
// An untouched layer starts from the layer below it, as that layer renders. A save writes the
// whole slice, so seeding from anything else would silently un-hide what a lower layer hid. The
// rule is stated here even though each surface implements it differently: the dock works it out in
// the client, and the sidebar is given it by its read endpoint.
//
// A surface supplies little: what its layers read, save and reset through, what its entries are
// and what keys them, how an entry draws in the preview, and any per-entry fields a user may set.
// The layer switch, the list, the eye and the persistence live here.
frappe.ui.ArrangementEditor = class ArrangementEditor {
	constructor() {
		this.make();
	}

	// -------------------------------------------------------------------------------------------
	// What a surface supplies. Everything below this block is the same for both surfaces.
	// -------------------------------------------------------------------------------------------

	// `{user: {read, save, saved(), label(), condition?}, site: {...}}`: where a layer is read
	// from, where it is written back to, what to call it in the switch, and what to say once it
	// lands. A layer whose `condition` returns false is not offered.
	get layers() {
		return {};
	}

	// The layers this user may write, in switch order. The switch only shows what the endpoints
	// will accept, so no value can fail on Save.
	get offered_layers() {
		return Object.entries(this.layers).filter(
			([, layer]) => !layer.condition || layer.condition()
		);
	}

	// Whatever a surface needs resolved before the dialog is titled: its subject and its gates.
	prepare() {}

	title() {
		return __("Arrange");
	}

	// Extra `frappe.ui.Dialog` options, such as a secondary action one surface offers and the
	// other does not.
	extra_actions() {
		return {};
	}

	// Read the layer named by `this.layer`, populating `this.entries` (key to entry) and setting
	// the arrangement through `arrange()`. It throws when the read fails; nothing is rendered and
	// no action, including Save, will run.
	async read() {}

	// The arguments the save endpoint takes, given the arrangement on screen.
	save_args() {
		return {};
	}

	// Apply what a save or a reset returned, in place.
	apply() {}

	// What the Reset button in the list header does. The two surfaces mean different things by
	// it, so neither inherits the other's.
	reset() {}

	// Whether this surface's layers may add an entry rather than only order and hide the ones the
	// base gave them. `frappe.desk.layers` sets the rule: the base adds, orders and hides, and the
	// layers above order and hide. A sidebar is the exception, because a `Custom Sidebar` row can
	// carry an item of its own. A dock row cannot; it names something the app already shipped.
	can_add() {
		return false;
	}

	// Put a new entry into the arrangement. Only reached when `can_add()` allows it.
	add() {}

	// The wording, one place per surface, so the panes can say what they are arranging. The base
	// reads `list_head`, `list_sub`, `reset_title`, `list_empty`, `preview_head`, `preview_sub`,
	// `preview_empty` and `load_error`. A surface may add more for its own use, which is where the
	// sidebar's Reset keeps its confirmation text.
	copy() {
		return {};
	}

	// Extra markup on an entry in the list, such as a chip saying who hid it.
	item_extras() {
		return "";
	}

	// Extra classes on an entry, in the list and in the preview, for anything a surface draws
	// differently.
	item_classes() {
		return "";
	}

	// Extra controls on a list entry, which need a handler and so are attached to the node.
	decorate_item() {}

	// Extra buttons beside Add and Reset in the list header, for an action one surface has and the
	// other does not. Each is `{label, title, onClick}`.
	extra_pane_actions() {
		return [];
	}

	// A muted line under the pane's subtitle, for reporting rather than for acting on. Empty by
	// default, because most surfaces have nothing to report.
	pane_note() {
		return "";
	}

	// What the eye says it will do. A surface where hiding means different things at different
	// layers states that here. See the dock, where an author hiding a row ships it off by default
	// and a site hiding one makes a customization.
	hide_tooltip(key, hidden) {
		return hidden ? __("Show") : __("Hide");
	}

	// One entry was dragged to a new place. A surface where position means more than order handles
	// that here. See the sidebar, where the drop position decides which section an entry is in.
	on_move() {}

	// -------------------------------------------------------------------------------------------
	// The editor itself
	// -------------------------------------------------------------------------------------------

	make() {
		this.entries = new Map();
		this.order = [];
		this.hidden = new Set();
		this.can_curate_site = frappe.user.has_role("Workspace Manager");
		this.prepare();
		// Which layer the editor opens on: the app's wherever it is offered, which is developer
		// mode and nowhere else. A developer's site is where an app's navigation is authored, so
		// that is the layer they came to edit, and opening anywhere else means switching every
		// time. The other two stay in the switch for the times they meant one site or themselves.
		//
		// Everyone else opens on the site's layer if they may curate it, since arranging for
		// everyone is what that permission is for, and on their own if not.
		//
		// Read after `prepare`, because that is where a surface settles what the permission means
		// for it. Opening on a layer this user cannot write would fail on Save instead of never
		// being offered, so this picks among the layers actually on offer.
		const offered = new Set(this.offered_layers.map(([name]) => name));
		if (offered.has("app")) {
			this.layer = "app";
		} else {
			this.layer = this.can_curate_site ? "site" : "user";
		}

		this.dialog = new frappe.ui.Dialog({
			title: this.title(),
			size: "extra-large",
			fields: [{ fieldtype: "HTML", fieldname: "picker" }],
			primary_action_label: __("Save"),
			primary_action: () => this.save(),
			...this.extra_actions(),
		});

		this.$body = $(this.dialog.fields_dict.picker.$wrapper);
		this.dialog.show();
		if (this.offered_layers.length > 1) this.mount_layer_switch();
		this.load();
	}

	// The just-me / everyone switch, and all the site layer's gate looks like from here: without
	// the right to curate for everyone the switch is absent, so nothing can fail on save. What
	// that right is belongs to the endpoints, which check it again.
	//
	// It sits in the dialog header beside the close button rather than above the panes as the
	// first field of the body. It is not part of the arrangement, it says which arrangement you
	// are looking at, and a field in front of the list read as one more thing to fill in before
	// starting.
	mount_layer_switch() {
		const options = this.offered_layers
			.map(([name, layer]) => `<option value="${name}">${layer.label()}</option>`)
			.join("");
		this.$layer = $(`
			<select class="ws-layer-switch form-control input-xs" title="${__("Arranging")}">
				${options}
			</select>
		`);
		// A switch that renders blank reads as no layer chosen, but one is always chosen.
		this.$layer.val(this.layer);
		this.$layer.on("change", () => this.switch_layer());
		this.dialog.$wrapper.find(".modal-actions").prepend(this.$layer);
	}

	// A value naming no layer, and the layer already on screen, are both non-switches. Treating
	// either as a switch would re-read the arrangement for nothing, and the first would also leave
	// `this.layer` naming a layer that does not exist, making every read through `layer_config`
	// undefined.
	switch_layer() {
		const layer = this.$layer.val();
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
			// Report the failure rather than sit on "Loading..." forever. `loaded` stays false, so
			// Save and every other action do nothing, since none should act on an arrangement that
			// was never read.
			console.error("Arrangement editor: could not read the arrangement", e);
			this.$body.html(`<div class="text-muted">${this.copy().load_error}</div>`);
			return;
		}

		this.loaded = true;
		this.render();
	}

	// Every key the list works in, in the surface's own order. Both surfaces build `this.entries`
	// in that order, so the map itself gives the order.
	all_keys() {
		return [...this.entries.keys()];
	}

	// The one list the editor works in: every entry the surface offers, in one order, and which of
	// them are hidden. `read()` sets it once, and the list on screen is that from then on.
	//
	// A key the layer never named is appended in the surface's own order and hidden. A layer that
	// named some entries and not others has said nothing about the rest, and an entry nobody has
	// placed should not appear on the surface uninvited. This is also how a newly installed app's
	// entries reach an arrangement someone has already made.
	arrange(order, hidden = []) {
		const named = order.filter((key) => this.entries.has(key));
		const unnamed = this.all_keys().filter((key) => !named.includes(key));

		this.order = [...named, ...unnamed];
		this.hidden = new Set([...hidden, ...unnamed].filter((key) => this.entries.has(key)));
	}

	// What is on the surface, in order: the arrangement minus what the eye has taken off. Every
	// surface uses this rather than reading `order`, because it is the arrangement as it renders.
	get selection() {
		return this.order.filter((key) => !this.hidden.has(key));
	}

	render() {
		const copy = this.copy();
		this.$body.html(`
			<div class="arrangement-editor">
				<div class="ws-pane ws-pane-arrangement">
					<div class="ws-pane-head">
						<span>${copy.list_head}</span>
						<span class="ws-pane-actions">
							${this.can_add() ? `<button class="ws-add btn btn-ghost">${copy.add_label}</button>` : ""}
							<button class="ws-reset btn btn-ghost" title="${copy.reset_title}">${__("Reset")}</button>
							${this.extra_pane_actions()
								.map(
									(action, idx) =>
										`<button class="ws-extra-action btn btn-ghost" data-action="${idx}" title="${frappe.utils.escape_html(
											action.title || ""
										)}">${action.label}</button>`
								)
								.join("")}
						</span>
					</div>
					<div class="ws-pane-sub">${copy.list_sub}</div>
					${this.pane_note() ? `<div class="ws-pane-note text-muted">${this.pane_note()}</div>` : ""}
					<div class="ws-list ws-arrangement"></div>
				</div>
				<div class="ws-pane ws-pane-preview">
					<div class="ws-pane-head">${copy.preview_head}</div>
					<div class="ws-pane-sub">${copy.preview_sub}</div>
					<div class="ws-list ws-preview"></div>
				</div>
			</div>
		`);

		this.$arrangement = this.$body.find(".ws-arrangement");
		this.$preview = this.$body.find(".ws-preview");

		this.$body.find(".ws-add").on("click", () => this.add());
		this.$body.find(".ws-reset").on("click", () => this.reset());
		const extras = this.extra_pane_actions();
		this.$body
			.find(".ws-extra-action")
			.on("click", (e) => extras[$(e.currentTarget).data("action")].onClick());

		this.render_panes();
		this.setup_sortable();
	}

	render_panes() {
		this.render_list();
		this.render_preview();
	}

	render_list() {
		this.$arrangement.empty();
		if (!this.order.length) {
			this.$arrangement.append(
				`<div class="ws-empty text-muted">${this.copy().list_empty}</div>`
			);
			return;
		}
		this.order.forEach((key) => this.$arrangement.append(this.list_item(key)));
	}

	// The preview is the arrangement as the surface renders it, so it holds what is on the surface
	// and nothing else. A hidden entry is absent here, which is all hiding one does.
	render_preview() {
		const shown = this.selection;

		this.$preview.empty();
		if (!shown.length) {
			this.$preview.append(
				`<div class="ws-empty text-muted">${this.copy().preview_empty}</div>`
			);
			return;
		}
		shown.forEach((key) => this.$preview.append(this.preview_item(key)));
	}

	// What an entry draws as: its own icon, or a lettered tile in place of one. A surface that
	// draws no icons returns nothing and is given no room for one. See the sidebar, which is
	// labels only.
	entry_icon(entry) {
		return entry.icon
			? frappe.utils.icon(entry.icon, "md")
			: frappe.utils.desktop_icon(entry.label, "gray", "sm", "Solid");
	}

	item(key, cls) {
		const entry = this.entries.get(key);
		const icon = this.entry_icon(entry);
		return $(`
			<div class="ws-item ${cls || ""} ${this.item_classes(key)}" data-key="${frappe.utils.escape_html(
			key
		)}">
				${icon ? `<span class="ws-item-icon">${icon}</span>` : ""}
				<span class="ws-item-label">${frappe.utils.escape_html(entry.label)}</span>
				${this.item_extras(key)}
			</div>
		`);
	}

	list_item(key) {
		let $el = this.item(
			key,
			`ws-arrangement-item ${this.hidden.has(key) ? "ws-item-hidden" : ""}`
		);
		$el.prepend(
			`<span class="ws-item-handle">${frappe.utils.icon("grip-vertical", "sm")}</span>`
		);
		this.decorate_item($el, key);
		$el.append(this.is_own_add(key) ? this.remove_button(key) : this.visibility_button(key));
		return $el;
	}

	// Whether this layer added the entry itself, rather than overriding one a lower layer holds.
	// An entry this layer added is removed with a cross rather than an eye: there is nothing below
	// it to hide it from, so changing your mind about your own row means deleting it.
	is_own_add() {
		return false;
	}

	// The eye, which is all of hide and show for an entry a lower layer holds: one list, one
	// control, and a row that keeps its place either way.
	visibility_button(key) {
		const hidden = this.hidden.has(key);
		let $btn = $(
			`<button class="ws-item-eye" title="${frappe.utils.escape_html(
				this.hide_tooltip(key, hidden)
			)}">${frappe.utils.icon(hidden ? "eye-off" : "eye", "sm")}</button>`
		);
		$btn.on("click", () => this.toggle(key));
		return $btn;
	}

	// The cross, for a row this layer added. Hiding it would store a layer holding an entry it
	// does not show, which means nothing: the entry exists only because this layer names it.
	remove_button(key) {
		let $btn = $(
			`<button class="ws-item-remove" title="${__("Remove")}">${frappe.utils.icon(
				"x",
				"sm"
			)}</button>`
		);
		$btn.on("click", () => this.remove(key));
		return $btn;
	}

	// Remove an entry this layer added from the arrangement entirely.
	remove(key) {
		this.entries.delete(key);
		this.order = this.order.filter((k) => k !== key);
		this.hidden.delete(key);
		this.render_panes();
	}

	toggle(key) {
		if (this.hidden.has(key)) this.hidden.delete(key);
		else this.hide(key);
		this.render_panes();
	}

	// Take an entry off the surface. It is hidden rather than dropped, because the arrangement is
	// stored whole: a row left out would keep whatever the layer below said about it and keep
	// rendering.
	hide(key) {
		this.hidden.add(key);
	}

	// One entry as it will read on the surface. A surface whose entries do not all draw the same
	// way overrides this. See the sidebar, where a section header is a header and not a link.
	preview_item(key) {
		const entry = this.entries.get(key);
		const icon = this.entry_icon(entry);
		return $(`
			<div class="ws-preview-item ${this.item_classes(key)}">
				${icon ? `<span class="ws-item-icon">${icon}</span>` : ""}
				<span class="ws-item-label">${frappe.utils.escape_html(entry.label)}</span>
			</div>
		`);
	}

	setup_sortable() {
		// A layer switch re-renders, so the list it was bound to is gone.
		if (this.sortable) this.sortable.destroy();

		this.sortable = new Sortable(this.$arrangement[0], {
			handle: ".ws-item-handle",
			animation: 150,
			ghostClass: "ws-item-ghost",
			// The preview is the point of the drag, so it follows the drop rather than waiting for
			// a save. The list is redrawn with it, because a surface may derive something from
			// where the entry landed.
			onUpdate: (evt) => {
				this.sync_order();
				this.on_move($(evt.item).attr("data-key"));
				this.render_panes();
			},
		});
	}

	// The arrangement on screen as stored rows: every entry, in the order the list holds it, each
	// carrying whether the eye has it off. An entry taken off is stored as hidden rather than
	// omitted, because an omitted row would keep whatever the layer below said about it and keep
	// rendering.
	//
	// `row(key, hidden)` is the only part a surface supplies, because the shape of a stored row is
	// the one thing the two surfaces do not share.
	arranged_rows(row) {
		return this.order.map((key) => row(key, this.hidden.has(key) ? 1 : 0));
	}

	sync_order() {
		this.order = $.map(this.$arrangement.find(".ws-item"), (el) => $(el).attr("data-key"));
	}

	async save() {
		// The layer arrives after the dialog opens. Saving before it lands would overwrite the
		// stored arrangement with one nobody has seen.
		if (!this.loaded) return;
		this.sync_order();

		this.apply(await frappe.xcall(this.layer_config.save, this.save_args()));

		this.dialog.hide();
		frappe.show_alert({ message: this.layer_config.saved(), indicator: "green" });
	}
};
