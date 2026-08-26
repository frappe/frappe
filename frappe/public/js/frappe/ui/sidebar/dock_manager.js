// The dock's arrangement, in the editor every navigation surface shares
// (`frappe.ui.ArrangementEditor`, which holds the layer switch, the list, the eye and the
// persistence). This is only what the dock is: what its entries are, where its two layers live,
// and the one action it has that a sidebar does not.
//
// The dock it arranges is the one for the app you're currently in: which of that app's entries
// appear on it, and in what order.
//
// An entry is a typed pair -- a `Sidebar` (a module) or a `Workspace` (one of the app's own, or
// one a companion app pinned onto it) -- and both kinds are arranged the same way, because a pin
// is an entry on the dock rather than a fixture on it.
//
// On a developer's site it also authors the layer *below* both stored ones: "Ship This Order"
// hands you the `add_to_dock` block for the arrangement on screen, to paste into the app's
// `hooks.py`. It writes nothing -- the last inch is given up on purpose, because the target is
// hand-authored Python and the drag-and-drop is where the value was. Not a third layer either:
// the two layers rearrange the list an app ships, and this is that list.
//
// One app on purpose -- a dock belongs to an app, so there's nothing to choose between here and
// no app switcher. Modules in other apps are managed from those apps' docks.

// What differs between the dock's two layers, in one place: where the arrangement is read from,
// where it is written back to, and what to say once it lands. Everything else -- the picker, the
// app slice, the shape of a saved row -- is the same work either way.
// Making a module the site is adding for itself. It creates the workspace that keeps the module
// reachable along with it -- see the endpoint, which explains why the two are one action.
const RESET_FOR_EVERYONE = "frappe.desk.doctype.dock.dock.reset_dock_for_everyone";

