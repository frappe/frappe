// The rail's arrangement, in the editor every navigation surface shares
// (`frappe.ui.ArrangementEditor`, which holds the layer switch, the list, the panel and the
// persistence). This file only describes what the dock is: what its entries are, where its three
// layers live, and the one action it has that a sidebar does not.
//
// It arranges the rail for the app you are currently in, on the rail itself: the tiles are the
// list, dragged into order, taken off with their cross, and opened for their label and icon in a
// panel beside the rail. A floating rail stays floating and is held open. The layer, Cancel and
// Save sit in a small bar in the corner of the screen, which can be dragged out of the way, so the
// sidebar beside the rail is left as it is.
//
// An entry names one destination -- a shell, a workspace or a web address -- and every kind is
// arranged the same way. A companion's entry is an ordinary entry on the rail, not a fixture.
//
// It covers one app on purpose: a dock belongs to an app, so there is nothing to choose between
// and no app switcher. Entries in other apps are managed from those apps' rails.

// What differs between the three layers, in one place: where the arrangement is read from, where
// it is written back to, what to call it, and what to say once it lands. Everything else, such as
// the list, the eye and the shape of a saved row, is the same whichever layer is on screen.
const RESET_FOR_EVERYONE = "frappe.desk.doctype.dock.dock.reset_dock_for_everyone";
const MARK_AS_STANDARD = "frappe.desk.doctype.dock.dock.mark_as_standard";

const DOCK_LAYERS = {
	user: {
		read: "frappe.desk.doctype.dock.dock.get_user_dock_layer",
		save: "frappe.desk.doctype.dock.dock.save_user_dock",
		label: () => __("Just for me"),
		phrase: () => __("just for me"),
		saved: () => __("Dock updated"),
	},
	site: {
		read: "frappe.desk.doctype.dock.dock.get_site_dock_layer",
		save: "frappe.desk.doctype.dock.dock.save_site_dock",
		label: () => __("For everyone"),
		phrase: () => __("for everyone"),
		condition: () => frappe.user.has_role("Workspace Manager"),
		saved: () => __("Dock updated for everyone"),
	},
	// The third value, which is all the app layer looks like from here. Developer mode only,
	// because authoring what an app ships writes a file into the app, and only where the app
	// already ships one, since promoting is `Export to app`, which writes the file in the same
	// step. Named after the app, which `layers` binds.
	app: {
		read: "frappe.desk.doctype.dock.dock.get_app_dock_layer",
		save: "frappe.desk.doctype.dock.dock.save_app_dock",
		condition: () => !!frappe.boot.developer_mode,
		saved: () => __("Exported to the app"),
	},
};

