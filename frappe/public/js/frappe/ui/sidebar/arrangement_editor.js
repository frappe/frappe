// One editor over the arrangements a navigation surface has.
//
// There are two surfaces, and both are the same thing: an ordered list of entries that more than
// one party can arrange. The dock belongs to an app and runs along the side of the screen; a
// Sidebar belongs to a module. Each is stored in two writable layers: every user has their own,
// and a curator can switch to the site's, which everyone sees and on top of which each user's own
// layer is applied. That is all the layer switch changes: both layers hold the same rows, arranged
// the same way, saved through endpoints that differ only in where they write.
//
// The editor is drawn on the surface itself, so the surface is its own preview. A sidebar is
// edited in its own column: the header names the layer after the module, as in "Stock for
// everyone", and the footer holds Cancel and Save. The list holds every entry the surface offers,
// in one order. Fields for one entry, and the form that adds one, open in a panel beside the
// surface, level with the row they belong to.
//
// An untouched layer starts from the layer below it, as that layer renders. A save writes the
// whole slice, so seeding from anything else would silently un-hide what a lower layer hid. The
// rule is stated here even though each surface implements it differently: the dock works it out in
// the client, and the sidebar is given it by its read endpoint.
//
// A surface supplies little: what its layers read, save and reset through, what its entries are
// and what keys them, how an entry draws, and any per-entry fields a user may set. The layer
// switch, the list, the panel and the persistence live here.

// The anchor the Add form opens against, which is the "+ Add" row rather than an entry.
const ADD_ANCHOR = "__add";

// The parts of a row that are controls of their own, rather than the row to drag or open.
const ROW_CONTROLS = ".ws-row-controls, .ws-fold";