const DOCK_LAYERS = {
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

frappe.ui.DockManager = class DockManager extends frappe.ui.ArrangementEditor {
	get layers() {
		return DOCK_LAYERS;
	}

	prepare() {
		// The dock renders for `get_sidebar_app()` (the shown sidebar's app), so curate that one.
		// It is also the only app context there is -- a module belonging to no app has no dock to
		// arrange, which is why the user menu doesn't offer this there.
		this.app = frappe.app.sidebar.get_sidebar_app();
		this.base_hidden = new Set();
		// Shipping hands you Python for an app's `hooks.py`, so it is offered where app content is
		// authored at all -- a developer's site -- and nowhere else. Not a role: the two layers
		// above are what a site rearranges, and neither of them needs this. The gate is kept for
		// meaning rather than for safety, now that the call is a read.
		this.can_ship = !!(frappe.boot.developer_mode && this.app);
	}

	title() {
		return this.app ? __("Manage {0} Dock", [__(this.app.app_title)]) : __("Manage Dock");
	}

	extra_actions() {
		return this.can_ship
			? {
					secondary_action_label: __("Ship This Order"),
					secondary_action: () => this.ship(),
			  }
			: {};
	}

	copy() {
		return {
			list_head: __("Entries"),
			add_label: __("Add"),
			list_sub: __("Drag to reorder. The eye takes an entry off the dock."),
			reset_title: __("Bring every entry back onto the dock."),
			list_empty: __("This app has nothing to arrange"),
			preview_head: __("Preview"),
			preview_sub: __("The dock as this arrangement leaves it."),
			preview_empty: __("Nothing on the dock"),
			load_error: __("Could not load the dock. Please try again."),
		};
	}

	// Load the layer being edited -- its own stored rows, not the resolved rail in
	// `frappe.boot.dock`. A save replaces the layer whole, so it has to be shown
	// what it will overwrite: shown the resolved rail, saving as a user would copy the site's
	// rows into their own layer and freeze them out of every later site change.
	//
	// Every read names the app, because a layer is one app's: reading without one would be
	// asking for an arrangement that no longer exists.
	async read() {
		// A dock belongs to an app and every read names one, so there is nothing to read without
		// it. The user menu already hides this surface where there is no app context; saying so
		// here is what keeps a hand-opened manager on the load error instead of on a failed call.
		if (!this.app) throw new Error("Manage Dock: no app in context");

		this.load_entries();

		const args = { app: this.app.app_name };
		const [layer, base] = await Promise.all([
			frappe.xcall(this.layer_config.read, args),
			frappe.xcall("frappe.desk.doctype.dock.dock.get_app_dock_layer", args),
		]);

		this.layer_rows = layer;
		// Which of these rows this layer added itself, so they carry a cross rather than an eye.
		// Read off the stored layer rather than guessed from the entry: an entry a *lower* layer
		// added is a reference from here, and hiding is the right control for it.
		this.own_adds = new Set(
			(layer || []).filter((row) => row.added).map((row) => this.key(row))
		);
		// What the apps ship, so a row the app itself hid can say so. "Hidden" is otherwise
		// silent about who hid it, and un-hiding an app's deliberate default should be a choice
		// rather than an accident.
		this.base_hidden = new Set(
			(base || []).filter((row) => row.hidden).map((row) => this.key(row))
		);
		// Only what this layer put on the dock is named; everything else the app offers follows
		// it in the app's own order, with the eye off.
		this.arrange(this.initial_selection());
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

	// What identifies an entry here, on the server and on the rail: the typed pair. Both halves,
	// because a `Sidebar` and a `Workspace` of one name are two entries.
	key(row) {
		return frappe.app.sidebar.dock_key(row);
	}

	// This layer's picks, in their order. The layer is this app's, so every row in it is about
	// this app -- the filter is against what the app still offers, not against whose app a row is.
	initial_selection() {
		const mine = new Set(this.all_keys());
		const arranged = (this.layer_rows || [])
			.filter((row) => !row.hidden && mine.has(this.key(row)))
			.map((row) => this.key(row));
		return arranged.length ? arranged : this.unarranged_selection();
	}

	// One row as a layer stores it, from the key the panes work in. The whole destination, and
	// nothing about how it reads -- an entry this layer has no opinion about inherits its icon
	// and title from the layer below.
	stored_row(key, hidden) {
		const entry = this.entries.get(key);
		return {
			sidebar: entry.sidebar,
			link_type: entry.link_type,
			link_to: entry.link_to,
			url: entry.url,
			hidden,
		};
	}

	// Where an untouched layer starts, so the arrangement is a trim rather than a build from
	// scratch. It has to start from what saving unchanged would produce, because a save writes
	// the whole app slice: seeded with everything the app offers, whoever merely opens this and
	// saves would write `hidden: 0` over what a layer below deliberately hid, un-hiding it
	// without ever asking to.
	//
	// Both layers therefore start from the layer *below* them, as that layer renders:
	//
	//   - the user's starts from the dock on screen -- the app's order with the site's
	//     arrangement applied
	//   - the site's starts from the base as it renders -- the app's entries minus the ones the
	//     app ships off. Never from the dock this manager happens to see, which carries their
	//     personal arrangement and is not theirs to publish.
	unarranged_selection() {
		if (this.layer === "site") {
			return this.all_keys().filter((key) => !this.base_hidden.has(key));
		}

		const shown = frappe.app.sidebar
			.collect_dock_entries(this.app)
			.map((entry) => this.key(entry));
		return shown.length ? shown : this.all_keys();
	}

	// Both upper layers may add an entry -- the server's bound is **reach**, never base
	// membership, so a person may put on their rail anything they can already navigate to.
	// The dialog that does it is ticket 14's; until it lands there is nothing here to open, and
	// offering a button that does nothing would be worse than not offering one.
	can_add() {
		return false;
	}

	is_own_add(key) {
		return this.own_adds.has(key);
	}

	// A row the app itself ships off says so. The eye is still all it takes to bring it back --
	// an off-by-default is a default, not a decision made for you.
	item_extras(key) {
		return this.base_hidden.has(key)
			? `<span class="ws-item-chip">${__("app ships this off")}</span>`
			: "";
	}

	// An empty selection isn't stored as "an empty dock": it is saved as no rows at all, which
	// is what this layer says when it has nothing to say -- so Reset here is a reset to the layer
	// below (the site's, or the app's own dock), and it takes effect on the next Save like every
	// other edit in the panes.
	//
	// Rows this layer added go too, not just off the rail. There is nothing below them to fall
	// back to, so leaving one behind hidden would keep a row nobody can see and nobody can
	// explain.
	reset() {
		this.own_adds.forEach((key) => this.remove(key));
		if (!this.selection.length) return;
		this.hidden = new Set(this.all_keys());
		this.render_panes();
	}

	// Drop every non-standard dock for this app -- the site's own layer included -- so everybody
	// is back on the app's exported dock.
	//
	// The one act that reaches past the site layer, and the reason it exists: a Workspace Manager
	// who re-curates the site's rail reaches nobody who has arranged their own. Immediate and
	// confirmed rather than a pane edit applied on Save, because it is not an edit to the
	// arrangement in front of them -- it is a decision about everybody else's.
	async reset_for_everyone() {
		frappe.confirm(
			__(
				"This drops the dock arrangement of every person on this site for {0}, and the site's own, back to what the app ships. It cannot be undone.",
				[frappe.utils.escape_html(this.app.app_title || this.app.app_name)]
			),
			async () => {
				this.apply(await frappe.xcall(RESET_FOR_EVERYONE, { app: this.app.app_name }));
				this.dialog.hide();
				frappe.show_alert({
					message: __("Everyone is back on the dock this app ships"),
					indicator: "green",
				});
			}
		);
	}

	save_args() {
		// The layer is this app's, so what is on screen is the whole of it. The old
		// carry-the-other-apps-rows-through dance went with the flat list: a save touches one
		// document, and that document holds one app's rows.
		//
		// Nothing selected at all is Reset: it stores no row, so the layer below shows through
		// instead of the app being hidden entry by entry.
		const mine = this.selection.length
			? this.arranged_rows((key, hidden) => this.stored_row(key, hidden))
			: [];

		return { app: this.app.app_name, items: JSON.stringify(mine) };
	}

	// Both saves answer with this app's resolved rail -- its own dock with the site's arrangement
	// and this user's own on top -- so the rail can be redrawn in place whichever layer was
	// written. Only this app's key is replaced, because only this app's document was saved.
	apply(rail) {
		frappe.boot.dock = { ...(frappe.boot.dock || {}), [this.app.app_name]: rail };
		frappe.app.sidebar.refresh_dock();
	}

	// Hand the author the block for the arrangement on screen. No confirm: nothing is written,
	// so there is nothing to agree to -- the old one described a write that no longer happens.
	//
	// Every entry the manager showed is named: the ones on the dock as positions, the ones the eye
	// has off as hidden. That is what makes ship round-trip -- paste, restart, and the dock renders
	// the screen it was taken from -- and it is why the hidden ones are sent too rather than just
	// what is on the dock.
	async ship() {
		if (!this.loaded) return;
		this.sync_order();

		const emitted = await frappe.xcall("frappe.desk.doctype.dock.dock.emit_dock_hook", {
			app: this.app.app_name,
			items: JSON.stringify(
				this.arranged_rows((key, hidden) => this.stored_row(key, hidden))
			),
		});

		this.show_emitted(emitted);
	}

	// A handover, not a confirm and not an editor: one line of framing, the block in a code box
	// under the path it belongs in, the rows the projection dropped and why, and a warning that
	// the block is not live until the bench restarts *and* that the arrangement it was taken from
	// is still sitting on top of it.
	show_emitted(emitted) {
		const dialog = new frappe.ui.Dialog({
			title: __("Ship This Order"),
			size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "handover" }],
		});

		const $body = $(dialog.fields_dict.handover.$wrapper);
		$body.html(`
			<div class="dock-ship">
				<p class="dock-ship-lede">${__("Paste this into {0} to ship this order with the app.", [
					`<code>${frappe.utils.escape_html(emitted.path)}</code>`,
				])}</p>
				<div class="dock-ship-code">
					<button class="dock-ship-copy btn btn-default btn-xs">${__("Copy")}</button>
					<pre>${frappe.utils.escape_html(emitted.code)}</pre>
				</div>
				${this.dropped_note(emitted.dropped)}
				<div class="dock-ship-warning">
					<p>${__(
						"The block is not live until the bench restarts -- and your own arrangement is still sitting on top of it, so the dock will keep rendering that instead."
					)}</p>
					<button class="dock-ship-clear btn btn-default btn-xs" title="${__(
						"Until the bench restarts this drops the dock back to the order the app ships today, not the block above."
					)}">${
			this.layer === "site" ? __("Clear the site's arrangement") : __("Clear my arrangement")
		}</button>
				</div>
			</div>
		`);

		$body.find(".dock-ship-copy").on("click", () => {
			frappe.utils.copy_to_clipboard(emitted.code);
		});
		// Offered *after* the paste and never fused to Ship: clearing at ship time would strand
		// the author on the unshipped dock. Reuses the ordinary clear-and-save path -- Reset,
		// then Save -- so there is no second way to empty a layer.
		$body.find(".dock-ship-clear").on("click", async () => {
			this.reset();
			await this.save();
			dialog.hide();
		});

		dialog.show();
	}

	// The projection, in one sentence carrying both halves of the rule. A dropped row is named
	// with the app that declared it, because "some rows are missing" is not something an author
	// should have to work out by diffing.
	dropped_note(dropped) {
		if (!dropped || !dropped.length) return "";

		const named = dropped
			.map((row) =>
				__("{0} (from {1})", [
					frappe.utils.escape_html(row.name),
					frappe.utils.escape_html(row.declared_by || __("another app")),
				])
			)
			.join(", ");

		return `<p class="dock-ship-dropped text-muted">${__(
			"Left out: {0}. A pinned workspace is already declared in the pinning app's own hooks.py, and a pin is appended rather than positioned -- where it sits on screen is the site's or your own arrangement, which no block can state.",
			[named]
		)}</p>`;
	}
};
