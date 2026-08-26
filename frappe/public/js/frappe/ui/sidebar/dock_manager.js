// The rail's arrangement, in the editor every navigation surface shares
// (`frappe.ui.ArrangementEditor`, which holds the layer switch, the list, the eye and the
// persistence). This is only what the dock is: what its entries are, where its three layers live,
// and the one action it has that a sidebar does not.
//
// The rail it arranges is the one for the app you are currently in. **One tool, two panes, one
// gesture per row** -- what authoring adds is a third value in the layer switch, an Add dialog
// and one action. Every alternative that made the app layer *look* different (a pool pane, a
// changed title, a coloured band, ladder tabs) was dropped, and so was every alternative that
// moved authoring out of a dialog and into the list.
//
// An entry names a shell, a page, or both, and every kind is arranged the same way -- a
// companion's entry is an entry on the rail, not a fixture on it.
//
// One app on purpose -- a dock belongs to an app, so there's nothing to choose between here and
// no app switcher. Entries in other apps are managed from those apps' rails.

// What differs between the three layers, in one place: where the arrangement is read from, where
// it is written back to, what to call it, and what to say once it lands. Everything else -- the
// list, the eye, the shape of a saved row -- is the same work whichever one is on screen.
const RESET_FOR_EVERYONE = "frappe.desk.doctype.dock.dock.reset_dock_for_everyone";
const MARK_AS_STANDARD = "frappe.desk.doctype.dock.dock.mark_as_standard";

const DOCK_LAYERS = {
	user: {
		read: "frappe.desk.doctype.dock.dock.get_user_dock_layer",
		save: "frappe.desk.doctype.dock.dock.save_user_dock",
		label: () => __("Just for me"),
		saved: () => __("Dock updated"),
	},
	site: {
		read: "frappe.desk.doctype.dock.dock.get_site_dock_layer",
		save: "frappe.desk.doctype.dock.dock.save_site_dock",
		label: () => __("For everyone"),
		condition: () => frappe.user.has_role("Workspace Manager"),
		saved: () => __("Dock updated for everyone"),
	},
	// The third value, and the whole of what the app layer looks like from here. Developer mode
	// only, because authoring what an app ships means writing a file into the app -- and only
	// where the app already ships one, since promoting is `Export to app` and that is one act
	// with the file write.
	app: {
		read: "frappe.desk.doctype.dock.dock.get_app_dock_layer",
		save: "frappe.desk.doctype.dock.dock.save_app_dock",
		label: () => __("Ship with the app"),
		condition: () => !!frappe.boot.developer_mode,
		saved: () => __("Exported to the app"),
	},
};