frappe.ui.ArrangementEditor = class ArrangementEditor {
	// Open a surface's editor, unless one is already open. Two editors cannot share the column, so
	// opening the other one leaves the first, asking about its unsaved changes as leaving does.
	static start(Surface, opts) {
		if (frappe.is_mobile()) return;

		const current = frappe.ui.ArrangementEditor.current;
		if (!current) return new Surface(opts);
		if (current instanceof Surface) return current;

		current.leave(() => new Surface(opts), { on_stay: () => {} });
	}

	constructor(opts = {}) {
		this.opts = opts;
		this.make();
	}

	// -------------------------------------------------------------------------------------------
	// What a surface supplies. Everything below this block is the same for both surfaces.
	// -------------------------------------------------------------------------------------------

	// `{user: {read, save, saved(), label(), phrase(), condition?}, site: {...}}`: where a layer is
	// read from, where it is written back to, what to call it in the switch menu and after the
	// surface's name ("for everyone"), and what to say once it lands. A layer whose `condition`
	// returns false is not offered.
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

	// Whatever a surface needs resolved before the editor is drawn: its subject and its gates.
	prepare() {}

	// What is being edited, as the prompt on leaving names it.
	title() {
		return __("this arrangement");
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

	// What Reset in the footer menu does. The two surfaces mean different things by it, so neither
	// inherits the other's.
	reset() {}

	// Whether this surface's layers may add an entry rather than only order and hide the ones the
	// base gave them. `frappe.desk.layers` sets the rule: the base adds, orders and hides, and the
	// layers above order and hide. A sidebar is the exception, because a `Custom Sidebar` row can
	// carry an item of its own. A dock row cannot; it names something the app already shipped.
	can_add() {
		return false;
	}

	// Open the Add form. Only reached when `can_add()` allows it.
	add() {}

	// Open the fields of one entry. A surface whose entries have none leaves this alone, and
	// clicking a row then does nothing.
	edit_entry() {}

	// The wording, one place per surface. The base reads `add_label`, `list_empty` and
	// `load_error`. A surface may add more for its own use, which is where the sidebar's Reset
	// keeps its confirmation text.
	copy() {
		return {};
	}

	// How one entry draws inside its row, as a jQuery node.
	row_content(key) {
		const entry = this.entries.get(key);
		return $(`<span class="ws-row-label">${frappe.utils.escape_html(entry.label)}</span>`);
	}

	// Extra classes on a row, for anything a surface draws differently.
	row_classes() {
		return "";
	}

	// Rows moved along with this one when it is dragged. See the sidebar, where a section carries
	// the entries under it.
	carried() {
		return [];
	}

	// Actions in the footer menu besides Reset, for things one surface has and the other does not.
	// Each is a `frappe.ui.Dropdown` row.
	extra_menu_items() {
		return [];
	}

	// Plain text for the layer switch's tooltip, for reporting rather than for acting on. Empty by
	// default, because most surfaces have nothing to report.
	layer_note() {
		return "";
	}

	// Whether this layer added the entry itself, rather than overriding one a lower layer holds.
	// An entry this layer added is deleted by its cross: there is nothing below it to hide it
	// from, so changing your mind about your own row means deleting it.
	is_own_add() {
		return false;
	}

	// Whether an entry a lower layer holds carries the cross here.
	can_remove() {
		return false;
	}

	// Whether an entry is shown in the list at all. A surface where taking an entry off removes it
	// from view, rather than dimming it in place, leaves the hidden ones out.
	is_listed() {
		return true;
	}

	// Whether an entry is arranged here but never taken off, so it carries no cross.
	is_pinned() {
		return false;
	}

	// One entry was dragged to a new place. A surface where position means more than order handles
	// that here. See the sidebar, where the drop position decides which section an entry is in.
	on_move() {}

	// Whether the editor stays open when the desk moves to `shell`. Moving somewhere that does not
	// show what is being edited leaves it. See `leave`.
	survives_shell() {
		return false;
	}

	// Where the editor draws: the sidebar's column, which it takes over until it closes.
	mount() {
		return frappe.app.sidebar.begin_editing(this);
	}

	unmount() {
		frappe.app.sidebar.end_editing(this);
	}

	// Where the layer's phrase goes: after the module's name in the sidebar header.
	layer_slot() {
		return frappe.app.sidebar.sidebar_header?.layer_slot();
	}

	// What the sidebar header's menu offers while this is open, or null for its usual rows. Only the
	// phrase takes the pointer while editing, so this is what the header gives the keyboard.
	header_menu_items() {
		return this.layer_menu();
	}

	// Which side of the phrase the layer menu opens on.
	layer_menu_side() {
		return "bottom";
	}

	// The element a panel opens beside.
	panel_edge() {
		return this.$frame.closest(".body-sidebar")[0];
	}

	// Called once a layer has been read and before it is drawn, with the read arrangement already
	// recorded as the saved one, so a change made here counts as unsaved.
	on_load() {}

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

		frappe.ui.ArrangementEditor.current = this;
		this.$frame = this.mount();
		this.render_frame();
		this.load();
	}

	render_frame() {
		this.$frame.html(`
			<div class="ws-scroll">
				<div class="ws-list"></div>
				<div class="ws-add-slot"></div>
			</div>
			<div class="ws-foot"></div>
		`);
		this.$list = this.$frame.find(".ws-list");
		this.$scroll = this.$frame.find(".ws-scroll");
		this.$add_slot = this.$frame.find(".ws-add-slot");

		this.render_layer_switch();
		this.render_footer();
		this.bind_keys();
	}

	bind_keys() {
		// Esc closes the panel, and nothing else: leaving the editor is Cancel's job, and a key that
		// threw away unsaved work by accident would cost more than one that did nothing.
		$(document)
			.off("keydown.arrangement-editor")
			.on("keydown.arrangement-editor", (e) => {
				if (e.key === "Escape" && this.panel && !e.isDefaultPrevented()) {
					this.close_panel();
				}
			});
	}

	render_footer() {
		const $foot = this.$frame.find(".ws-foot").empty();

		const $more = frappe.ui.button({
			icon: "ellipsis",
			variant: "ghost",
			title: __("More actions"),
			css_class: "ws-more",
		});
		new frappe.ui.Dropdown({
			trigger: $more,
			side: "top",
			options: () => this.menu_items(),
		});

		this.$save = frappe.ui.button({
			label: __("Save"),
			variant: "ghost",
			disabled: !this.is_dirty(),
			onclick: () => this.save(),
		});

		$foot.append(
			$more,
			`<span class="ws-foot-spacer"></span>`,
			frappe.ui.button({
				label: __("Cancel"),
				variant: "ghost",
				onclick: () => this.cancel(),
			}),
			this.$save
		);
	}

	// Which layer is on screen, which is also where Save writes, as words that finish the
	// surface's name. The chevron says there are others to switch to; without the right to write a
	// second layer there is nothing to choose. What that right is belongs to the endpoints, which
	// check it again.
	//
	// It is drawn once per session and only its words change after that, because its menu and
	// tooltip are bound to the node.
	render_layer_switch() {
		const $slot = this.layer_slot();
		if (!$slot) return;
		if (!this.$layer_switch || !$.contains($slot[0], this.$layer_switch[0])) {
			const switchable = this.offered_layers.length > 1;
			this.$layer_switch = $(`<span class="ws-layer-switch">
				<span class="ws-layer-phrase"></span>
				${switchable ? frappe.utils.icon("chevron-down", "sm") : ""}
			</span>`);
			// The phrase sits inside the sidebar header, which has a menu of its own.
			this.$layer_switch.on("pointerdown click", (e) => e.stopPropagation());
			$slot.empty().append(this.$layer_switch);
			if (switchable) {
				new frappe.ui.Dropdown({
					trigger: this.$layer_switch,
					side: this.layer_menu_side(),
					options: () => this.layer_menu(),
				});
			}
		}
		this.$layer_switch.find(".ws-layer-phrase").text(this.layer_config.phrase());
	}

	// What the layer switch says on hover, read again with each layer.
	render_layer_note() {
		const note = this.layer_note();
		this.layer_tooltip?.destroy();
		this.layer_tooltip = null;
		if (!note || !this.$layer_switch) return;
		this.layer_tooltip = new frappe.ui.Tooltip(this.$layer_switch[0], {
			text: note,
			side: this.layer_menu_side(),
			text_align: "start",
		});
	}

	layer_menu() {
		return [
			{
				group: __("Editing for"),
				options: this.offered_layers.map(([name, layer]) => ({
					label: layer.label(),
					selected: name === this.layer,
					onclick: () => this.switch_layer(name),
				})),
			},
		];
	}

	menu_items() {
		return [
			{
				label: __("Reset"),
				icon: "rotate-ccw",
				description: this.copy().reset_title,
				onclick: () => this.reset(),
			},
			...this.extra_menu_items(),
		];
	}

	// A value naming no layer, and the layer already on screen, are both non-switches. Treating
	// either as a switch would re-read the arrangement for nothing, and the first would also leave
	// `this.layer` naming a layer that does not exist, making every read through `layer_config`
	// undefined.
	//
	// The other layer is a different arrangement, so what was changed on this one would be lost.
	switch_layer(layer) {
		if (!this.layers[layer] || layer === this.layer) return;

		const go = () => {
			this.layer = layer;
			this.render_layer_switch();
			this.load();
		};
		if (!this.is_dirty()) return go();

		frappe.confirm(
			__("Switch to {0}? Your changes to this arrangement are not saved.", [
				frappe.utils.escape_html(this.layers[layer].label()),
			]),
			go
		);
	}

	get layer_config() {
		return this.layers[this.layer];
	}

	async load() {
		this.loaded = false;
		this.close_panel();
		this.$add_slot.empty();
		this.render_loading();
		this.update_dirty();

		try {
			await this.read();
		} catch (e) {
			// Report the failure rather than sit on "Loading..." forever. `loaded` stays false, so
			// Save and every other action do nothing, since none should act on an arrangement that
			// was never read.
			console.error("Arrangement editor: could not read the arrangement", e);
			this.$list.html(`<div class="ws-empty">${this.copy().load_error}</div>`);
			return;
		}

		this.loaded = true;
		this.saved_args = this.args_signature();
		this.on_load();
		this.render_body();
	}

	render_loading() {
		this.$list.html(`<div class="ws-empty">${__("Loading...")}</div>`);
	}

	render_body() {
		this.render_layer_note();

		const $slot = this.$add_slot.empty();
		if (this.can_add()) {
			this.$add = $(`<button type="button" class="ws-add-row" data-key="${ADD_ANCHOR}">
				${frappe.utils.icon("plus", "sm")}
				<span>${frappe.utils.escape_html(this.copy().add_label)}</span>
			</button>`);
			this.$add.on("click", () => {
				if (this.panel?.key === ADD_ANCHOR) this.close_panel();
				else this.add();
			});
			$slot.append(this.$add);
		}

		this.render_list();
		this.setup_sortable();
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

	// What is on the surface, in order: the arrangement minus what has been taken off. Every
	// surface uses this rather than reading `order`, because it is the arrangement as it renders.
	get selection() {
		return this.order.filter((key) => !this.hidden.has(key));
	}

	render_list() {
		this.$list.empty();
		const listed = this.order.filter((key) => this.is_listed(key));
		if (!listed.length) {
			this.$list.append(`<div class="ws-empty">${this.copy().list_empty}</div>`);
		}
		listed.forEach((key) => this.$list.append(this.list_row(key)));

		this.$add?.toggleClass("is-open", this.panel?.key === ADD_ANCHOR);
		this.update_dirty();
		this.panel?.place();
	}

	list_row(key) {
		const $row = $(`<div class="ws-row ${this.row_classes(key)}"></div>`)
			.attr("data-key", key)
			.toggleClass("is-hidden", this.hidden.has(key))
			.toggleClass("is-open", this.panel?.key === key);

		$row.append($(`<div class="ws-row-body"></div>`).append(this.row_content(key)));

		const $controls = $(`<span class="ws-row-controls"></span>`);
		if (this.is_own_add(key) || (!this.is_pinned(key) && this.can_remove(key))) {
			$controls.append(this.remove_button(key));
		}
		$row.append($controls);

		$row.on("click", (e) => {
			if (this.dragged || $(e.target).closest(ROW_CONTROLS).length) return;
			if (this.panel?.key === key) this.close_panel();
			else this.edit_entry(key);
		});
		return $row;
	}

	// The cross, for a row this layer added. Hiding it would store a layer holding an entry it
	// does not show, which means nothing: the entry exists only because this layer names it.
	remove_button(key) {
		return frappe.ui.button({
			icon: "x",
			variant: "ghost",
			size: "xs",
			title: __("Remove"),
			css_class: "ws-remove",
			onclick: () => this.remove(key),
		});
	}

	// Remove an entry this layer added from the arrangement entirely.
	remove(key) {
		if (this.panel?.key === key) this.close_panel();
		this.entries.delete(key);
		this.order = this.order.filter((k) => k !== key);
		this.hidden.delete(key);
		this.render_list();
	}

	// Take an entry off the surface. It is hidden rather than dropped, because the arrangement is
	// stored whole: a row left out would keep whatever the layer below said about it and keep
	// rendering.
	hide(key) {
		this.hidden.add(key);
	}

	setup_sortable() {
		// A layer switch re-renders, so the list it was bound to is gone.
		if (this.sortable) this.sortable.destroy();

		// The whole row is what is dragged, except its own controls, which stay clickable.
		this.sortable = new Sortable(this.$list[0], {
			draggable: ".ws-row",
			filter: ROW_CONTROLS,
			preventOnFilter: false,
			animation: 150,
			ghostClass: "ws-row-ghost",
			onStart: (evt) => {
				this.dragged = true;
				const key = $(evt.item).attr("data-key");
				this.carried_keys = this.carried(key);
				this.row_nodes(this.carried_keys).addClass("ws-row-carried");
			},
			onEnd: (evt) => {
				const key = $(evt.item).attr("data-key");
				if (evt.oldIndex !== evt.newIndex) {
					this.sync_order(key);
					this.on_move(key);
				}
				this.carried_keys = [];
				this.render_list();
				// The release that ends a drag is also a click, which is not a request to open
				// the row it landed on.
				setTimeout(() => (this.dragged = false));
			},
		});
	}

	// The rows for some keys. Keys hold characters a selector would need escaping for, so the rows
	// are matched by attribute value instead.
	row_nodes(keys) {
		const wanted = new Set(keys);
		return this.$list.find(".ws-row").filter((_, el) => wanted.has(el.dataset.key));
	}

	// The list as the drop left it. Rows carried along with the dragged one stayed where they were
	// in the document while hidden, so they are put back directly under it. Entries the list does
	// not show keep the places they had, so a drag cannot drop them from the arrangement.
	sync_order(moved) {
		const carried = new Set(this.carried_keys || []);
		const dropped = $.map(this.$list.find(".ws-row"), (el) => el.dataset.key).filter(
			(key) => !carried.has(key)
		);
		dropped.splice(dropped.indexOf(moved) + 1, 0, ...(this.carried_keys || []));
		this.order = this.order.map((key) => (this.is_listed(key) ? dropped.shift() : key));
	}

	// The arrangement on screen as stored rows: every entry, in the order the list holds it, each
	// carrying whether it was taken off. An entry taken off is stored as hidden rather than
	// omitted, because an omitted row would keep whatever the layer below said about it and keep
	// rendering.
	//
	// `row(key, hidden)` is the only part a surface supplies, because the shape of a stored row is
	// the one thing the two surfaces do not share.
	arranged_rows(row) {
		return this.order.map((key) => row(key, this.hidden.has(key) ? 1 : 0));
	}

	// What Save would send, as one string, so an arrangement can be compared with the one read.
	args_signature() {
		return JSON.stringify(this.save_args());
	}

	is_dirty() {
		return !!this.loaded && this.args_signature() !== this.saved_args;
	}

	update_dirty() {
		this.$save?.prop("disabled", !this.is_dirty());
	}

	// -------------------------------------------------------------------------------------------
	// The panel beside the column
	// -------------------------------------------------------------------------------------------

	// Open a panel of fields beside the column, level with the row `key` names. `on_change` is
	// called with the panel's values whenever one changes, for fields that apply as they are
	// edited; `primary` adds a button that acts on them, for a form such as Add. `choice` names a
	// Select field to draw as a row of pills over the others, for a form that starts from a kind.
	// `actions` are buttons for the header, beside the close button.
	open_panel({ key, title, fields, on_change, primary_label, primary, choice, actions }) {
		this.close_panel();
		this.panel = new frappe.ui.ArrangementPanel({
			editor: this,
			key,
			title,
			fields,
			on_change,
			primary_label,
			primary,
			choice,
			actions,
		});
		this.render_list();
		return this.panel;
	}

	open_add_panel(opts) {
		return this.open_panel({ key: ADD_ANCHOR, primary_label: __("Add"), ...opts });
	}

	close_panel() {
		if (!this.panel) return;
		this.panel.destroy();
		this.panel = null;
		this.$list?.find(".ws-row.is-open").removeClass("is-open");
		this.$add?.removeClass("is-open");
	}

	// The node a panel is level with: the row it edits, or the Add row.
	anchor_node(key) {
		if (key === ADD_ANCHOR) return this.$add;
		return this.row_nodes([key]).first();
	}

	// -------------------------------------------------------------------------------------------
	// Leaving
	// -------------------------------------------------------------------------------------------

	cancel() {
		if (!this.is_dirty()) return this.close();
		frappe.confirm(__("Discard your changes?"), () => this.close());
	}

	close() {
		this.close_panel();
		if (this.sortable) this.sortable.destroy();
		this.sortable = null;
		$(document).off("keydown.arrangement-editor");
		this.layer_tooltip?.destroy();
		this.layer_slot()?.empty();
		this.unmount();
		if (frappe.ui.ArrangementEditor.current === this)
			frappe.ui.ArrangementEditor.current = null;
	}

	// The desk is moving somewhere that does not show what is being edited. Nothing unsaved means
	// nothing to ask, so the editor closes and the move goes ahead. Otherwise the person chooses:
	// save and go, go without saving, or stay. Staying undoes the navigation that asked, which is
	// what `on_stay` does unless the caller was not a navigation.
	leave(proceed, { on_stay = () => window.history.back() } = {}) {
		if (this.leaving) return;
		if (!this.is_dirty()) {
			this.close();
			proceed();
			return;
		}

		this.leaving = true;
		let decided = false;
		const dialog = new frappe.ui.Dialog({
			title: __("Save your changes?"),
			fields: [
				{
					fieldtype: "HTML",
					options: `<p class="text-muted">${__(
						"You are leaving {0}, and your changes to it are not saved.",
						[frappe.utils.escape_html(this.title())]
					)}</p>`,
				},
			],
			primary_action_label: __("Save"),
			primary_action: async () => {
				decided = true;
				dialog.hide();
				// A save that is refused or fails leaves the person where their changes are.
				const saved = await this.save().catch(() => false);
				if (saved) proceed();
				else on_stay();
			},
			secondary_action_label: __("Discard"),
			secondary_action: () => {
				decided = true;
				dialog.hide();
				this.close();
				proceed();
			},
		});
		dialog.add_custom_action(__("Stay"), () => dialog.hide());
		dialog.onhide = () => {
			this.leaving = false;
			if (!decided) on_stay();
		};
		dialog.show();
	}

	// Returns whether it saved, so leaving knows whether to go on.
	async save() {
		// The layer arrives after the editor opens. Saving before it lands would overwrite the
		// stored arrangement with one nobody has seen.
		if (!this.loaded || this.saving) return false;
		this.saving = true;
		this.$save?.attr("aria-busy", "true");

		try {
			const result = await frappe.xcall(this.layer_config.save, this.save_args());
			const message = this.layer_config.saved();
			this.close();
			this.apply(result);
			frappe.show_alert({ message, indicator: "green" });
			return true;
		} finally {
			this.saving = false;
			this.$save?.removeAttr("aria-busy");
		}
	}
};

// A panel of fields beside the surface, level with the row it belongs to. It follows the
// row as the list scrolls and as the list is redrawn, and closes when the row is no longer shown.
//
// It is drawn as an espresso popover (`.es-popover`), but placed and closed here rather than by
// `frappe.ui.Popover`. That one is tied to a trigger element it owns, and the row this belongs to
// is redrawn on every change. It also closes on any click outside it, which would include the
// pickers its own fields open.
frappe.ui.ArrangementPanel = class ArrangementPanel {
	constructor({
		editor,
		key,
		title,
		fields,
		on_change,
		primary_label,
		primary,
		choice,
		actions,
	}) {
		Object.assign(this, {
			editor,
			key,
			title,
			fields,
			on_change,
			primary_label,
			primary,
			choice,
			actions,
		});
		this.make();
	}

	make() {
		this.$wrapper = $(`<div class="es-popover ws-panel" role="dialog" tabindex="-1"
			data-side="right" data-align="start">
			<div class="ws-panel-head"><span class="es-popover__title ws-panel-title"></span></div>
			<div class="ws-panel-body"></div>
			<div class="ws-panel-foot"></div>
		</div>`).appendTo(document.body);
		this.$wrapper.attr("aria-label", this.title);
		this.$wrapper.find(".ws-panel-title").text(this.title);
		this.$wrapper.find(".ws-panel-head").append(
			...(this.actions || []),
			frappe.ui.button({
				icon: "x",
				variant: "ghost",
				title: __("Close"),
				onclick: () => this.editor.close_panel(),
			})
		);

		// Changes are passed on only once the defaults are in. They are set a field at a time, and
		// a value read in between is missing the fields not set yet, which would read as those
		// fields having been cleared.
		this.ready = false;
		const defaults = {};
		const fields = this.fields.map(({ default: value, ...df }) => {
			if (df.fieldname && value !== undefined) defaults[df.fieldname] = value;
			if (this.choice && df.fieldname === this.choice) return { ...df, hidden: 1 };
			return this.on_change && df.fieldname
				? { ...df, change: () => this.ready && this.changed() }
				: df;
		});
		this.field_group = new frappe.ui.FieldGroup({
			fields,
			body: this.$wrapper.find(".ws-panel-body")[0],
			no_submit_on_enter: true,
		});
		this.field_group.make();
		this.field_group.set_values(defaults).then(() => {
			this.field_group.refresh_dependency();
			this.ready = true;
		});
		if (this.choice) this.make_choice();

		if (this.primary) {
			const submit = () => this.primary(this.field_group.get_values(true), this.field_group);
			this.$wrapper.find(".ws-panel-foot").append(
				frappe.ui.button({
					label: this.primary_label,
					variant: "ghost",
					onclick: submit,
				})
			);
			this.$wrapper.on("keydown", "input", (e) => {
				if (e.key === "Enter" && !e.isDefaultPrevented()) {
					e.preventDefault();
					submit();
				}
			});
		}

		this.place = this.place.bind(this);
		this.editor.$scroll.on("scroll.ws-panel", this.place);
		$(window).on("resize.ws-panel", this.place);
		this.observer = new ResizeObserver(this.place);
		this.observer.observe(this.$wrapper[0]);

		this.place();
		this.$wrapper.attr("data-state", "open");
		this.field_group.focus_on_first_input();
	}

	changed() {
		this.on_change(this.field_group.get_values(true), this.field_group);
	}

	// The `choice` field as pills over the form. The field itself stays, hidden, so the others'
	// `depends_on` still read it.
	make_choice() {
		const df = this.fields.find((f) => f.fieldname === this.choice);
		const pills = new frappe.ui.TabButtons({
			label: df.label,
			options: df.options.map(({ label, value }) => ({ label, value })),
			value: df.default,
			on_change: (value) => this.field_group.set_value(df.fieldname, value),
		});
		pills.el.classList.add("ws-panel-choice");
		this.$wrapper.find(".ws-panel-body").prepend(pills.el);
	}

	// Mark the fields a form cannot go without, once it is submitted without them rather than as
	// soon as it opens. Returns whether any were missing.
	flag_missing(fieldnames) {
		this.flagged = this.flagged || new Set();
		for (const field of this.field_group.fields_list) {
			const name = field.df.fieldname;
			const missing = fieldnames.includes(name);
			if (!missing && !this.flagged.has(name)) continue;

			field.$wrapper.toggleClass("has-error", missing);
			if (missing) {
				this.flagged.add(name);
				field.set_new_description(__("Required"));
			} else {
				this.flagged.delete(name);
				field.set_new_description(field.df.description || "");
				if (!field.df.description) field.toggle_description(false);
			}
		}
		return fieldnames.length > 0;
	}

	// Beside the surface, with its top level with the row, kept on screen.
	place() {
		const $anchor = this.editor.anchor_node(this.key);
		if (!$anchor?.length || !$anchor.is(":visible")) {
			this.editor.close_panel();
			return;
		}

		const column = this.editor.panel_edge().getBoundingClientRect();
		const row = $anchor[0].getBoundingClientRect();
		const height = this.$wrapper.outerHeight();
		const top = Math.max(8, Math.min(row.top - 12, window.innerHeight - height - 8));
		this.$wrapper.css({ top, left: column.right + 8 });
	}

	// The popover's exit animation plays first. While it fades it is no longer the panel, so the
	// next one opened meanwhile is the only `.ws-panel`.
	destroy() {
		this.observer?.disconnect();
		this.editor.$scroll?.off("scroll.ws-panel");
		$(window).off("resize.ws-panel");
		const $wrapper = this.$wrapper
			.attr("data-state", "closed")
			.removeClass("ws-panel")
			.addClass("ws-panel-closing");
		setTimeout(() => $wrapper.remove(), 150);
	}
};
