// One editor over the arrangements a navigation surface has.
//
// Two of them exist, and both are the same thing: an ordered list of entries that more than one
// party gets an opinion about. The dock is an app's, running along the side of the screen; a
// Sidebar is a module's. Each is stored in two writable layers -- everyone has their own, and a
// curator can switch to the site's, which everyone sees and each person's own is then applied on
// top of. That is the only thing the layer switch changes: both layers are the same rows,
// arranged the same way, saved through endpoints that differ only in where they land.
//
// One list and a preview beside it. The list holds every entry the surface offers, in one order,
// and the eye on a row is the whole of on-the-surface or hidden -- so a hidden entry keeps its
// place and comes back where it was left, rather than out of a pool at the end. The pane beside it
// draws the arrangement the way the surface will render it, which is the question a person
// actually has while dragging: not "which rows did I pick" but "what does it look like".
//
// An untouched layer starts from the layer *below* it as that layer renders. A save writes the
// whole slice, so seeding from anything else would silently un-hide what a lower layer hid --
// which is why the rule is stated here even though each surface reaches it its own way: the dock
// works it out in the client, the sidebar is handed it by its read endpoint.
//
// What a surface supplies is small: what its layers read, save and reset through, what its entries
// are and what keys them, how one of them draws in the preview, and whatever per-entry fields it
// lets a person state. The layer switch, the list, the eye and the persistence are here.
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

	// Read the layer named by `this.layer`, leaving `this.entries` (key -> entry) behind and
	// stating the arrangement through `arrange()`. Throwing is how it says the read failed;
	// nothing is rendered and neither Save nor anything else will act.
	async read() {}

	// The arguments the save endpoint takes, once the list on screen is the arrangement.
	save_args() {
		return {};
	}

	// Apply what a save or a reset answered with, in place.
	apply() {}

	// What the Reset button in the list's head does. The two surfaces mean different things by
	// it, so neither inherits the other's.
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
	// The base reads `list_head`, `list_sub`, `reset_title`, `list_empty`, `preview_head`,
	// `preview_sub`, `preview_empty` and `load_error`; a surface may carry more for its own use,
	// which is where the sidebar's Reset keeps its confirmation.
	copy() {
		return {};
	}

	// Extra markup on an entry in the list -- a chip saying who hid it, and the like.
	item_extras() {
		return "";
	}

	// Extra classes on an entry, in the list and in the preview -- what a surface draws
	// differently about one.
	item_classes() {
		return "";
	}

	// Extra affordances on a list entry, which need a handler and so are hung on the node.
	decorate_item() {}

	// One entry was dragged to a new place. A surface where position means something beyond
	// order says so here -- see the sidebar, where where you drop an entry is what says which
	// section it belongs to.
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
		// Which layer the editor opens on: the site's, for whoever may curate it. Arranging for
		// everyone is what the right is for, and a curator who meant only their own has the
		// switch sitting in the header to say so. Everybody else has one layer and opens on it.
		//
		// Read after `prepare`, because that is where a surface settles what the right means for
		// it -- opening on a layer this person may not write would be an editor that fails on
		// Save rather than one that never offered it.
		this.layer = this.can_curate_site ? "site" : "user";

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
		if (this.can_curate_site) this.mount_layer_switch();
		this.load();
	}

	// The just-me / everyone switch, and the whole of what the site layer's gate looks like from
	// here: without the right to curate for everyone the switch is absent, so there is nothing to
	// fail on save. What that right *is* belongs to the endpoints, which check it again.
	//
	// It hangs in the dialog's own header beside the close button rather than sitting above the
	// panes as the first field of the body. It is not part of the arrangement -- it says which
	// arrangement you are looking at -- and a field in front of the list read as one more thing
	// to fill in before getting to the work.
	mount_layer_switch() {
		this.$layer = $(`
			<select class="ws-layer-switch form-control input-xs" title="${__("Arranging")}">
				<option value="user">${__("Just for me")}</option>
				<option value="site">${__("For everyone")}</option>
			</select>
		`);
		// a switch that renders blank reads as "no layer chosen" when one always is
		this.$layer.val(this.layer);
		this.$layer.on("change", () => this.switch_layer());
		this.dialog.$wrapper.find(".modal-actions").prepend(this.$layer);
	}

	// Neither a value that names no layer nor the layer already on screen is a switch to
	// anything, and reading either as one would re-read the arrangement for nothing -- or, in
	// the first case, leave `this.layer` naming a layer that does not exist and every read
	// through `layer_config` undefined.
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

	// Every key the list works in, in the surface's own order. `this.entries` is built in that
	// order by both of them, so the map is the answer.
	all_keys() {
		return [...this.entries.keys()];
	}

	// The one list the editor works in: every entry the surface offers, in one order, and which
	// of them are hidden. `read()` states it once, and the list on screen is that statement from
	// then on.
	//
	// A key the layer never named is appended in the surface's own order, and hidden -- a layer
	// that named some entries and not others has said nothing about the rest, and an entry
	// nobody has placed is not one to put on the surface uninvited. This is also what carries a
	// newly installed app's entries into an arrangement somebody has already made.
	arrange(order, hidden = []) {
		const named = order.filter((key) => this.entries.has(key));
		const unnamed = this.all_keys().filter((key) => !named.includes(key));

		this.order = [...named, ...unnamed];
		this.hidden = new Set([...hidden, ...unnamed].filter((key) => this.entries.has(key)));
	}

	// What is on the surface, in order: the arrangement minus what the eye has taken off. Every
	// surface asks this rather than reading `order` -- it is the arrangement as it renders.
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
						</span>
					</div>
					<div class="ws-pane-sub">${copy.list_sub}</div>
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

	// The preview is the arrangement as the surface renders it, so it holds what is on the
	// surface and nothing else -- a hidden entry is absent here, which is the whole of what
	// hiding one does.
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

	// What an entry draws as: its own icon, or a lettered tile standing in for one. A surface that
	// draws no icons answers with nothing and is given no room for one -- see the sidebar, which
	// is labels the whole way down.
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

	// Whether this layer added the entry itself, rather than having an opinion about one a layer
	// below holds. An own add comes off with a cross rather than an eye: there is nothing under
	// it to hide it *from*, so changing your mind about your own row means gone.
	is_own_add() {
		return false;
	}

	// The eye, which is the whole of hide and show for an entry a lower layer holds: one list,
	// one control, and a row that keeps its place either way.
	visibility_button(key) {
		const hidden = this.hidden.has(key);
		let $btn = $(
			`<button class="ws-item-eye" title="${
				hidden ? __("Show") : __("Hide")
			}">${frappe.utils.icon(hidden ? "eye-off" : "eye", "sm")}</button>`
		);
		$btn.on("click", () => this.toggle(key));
		return $btn;
	}

	// The cross, for a row this layer added. Hiding it would store "this layer holds an entry it
	// does not show", which is a sentence with no meaning -- the entry exists only because this
	// layer says so.
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

	// Take an own-added entry off the arrangement entirely.
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

	// Take an entry off the surface. Hidden rather than dropped, because the arrangement is
	// stored whole: a row simply left out would keep whatever the layer below said about it and
	// go on rendering.
	hide(key) {
		this.hidden.add(key);
	}

	// One entry as it will read on the surface. A surface whose entries do not all draw the same
	// way overrides it -- see the sidebar, where a section header is a header and not a link.
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
		// a layer switch re-renders, and the list it was bound to is gone
		if (this.sortable) this.sortable.destroy();

		this.sortable = new Sortable(this.$arrangement[0], {
			handle: ".ws-item-handle",
			animation: 150,
			ghostClass: "ws-item-ghost",
			// the preview is what the drag was for, so it follows the drop rather than waiting
			// for a save -- and the list is redrawn with it, because a surface may have read
			// something into where the entry landed
			onUpdate: (evt) => {
				this.sync_order();
				this.on_move($(evt.item).attr("data-key"));
				this.render_panes();
			},
		});
	}

	// The arrangement on screen as stored rows: every entry, in the order the list holds it,
	// each carrying whether the eye has it off. An entry left out is stored rather than simply
	// omitted -- omitted, it would keep whatever the layer below said about it and go on
	// rendering.
	//
	// `row(key, hidden)` is the only part a surface has to supply, because what a stored row
	// looks like is the one thing the two of them do not share.
	arranged_rows(row) {
		return this.order.map((key) => row(key, this.hidden.has(key) ? 1 : 0));
	}

	sync_order() {
		this.order = $.map(this.$arrangement.find(".ws-item"), (el) => $(el).attr("data-key"));
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