frappe.ui.DockManager = class DockManager extends frappe.ui.ArrangementEditor {
	get layers() {
		const app = __(this.app?.app_title || this.app?.app_name || "");
		return {
			...DOCK_LAYERS,
			app: {
				...DOCK_LAYERS.app,
				label: () => __("For {0}", [app]),
				phrase: () => __("for {0}", [app]),
			},
		};
	}

	prepare() {
		// The rail renders for `get_sidebar_app()`, the shown sidebar's app, so curate that one.
		// It is also the only app context there is: a module belonging to no app has no rail to
		// arrange, which is why the user menu does not offer this there.
		this.app = frappe.app.sidebar.get_sidebar_app();
		this.base_hidden = new Set();
		this.own_adds = new Set();
		// Writing a file into an app is a developer action, so the promotion is offered only where
		// app content is authored. It is not gated by a role: the two layers above are what a site
		// rearranges, and neither needs this.
		this.can_export = !!(frappe.boot.developer_mode && this.app);
	}

	// One title, whichever layer is on screen: the bar already names the layer.
	title() {
		return this.app ? __("the {0} dock", [__(this.app.app_title)]) : __("the dock");
	}

	copy() {
		return {
			add_label: __("Add to the dock"),
			reset_title: __("Bring every entry back onto the dock."),
			list_empty: __("This app has nothing to arrange"),
			load_error: __("Could not load the dock. Please try again."),
		};
	}

	// The rail is held open while it is arranged and goes back to the person's preference when this
	// closes. The tiles are drawn by this editor meanwhile, and the controls by a bar of its own.
	mount() {
		const sidebar = frappe.app.sidebar;
		sidebar.watch_editor(this);
		sidebar.dock.hold_open(true);
		this.$tiles = sidebar.dock.begin_editing(this);
		return $(`<div class="ws-bar" role="toolbar"></div>`)
			.attr("aria-label", __("Arranging the dock"))
			.appendTo(document.body);
	}

	unmount() {
		this.destroy_tooltips();
		this.add_tooltip?.destroy();
		this.note_tooltip?.destroy();
		const sidebar = frappe.app.sidebar;
		sidebar.dock.end_editing(this);
		sidebar.dock.hold_open(false);
		sidebar.unwatch_editor(this);
		this.$frame.remove();
	}

	render_frame() {
		const dock = frappe.app.sidebar.dock;
		this.$frame.html(`
			<span class="ws-bar-grip">${frappe.utils.icon("grip-vertical", "sm")}</span>
			<span class="ws-bar-title">
				<span class="ws-bar-name">${__("Dock")}</span>
				<span class="ws-bar-layer"></span>
			</span>
			<span class="ws-note hidden"></span>
			<div class="ws-foot"></div>
		`);
		this.$note = this.$frame.find(".ws-note");
		this.$list = this.$tiles;
		this.$scroll = this.$tiles;
		this.$add_slot = dock.$add_slot;

		if (this.offered_layers.length > 1) {
			new frappe.ui.Dropdown({
				trigger: this.$frame.find(".ws-bar-layer"),
				side: "top",
				options: () => this.layer_menu(),
			});
		}
		this.render_layer_switch();
		this.render_footer();
		this.bind_keys();
		this.setup_bar_drag();
	}

	// The bar starts in the corner and moves by its grip, kept on screen.
	setup_bar_drag() {
		const bar = this.$frame[0];
		const grip = this.$frame.find(".ws-bar-grip")[0];
		let grab = null;
		grip.addEventListener("pointerdown", (e) => {
			const box = bar.getBoundingClientRect();
			grab = { dx: e.clientX - box.left, dy: e.clientY - box.top };
			grip.setPointerCapture(e.pointerId);
		});
		grip.addEventListener("pointermove", (e) => {
			if (!grab) return;
			const left = Math.min(
				Math.max(8, e.clientX - grab.dx),
				window.innerWidth - bar.offsetWidth - 8
			);
			const top = Math.min(
				Math.max(8, e.clientY - grab.dy),
				window.innerHeight - bar.offsetHeight - 8
			);
			this.$frame.css({ left, top, bottom: "auto" });
		});
		grip.addEventListener("pointerup", () => (grab = null));
	}

	layer_slot() {
		return this.$frame?.find(".ws-bar-layer");
	}

	// The sidebar is not being edited, so its header keeps its own menu.
	header_menu_items() {
		return null;
	}

	panel_edge() {
		return frappe.app.sidebar.dock.$dock[0];
	}

	// The tiles stay as they are while the layer loads, rather than giving way to a loading line
	// the rail has no room for.
	render_loading() {}

	// A drag that opened the editor is its first change: the tiles go where they were dropped.
	// Entries the drop did not show keep their places.
	on_load() {
		const dropped = this.opts.order;
		if (!dropped || this.applied_drop) return;
		this.applied_drop = true;

		const at = new Map(dropped.map((key, i) => [key, i]));
		const listed = this.order.filter((key) => this.is_listed(key));
		const known = listed.filter((key) => at.has(key)).sort((a, b) => at.get(a) - at.get(b));
		const next = listed.map((key) => (at.has(key) ? known.shift() : key));
		this.order = this.order.map((key) => (this.is_listed(key) ? next.shift() : key));
	}

	// Every shell in this app shows this app's rail, so moving between them keeps the editor open.
	survives_shell(shell) {
		return frappe.app.sidebar.app_for_sidebar(shell) === this.app?.app_name;
	}

	// A dock entry is its tile, drawn the way the rail draws it.
	row_content(key) {
		const entry = this.entries.get(key);
		const sidebar = frappe.app.sidebar;
		const icon = entry.icon
			? frappe.utils.icon(entry.icon, "rail")
			: frappe.utils.desktop_icon(entry.label, "gray", "rail");
		const active = sidebar.is_active_entry(entry) ? "active" : "";
		return $(`<span class="dock-item ${active}">
			<span class="dock-item-icon">${icon}</span>
		</span>`);
	}

	row_classes() {
		return "ws-tile";
	}

	// A tile is named by its tooltip, as on the rail.
	list_row(key) {
		const $row = super.list_row(key).attr("aria-label", this.entries.get(key).label);
		this.tile_tooltips.push(
			new frappe.ui.Tooltip($row[0], {
				text: this.entries.get(key).label,
				side: "right",
				delay: 0,
				offset: 10,
				class: "es-tooltip--plain",
			})
		);
		return $row;
	}

	render_list() {
		this.destroy_tooltips();
		super.render_list();
	}

	// The bar has no room for the note's words, so they are an icon's tooltip.
	render_body() {
		this.add_tooltip?.destroy();
		this.note_tooltip?.destroy();
		super.render_body();
		const note = this.$note.text().trim();
		if (note) {
			this.$note.html(frappe.utils.icon("info", "sm"));
			this.note_tooltip = new frappe.ui.Tooltip(this.$note[0], { text: note, side: "top" });
		}
		if (this.$add) {
			this.add_tooltip = new frappe.ui.Tooltip(this.$add[0], {
				text: this.copy().add_label,
				side: "right",
				delay: 0,
				offset: 10,
				class: "es-tooltip--plain",
			});
		}
	}

	destroy_tooltips() {
		(this.tile_tooltips || []).forEach((tip) => tip.destroy());
		this.tile_tooltips = [];
	}

	// The label and icon a tile reads with. A stored row carries both, and the server blanks the
	// ones that match what the layer below says, so an untouched tile keeps following it.
	edit_entry(key) {
		const entry = this.entries.get(key);
		this.open_panel({
			key,
			title: entry.label,
			fields: [
				{
					fieldtype: "Data",
					fieldname: "title",
					label: __("Label"),
					default: entry.label,
				},
				{ fieldtype: "Icon", fieldname: "icon", label: __("Icon"), default: entry.icon },
			],
			on_change: (values) => {
				if (values.title) entry.label = values.title;
				entry.icon = values.icon || null;
				this.render_list();
			},
		});
	}

	// Load the layer being edited: its own stored rows, not the resolved rail in
	// `frappe.boot.dock`. A save replaces the layer whole, so it has to show what it will
	// overwrite. Shown the resolved rail instead, saving as a user would copy the site's rows into
	// their own layer and freeze them against every later site change.
	//
	// Every read names the app, because a layer belongs to one app. Reading without one would ask
	// for an arrangement that does not exist.
	async read() {
		// A dock belongs to an app and every read names one, so there is nothing to read without
		// it. The user menu already hides this surface where there is no app context. Checking
		// here keeps a manually opened manager on the load error instead of a failed call.
		if (!this.app) throw new Error("Manage Dock: no app in context");

		const args = { app: this.app.app_name };
		const [layer, base] = await Promise.all([
			frappe.xcall(this.layer_config.read, args),
			frappe.xcall("frappe.desk.doctype.dock.dock.get_app_dock_layer", args),
		]);

		this.layer_rows = layer;
		this.load_entries();
		// What the app itself ships, unfiltered by anyone's reach: the pool the manager offers and
		// what `unnamed_modules` counts against.
		this.base_rows = base || [];
		// Which of these rows this layer added itself, so they carry a cross rather than an eye.
		// Read from the stored layer rather than inferred from the entry: an entry a lower layer
		// added is a reference from here, and hiding is the right control for it.
		this.own_adds = new Set(
			(layer || []).filter((row) => row.added).map((row) => this.key(row))
		);
		// What the apps ship, so a row the app itself hid can say so. The hidden flag alone does
		// not say who hid it, and un-hiding an app's deliberate default should be a choice rather
		// than an accident.
		this.base_hidden = new Set(
			(base || []).filter((row) => row.hidden).map((row) => this.key(row))
		);
		// Only what this layer put on the dock is named. Everything else the app offers follows it
		// in the app's own order, with the eye off.
		this.arrange(this.initial_selection());
	}

	// Every entry this app's rail can show, in the server's order, each resolved to the label and
	// icon it renders as. An entry the boot payload does not carry is one the user can see nothing
	// in, such as a module whose items are all blocked or a workspace they cannot open, so it is
	// not offered. Keyed by its destination, which is what a layer row names.
	load_entries() {
		this.entries = new Map();
		const added = (this.layer_rows || []).filter((row) => row.added);
		[...((this.app && this.app.dock) || []), ...added].forEach((row) => {
			const entry = frappe.app.sidebar.dock_entry(row);
			if (entry && !this.entries.has(this.key(entry)))
				this.entries.set(this.key(entry), entry);
		});
	}

	// A read-only count, not a control: how many of the app's modules are on no tier at all,
	// neither on the rail nor shipped off it, simply never named. No layer can bring those back,
	// so an author who did not intend it should see the number.
	//
	// Counted against the app's own rows rather than the entry set, which is reach-filtered. A
	// module the record names but this user cannot see is still named, and reporting it as unnamed
	// would send an author looking for a row that is already there.
	unnamed_modules() {
		const named = new Set(
			(this.base_rows || [])
				.filter((row) => row.link_type === "Sidebar")
				.map((row) => row.link_to)
		);
		return frappe.app.sidebar
			.navigable_app_modules(this.app)
			.filter((shell) => !named.has(shell));
	}

	// What identifies an entry here, on the server and on the rail: the whole destination. The
	// kind is half of it, because a `Sidebar` and a `Workspace` with the same name are two
	// entries.
	key(row) {
		return frappe.app.sidebar.dock_entry_key(row);
	}

	// This layer's picks, in their order. The layer belongs to this app, so every row in it is
	// about this app: the filter checks what the app still offers, not which app a row belongs to.
	initial_selection() {
		const mine = new Set(this.all_keys());
		const arranged = (this.layer_rows || [])
			.filter((row) => !row.hidden && mine.has(this.key(row)))
			.map((row) => this.key(row));
		return arranged.length ? arranged : this.unarranged_selection();
	}

	// One row as a layer stores it, built from the key the list works in: the whole destination,
	// plus how it reads if this layer overrides that.
	//
	// An entry this layer only references still sends its icon and title back. The server
	// recognises them as inherited and blanks them, which keeps the app's and the site's later
	// relabels reaching a row nobody touched. An entry this layer added has nothing below it to
	// inherit from, so its own icon and title are the only ones.
	stored_row(key, hidden) {
		const entry = this.entries.get(key);
		return {
			link_type: entry.link_type,
			link_to: entry.link_to,
			url: entry.url,
			icon: entry.icon,
			title: entry.label,
			added: this.is_own_add(key) ? 1 : 0,
			hidden,
		};
	}

	// Where an untouched layer starts, so arranging it is a trim rather than a build from scratch.
	// It has to start from what saving unchanged would produce, because a save writes the whole
	// app slice. Seeded with everything the app offers, a user who opened this and saved would
	// write `hidden: 0` over what a lower layer deliberately hid, un-hiding it by accident.
	//
	// So each layer starts from the layer below it, as that layer renders:
	//
	//   - the app's starts from its own rows, which is what it already holds
	//   - the site's starts from the app's dock as it renders, its entries minus the ones the app
	//     ships off. Never from the rail this manager happens to show, which carries the curator's
	//     personal arrangement and is not theirs to publish.
	//   - a user's starts from the rail on screen: the app's dock with the site's on top.
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

	// Every layer may add an entry. The server bounds this by reach, so a user may put on their
	// rail anything they can already navigate to, and never by base membership, which is what the
	// old "never add" rule claimed but did not enforce.
	can_add() {
		return !!this.app;
	}

	is_own_add(key) {
		return this.own_adds.has(key);
	}

	// One control, the cross, at every layer. On a tile a lower layer holds it stores the row
	// hidden, which on the app's layer ships it off by default. The tile leaves the rail either
	// way, and adding the same entry again is how it comes back (see `place`). A tile this layer
	// added already carries a cross of its own, which removes it.
	can_remove(key) {
		return !this.is_own_add(key);
	}

	can_hide() {
		return false;
	}

	is_listed(key) {
		return !this.hidden.has(key);
	}

	remove(key) {
		if (this.is_own_add(key)) return super.remove(key);
		if (this.panel?.key === key) this.close_panel();
		this.hide(key);
		this.render_list();
	}

	// The two resets sit side by side in the menu, because they reach different sets of users and
	// only one of them can be undone by the user it affects.
	extra_menu_items() {
		const items = [];
		if (this.layer === "site" && this.can_curate_site) {
			items.push({
				label: __("Reset for everyone"),
				icon: "history",
				theme: "red",
				description: __(
					"Drops every person's own arrangement of this rail as well as the site's, so everybody is back on what the app ships."
				),
				onclick: () => this.reset_for_everyone(),
			});
		}
		if (this.can_export) {
			items.push({
				label: __("Export to app"),
				icon: "package-plus",
				onclick: () => this.export_to_app(),
			});
		}
		return items;
	}

	// A read-only count, not a control: the app's modules on no tier at all, neither on the rail
	// nor shipped off it, simply never named. Nothing above the app layer can bring one back, so
	// an author who did not intend it should see the number.
	pane_note() {
		const unnamed = this.unnamed_modules();
		if (!unnamed.length) return "";

		return `<span title="${frappe.utils.escape_html(unnamed.join(", "))}">${__(
			"{0} of this app's modules are on no tier at all",
			[unnamed.length]
		)}</span>`;
	}

	// An empty selection is not stored as an empty dock. It is saved as no rows at all, which is
	// what this layer says when it has nothing to say, so Reset here resets to the layer below,
	// the site's or the app's own dock, and takes effect on the next Save like every other edit
	// in the list.
	//
	// Rows this layer added are removed too, not just taken off the rail. There is nothing below
	// them to fall back to, so leaving one hidden would keep a row nobody can see or explain.
	reset() {
		this.own_adds.forEach((key) => this.remove(key));
		if (!this.selection.length) return;
		this.hidden = new Set(this.all_keys());
		this.render_list();
	}

	// Drop every non-standard dock for this app, including the site's own layer, so everyone is
	// back on the app's exported dock.
	//
	// This is the one action that reaches past the site layer, which is why it exists: a Workspace
	// Manager who re-curates the site's rail reaches nobody who has arranged their own. It is
	// immediate and confirmed rather than an edit applied on Save, because it is not an edit
	// to the arrangement in front of them but a decision about everyone else's.
	async reset_for_everyone() {
		frappe.confirm(
			__(
				"This drops the dock arrangement of every person on this site for {0}, and the site's own, back to what the app ships. It cannot be undone.",
				[frappe.utils.escape_html(this.app.app_title || this.app.app_name)]
			),
			async () => {
				const rail = await frappe.xcall(RESET_FOR_EVERYONE, { app: this.app.app_name });
				this.close();
				this.apply(rail);
				frappe.show_alert({
					message: __("Everyone is back on the dock this app ships"),
					indicator: "green",
				});
			}
		);
	}

	save_args() {
		// The layer belongs to this app, so what is on screen is all of it. Carrying other apps'
		// rows through was needed by the old flat list; now a save touches one document and that
		// document holds one app's rows.
		//
		// Nothing selected means Reset: it stores no row, so the layer below shows through instead
		// of the app being hidden entry by entry.
		const mine = this.selection.length
			? this.arranged_rows((key, hidden) => this.stored_row(key, hidden))
			: [];

		return { app: this.app.app_name, items: JSON.stringify(mine) };
	}

	// Both saves return this app's resolved rail, its own dock with the site's arrangement and
	// this user's on top, so the rail can be redrawn in place whichever layer was written. Only
	// this app's key is replaced, because only this app's document was saved.
	apply(rail) {
		frappe.boot.dock = { ...(frappe.boot.dock || {}), [this.app.app_name]: rail };
		frappe.app.sidebar.refresh_dock();
		// The header draws the module's icon from this rail too.
		frappe.app.sidebar.refresh_header();
	}

	// Add, kind first: what it opens, then the target, then how it reads.
	//
	// The pool is never drawn. Anything nameable is an unbounded set, covering every workspace,
	// every module and any URL, so it lives in the picker's own search instead.
	//
	// Icon and title start empty, with no prefill and no placeholder holding the module's title.
	// Prefilling would make divergence look like inheritance: a site that renames a module sees
	// the new name in the sidebar header and the old one on the rail, and a prefilled field gives
	// the author no reason to suspect the two can differ. The cost is that filling an empty rail
	// takes a round trip per entry with two fields typed by hand.
	add() {
		if (!this.loaded) return;

		const sidebar = frappe.app.sidebar;
		const panel = this.open_add_panel({
			title: __("Add to the dock"),
			fields: [
				{
					fieldtype: "Select",
					fieldname: "opens",
					label: __("What it opens"),
					options: [
						{ value: "Sidebar", label: __("Module") },
						{ value: "Workspace", label: __("Workspace") },
						{ value: "URL", label: __("Web address") },
					],
					default: "Sidebar",
					onchange: () => this.describe_target(panel.field_group),
				},
				{
					fieldtype: "Autocomplete",
					fieldname: "module",
					label: __("Module"),
					depends_on: "eval:doc.opens == 'Sidebar'",
					// The app's navigable modules, which is what `get_app_modules` returns, rather
					// than a link query, which would show only the few modules that have a
					// `Sidebar` document.
					options: sidebar.navigable_app_modules(this.app).map((shell) => ({
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
				{ fieldtype: "Icon", fieldname: "icon", label: __("Icon") },
				{
					fieldtype: "Data",
					fieldname: "title",
					label: __("Title"),
					description: __("How it reads on the rail."),
				},
			],
			choice: "opens",
			primary: (values) => {
				const target = { Sidebar: "module", Workspace: "workspace", URL: "url" }[
					values.opens
				];
				const missing = [target, "icon", "title"].filter((field) => !values[field]);
				if (panel.flag_missing(missing)) return;

				const entry = this.entry_from(values);
				if (!entry) return;
				this.close_panel();
				this.place(entry);
			},
		});

		this.describe_target(panel.field_group);
	}

	// One line under the target saying what the row will do, because the two common shapes behave
	// differently and their fields alone do not show that.
	describe_target(form) {
		const hints = {
			Sidebar: __("Opens the module's home and shows its sidebar."),
			Workspace: __("Its sidebar is derived from the module that owns it."),
			URL: __("Leaves the desk. It has no sidebar."),
		};
		$(form.fields_dict.hint.$wrapper).html(
			`<div class="ws-panel-hint">${hints[form.get_value("opens")] || ""}</div>`
		);
	}

	// The Add form's values as a rail entry, or nothing if it named nothing.
	entry_from(values) {
		const row =
			values.opens === "Sidebar"
				? { link_type: "Sidebar", link_to: values.module }
				: values.opens === "Workspace"
				? { link_type: "Workspace", link_to: values.workspace }
				: { link_type: "URL", url: values.url };

		if (!(row.link_to || row.url)) {
			frappe.throw(__("Pick something for it to open."));
		}

		return {
			...row,
			module: row.link_type === "Sidebar" ? row.link_to : null,
			icon: values.icon,
			label: values.title,
		};
	}

	// Put a newly added entry into the arrangement on screen. Nothing is saved yet; Save does
	// that, the same as for a drag.
	place(entry) {
		const key = this.key(entry);
		if (this.entries.has(key)) {
			// Same destination means the same entry, and adding it again would put a second button
			// to one place. The existing one is un-hidden instead, which is what the user meant.
			this.hidden.delete(key);
			this.render_list();
			return;
		}

		this.entries.set(key, { ...entry, module: entry.module || null });
		this.own_adds.add(key);
		this.order.push(key);
		this.hidden.delete(key);
		this.render_list();
	}

	// Author's promotion: write this app's dock into the app as a file so git carries it.
	//
	// This is the dock's promotion, not the sidebar's. `Sidebar.mark_as_standard` builds a stored
	// document from a computed base, and a dock has none. There is no unmark button here: taking
	// an app's rail away is a larger action than an editor should offer beside Save, and it has
	// its own endpoint.
	async export_to_app() {
		if (!this.loaded) return;

		// Save first. Promotion reads what is stored, so exporting with unsaved drags on screen
		// would silently ship the arrangement the author had before they started, which is the
		// worst way to be wrong about a file that goes into git.
		await frappe.xcall(this.layer_config.save, this.save_args());
		await frappe.xcall(MARK_AS_STANDARD, { app: this.app.app_name });
		// The app now ships a dock, so the third value in the switch has something to write to.
		this.layer = "app";
		this.render_layer_switch();
		this.load();
	}
};