frappe.ui.DockManager = class DockManager extends frappe.ui.ArrangementEditor {
	get layers() {
		return DOCK_LAYERS;
	}

	prepare() {
		// The rail renders for `get_sidebar_app()` (the shown sidebar's app), so curate that one.
		// It is also the only app context there is -- a module belonging to no app has no rail to
		// arrange, which is why the user menu doesn't offer this there.
		this.app = frappe.app.sidebar.get_sidebar_app();
		this.base_hidden = new Set();
		this.own_adds = new Set();
		// Writing a file into an app is a developer's act, so the promotion is offered where app
		// content is authored at all and nowhere else. Not a role: the two layers above are what a
		// site rearranges, and neither of them needs this.
		this.can_export = !!(frappe.boot.developer_mode && this.app);
	}

	// One title, whichever layer is on screen. A layer-dependent title was dropped with the rest
	// of the "make the app layer look different" alternatives: the switch one line below already
	// says which layer this is, and saying it twice reads as a warning.
	title() {
		return this.app ? __("Manage {0} Dock", [__(this.app.app_title)]) : __("Manage Dock");
	}

	extra_actions() {
		return this.can_export
			? {
					secondary_action_label: __("Export to app"),
					secondary_action: () => this.export_to_app(),
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
		// What the app itself ships, unfiltered by anybody's reach -- the pool the manager offers
		// and what `unnamed_modules` counts against.
		this.base_rows = base || [];
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

	// Every entry this app's rail can show, in the server's order, each resolved to the label and
	// icon it renders as. An entry the boot payload doesn't carry is one the user may see nothing
	// in -- a module whose every item is blocked, a workspace they may not open -- so it is not
	// offerable. Keyed by its destination, which is also what a layer row names.
	load_entries() {
		this.entries = new Map();
		((this.app && this.app.dock) || []).forEach((row) => {
			const entry = frappe.app.sidebar.dock_entry(row);
			if (entry) this.entries.set(this.key(entry), entry);
		});
	}

	// A muted reading, not an affordance: how many of the app's modules are on no tier at all --
	// not on the rail, not shipped off it, simply never named. Those are the ones no layer can
	// bring back, so an author who did not mean it should be able to see the number.
	//
	// Read off the app's **own rows** rather than off the entry set, which is reach-filtered: a
	// module the record names but this person cannot see is named, and reporting it as unnamed
	// would send an author looking for a row that is already there.
	unnamed_modules() {
		const named = new Set((this.base_rows || []).map((row) => row.sidebar).filter(Boolean));
		return frappe.app.sidebar.app_modules(this.app).filter((shell) => !named.has(shell));
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

	// One row as a layer stores it, from the key the panes work in: the whole destination, plus
	// how it reads *only if this layer has an opinion about that*.
	//
	// An entry this layer merely references sends its icon and title back too -- the server
	// recognises them as inherited and blanks them, which is what keeps the app's and the site's
	// later relabels reaching a row nobody touched. An entry this layer **added** has nothing
	// below it to inherit from, so its own icon and title are the only ones there are.
	stored_row(key, hidden) {
		const entry = this.entries.get(key);
		return {
			sidebar: entry.sidebar,
			link_type: entry.link_type,
			link_to: entry.link_to,
			url: entry.url,
			icon: entry.icon,
			title: entry.label,
			added: this.is_own_add(key) ? 1 : 0,
			hidden,
		};
	}

	// Where an untouched layer starts, so the arrangement is a trim rather than a build from
	// scratch. It has to start from what saving unchanged would produce, because a save writes
	// the whole app slice: seeded with everything the app offers, whoever merely opens this and
	// saves would write `hidden: 0` over what a layer below deliberately hid, un-hiding it
	// without ever asking to.
	//
	// Each layer therefore starts from the layer *below* it, as that layer renders:
	//
	//   - the app's starts from its own rows, which is what it already holds
	//   - the site's starts from the app's dock as it renders -- its entries minus the ones the
	//     app ships off. Never from the rail this manager happens to see, which carries the
	//     curator's personal arrangement and is not theirs to publish.
	//   - a person's starts from the rail on screen -- the app's dock with the site's on top.
	unarranged_selection() {
		if (this.layer === "app") {
			return (this.layer_rows || [])
				.filter((row) => !row.hidden)
				.map((row) => this.key(row));
		}

		if (this.layer === "site") {
			return this.all_keys().filter((key) => !this.base_hidden.has(key));
		}

		const shown = frappe.app.sidebar
			.collect_dock_entries(this.app)
			.map((entry) => this.key(entry));
		return shown.length ? shown : this.all_keys();
	}

	// Every layer may add an entry. The server's bound is **reach** -- a person may put on their
	// rail anything they can already navigate to -- and never base membership, which is what
	// *never add* claimed and never enforced.
	can_add() {
		return !!this.app;
	}

	is_own_add(key) {
		return this.own_adds.has(key);
	}

	// **One control at every layer**, and the layer switch one line above is what says whether
	// hiding is an author stating a default or a site exercising a customisation. A control per
	// meaning was dropped: the meaning is already on screen, so a second control would be a
	// second way to say the same thing. The tooltip carries the difference.
	hide_tooltip(key, hidden) {
		if (hidden) return __("Show");
		return this.layer === "app" ? __("Ship this off by default") : __("Hide");
	}

	// The two resets, side by side, because they are two different reaches and only one of them
	// is undoable by the person it affects.
	extra_pane_actions() {
		if (this.layer !== "site" || !this.can_curate_site) return [];

		return [
			{
				label: __("Reset for everyone"),
				title: __(
					"Drops every person's own arrangement of this rail as well as the site's, so everybody is back on what the app ships."
				),
				onClick: () => this.reset_for_everyone(),
			},
		];
	}

	// A reading, not an affordance: the app's modules that are on no tier at all -- not on the
	// rail, not shipped off it, simply never named. Nothing above the app layer can bring one
	// back, so an author who did not mean it should be able to see the number.
	pane_note() {
		const unnamed = this.unnamed_modules();
		if (!unnamed.length) return "";

		return `<span title="${frappe.utils.escape_html(unnamed.join(", "))}">${__(
			"{0} of this app's modules are on no tier at all",
			[unnamed.length]
		)}</span>`;
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

	// Add, type-first: what it opens, then the target, then how it reads, with the shell override
	// behind a collapsed disclosure.
	//
	// **The pool is never drawn.** *Anything nameable* is an unbounded set -- every workspace, every
	// module, any URL -- and a pane for it would break the two-pane pair the whole surface is. It
	// lives in the picker's own search instead.
	//
	// **Icon and title start empty**, with no prefill and no placeholder holding the module's
	// title. Prefilling was refused for making divergence look like inheritance: a site that
	// renames a module sees the new name in the sidebar header and the old one on the rail, and a
	// pre-filled field gives the author no reason to suspect the two ever come apart. The cost is
	// taken knowingly -- an empty rail is a round trip per entry with two fields typed by hand.
	add() {
		if (!this.loaded) return;

		const sidebar = frappe.app.sidebar;
		const dialog = new frappe.ui.Dialog({
			title: __("Add to the dock"),
			fields: [
				{
					fieldtype: "Select",
					fieldname: "opens",
					label: __("What it opens"),
					options: [
						{ value: "Module", label: __("Module") },
						{ value: "Workspace", label: __("Workspace") },
						{ value: "URL", label: __("Web address") },
					],
					default: "Module",
					reqd: 1,
					onchange: () => this.describe_target(dialog),
				},
				{
					fieldtype: "Autocomplete",
					fieldname: "module",
					label: __("Module"),
					depends_on: "eval:doc.opens == 'Module'",
					// The app's navigable modules, which is what `get_app_modules` answers -- not a
					// link query, which would show only the minority that happen to have a
					// `Sidebar` document.
					options: sidebar.app_modules(this.app).map((shell) => ({
						value: shell,
						label: frappe.boot.module_sidebars[shell]?.label || shell,
					})),
				},
				{
					fieldtype: "Link",
					fieldname: "workspace",
					label: __("Workspace"),
					options: "Workspace",
					depends_on: "eval:doc.opens == 'Workspace'",
				},
				{
					fieldtype: "Data",
					fieldname: "url",
					label: __("Web address"),
					depends_on: "eval:doc.opens == 'URL'",
				},
				{ fieldtype: "HTML", fieldname: "hint" },
				{ fieldtype: "Section Break" },
				{ fieldtype: "Icon", fieldname: "icon", label: __("Icon"), reqd: 1 },
				{ fieldtype: "Column Break" },
				{
					fieldtype: "Data",
					fieldname: "title",
					label: __("Title"),
					reqd: 1,
					description: __("How it reads on the rail."),
				},
				{
					fieldtype: "Section Break",
					fieldname: "shell_section",
					label: __("Show a different sidebar"),
					collapsible: 1,
					// Collapsed by default: it is only for a page whose own module is not the shell
					// you want -- a page on a code-only module, which is on no rail, being the
					// case it exists for -- and every ordinary row leaves it alone.
					depends_on: "eval:doc.opens != 'URL'",
				},
				{
					fieldtype: "Link",
					fieldname: "shell",
					label: __("Sidebar"),
					options: "Sidebar",
					description: __(
						"Leave blank to derive it from what this opens. Fill it in only when the page's own module is not the sidebar you want."
					),
				},
			],
			primary_action_label: __("Add"),
			primary_action: (values) => {
				const entry = this.entry_from(values);
				if (!entry) return;
				dialog.hide();
				this.place(entry);
			},
		});

		dialog.show();
		this.describe_target(dialog);
	}

	// One line under the target saying what the row will do, because the two ordinary shapes
	// behave differently and neither says so from its fields alone.
	describe_target(dialog) {
		const hints = {
			Module: __("Opens the module's home."),
			Workspace: __("Its sidebar is derived from the module that owns it."),
			URL: __("Leaves the desk. It has no sidebar."),
		};
		$(dialog.fields_dict.hint.$wrapper).html(
			`<div class="text-muted small">${hints[dialog.get_value("opens")] || ""}</div>`
		);
	}

	// The dialog's answer as a rail entry, or nothing if it named nothing.
	entry_from(values) {
		const row =
			values.opens === "Module"
				? { sidebar: values.module }
				: values.opens === "Workspace"
				? {
						sidebar: values.shell || null,
						link_type: "Workspace",
						link_to: values.workspace,
				  }
				: { link_type: "URL", url: values.url };

		if (!(row.sidebar || row.link_to || row.url)) {
			frappe.throw(__("Pick something for it to open."));
		}

		return {
			...row,
			module: row.sidebar || null,
			icon: values.icon,
			label: values.title,
		};
	}

	// Put a newly added entry on the arrangement in front of us. Nothing is saved yet -- Save is
	// what says so, exactly as it is for a drag.
	place(entry) {
		const key = this.key(entry);
		if (this.entries.has(key)) {
			// Same destination, so it is the same entry: adding it again would be a second button
			// to one place. The one already there is un-hidden instead, which is what the person
			// meant.
			this.hidden.delete(key);
			this.render_panes();
			return;
		}

		this.entries.set(key, { ...entry, module: entry.module || null });
		this.own_adds.add(key);
		this.order.push(key);
		this.hidden.delete(key);
		this.render_panes();
	}

	// Author's promotion: write this app's dock into the app as a file, so git carries it.
	//
	// The **dock's own** promotion, not the sidebar's -- `Sidebar.mark_as_standard` materialises a
	// computed base, and a dock has none. There is no unmark button in this surface: taking an
	// app's rail away is a bigger act than an editor should offer beside Save, and it has its own
	// endpoint.
	async export_to_app() {
		if (!this.loaded) return;

		// Save first. Promotion reads what is *stored*, so exporting with unsaved drags on screen
		// would ship the arrangement the author had before they started -- silently, which is the
		// worst way to be wrong about a file that goes into git.
		this.sync_order();
		await frappe.xcall(this.layer_config.save, this.save_args());
		await frappe.xcall(MARK_AS_STANDARD, { app: this.app.app_name });
		// The app now ships a dock, so the third value in the switch has something to write to.
		this.layer = "app";
		if (this.$layer) this.$layer.val("app");
		this.load();
	}
};
