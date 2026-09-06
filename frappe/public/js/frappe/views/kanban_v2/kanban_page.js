frappe.provide("frappe.views");

/**
 * Select-value → badge theme + lucide icon for cards.
 * Case-insensitive keys; missing values fall back to frappe.utils.guess_colour().
 * Override per doctype via `frappe.kanban_v2.settings` (plain string = `{ theme }`).
 */
const SELECT_STYLES = {
	low: { theme: "gray", icon: "signal-low" },
	medium: { theme: "amber", icon: "signal-medium" },
	high: { theme: "red", icon: "signal-high" },
	urgent: { theme: "red", icon: "signal" },

	draft: { theme: "gray", icon: "circle-dashed" },
	submitted: { theme: "blue", icon: "send" },
	cancelled: { theme: "red", icon: "circle-x" },
	canceled: { theme: "red", icon: "circle-x" },

	"not started": { theme: "gray", icon: "circle" },
	todo: { theme: "gray", icon: "circle" },
	open: { theme: "gray", icon: "circle" },
	queued: { theme: "gray", icon: "circle-dashed" },
	scheduled: { theme: "gray", icon: "circle-dashed" },
	backlog: { theme: "gray", icon: "circle-dashed" },

	"in progress": { theme: "blue", icon: "circle-dot" },
	working: { theme: "blue", icon: "circle-dot" },
	running: { theme: "blue", icon: "circle-dot" },
	started: { theme: "blue", icon: "circle-dot" },
	processing: { theme: "blue", icon: "circle-dot" },

	"on hold": { theme: "amber", icon: "circle-pause" },
	paused: { theme: "amber", icon: "circle-pause" },
	pending: { theme: "amber", icon: "hourglass" },
	"pending review": { theme: "amber", icon: "eye" },
	"under review": { theme: "amber", icon: "eye" },
	"awaiting approval": { theme: "amber", icon: "user-check" },
	"pending approval": { theme: "amber", icon: "user-check" },
	blocked: { theme: "red", icon: "ban" },
	retrying: { theme: "amber", icon: "loader" },

	done: { theme: "green", icon: "circle-check" },
	success: { theme: "green", icon: "circle-check" },
	completed: { theme: "green", icon: "circle-check" },
	closed: { theme: "green", icon: "circle-check" },
	approved: { theme: "green", icon: "circle-check" },
	resolved: { theme: "green", icon: "circle-check" },
	verified: { theme: "green", icon: "circle-check" },

	// Explicit: fallback would treat "Partially Failed" as a plain failure.
	"partial success": { theme: "amber", icon: "circle-ellipsis" },
	"partially failed": { theme: "amber", icon: "circle-alert" },
	"partially completed": { theme: "amber", icon: "circle-ellipsis" },
	"timed out": { theme: "amber", icon: "clock-alert" },
	timeout: { theme: "amber", icon: "clock-alert" },

	failed: { theme: "red", icon: "circle-x" },
	error: { theme: "red", icon: "circle-x" },
	rejected: { theme: "red", icon: "circle-x" },
	expired: { theme: "red", icon: "clock-alert" },
	overdue: { theme: "red", icon: "timer" },

	active: { theme: "green", icon: "circle-check" },
	enabled: { theme: "green", icon: "circle-check" },
	inactive: { theme: "gray", icon: "circle" },
	disabled: { theme: "gray", icon: "circle-off" },
	archived: { theme: "gray", icon: "archive" },
};

/**
 * Kanban v2 board page. Route: List/{Doctype}/Kanban/{board_name}.
 * Customize via `frappe.kanban_v2.settings` / `extend_settings` (see settings.js).
 */
frappe.views.KanbanV2Page = class KanbanV2Page {
	constructor(wrapper) {
		this.page = wrapper.page;

		this.page.page_form.removeClass("hide row").addClass("flex").show();
		this.page.page_form.addClass("list-page-form");
		this.$filter_section = $(
			'<div class="filter-section flex ms-auto kanban-v2-filter-section"></div>'
		).appendTo(this.page.page_form);

		this.$container = $('<div class="kanban-v2-container px-4 pb-2">').appendTo(
			this.page.main
		);

		// Shared page instance with List view — restore_page_shell() must undo this.
		this.setup_board_height_sync();
		this.apply_page_shell();

		this.make_selection_bar();
	}

	/** Durable empty / error shell via frappe.ui.empty_state. */
	show_empty(opts) {
		this.$container.empty().append(
			frappe.ui.empty_state({
				...opts,
				css_class: ["min-h-64", opts.css_class].filter(Boolean).join(" "),
			})
		);
	}

	/**
	 * Turn the shared page into the Kanban shell: a full-height, full-width,
	 * padding-less flex column with the list side section suppressed. Idempotent,
	 * so it's safe to call on every route load.
	 */
	apply_page_shell() {
		this.setup_board_height_sync();
		this.page.main.addClass("flex flex-col overflow-hidden p-0");
		if (this.$filter_section) this.$filter_section.show();
		if (this.$container) this.$container.show();
		$(document.body).addClass("no-list-sidebar");
		this.page.container.addClass("kanban-v2-full-width");
		this.sync_board_height();
	}

	/**
	 * Undo apply_page_shell() so returning to the List view (which reuses this
	 * page instance) gets a clean, padded, fixed-width main section back.
	 */
	restore_page_shell() {
		this.page.main.removeClass("flex flex-col overflow-hidden p-0");
		if (this.$filter_section) this.$filter_section.hide();
		if (this.$container) this.$container.hide();
		// NOTE: don't remove `no-list-sidebar`. It's set to true by base_list for
		// every list view and never unset elsewhere, so the List view we're likely
		// returning to needs it; our teardown runs after the list's own setup, so
		// removing it here would clobber the list and re-show its side section.
		this.page.container.removeClass("kanban-v2-full-width");
	}

	/** Board name from the List/.../Kanban/{board} route. */
	get_board_name_from_route() {
		const route = frappe.get_route();
		if (route[0] === "List" && frappe.utils.to_title_case(route[2] || "") === "Kanban") {
			return route[3] || null;
		}
		return null;
	}

	/** Floating bulk-action bar + Escape / route-change teardown. */
	make_selection_bar() {
		this.selected_ids = [];
		this.$selection_bar = $(`
			<div class="kn-selection-bar items-center gap-2 rounded-md border bg-surface-base ps-4 pe-2.5 py-2.5">
				<span class="kn-sel-count text-sm-semibold text-ink-gray-8 whitespace-nowrap pe-1"></span>
				${frappe.ui.button.html({ label: __("Edit"), css_class: "kn-sel-edit" })}
				${frappe.ui.button.html({ label: __("Assign"), css_class: "kn-sel-assign" })}
				${frappe.ui.button.html({ label: __("Tags"), css_class: "kn-sel-tags" })}
				<span class="kn-sel-custom flex items-center gap-2"></span>
				${frappe.ui.button.html({ label: __("Delete"), theme: "red", css_class: "kn-sel-delete" })}
				${frappe.ui.button.html({ label: __("Clear"), variant: "ghost", css_class: "kn-sel-clear" })}
			</div>`).appendTo(document.body);

		const done = () => {
			if (this.board) {
				this.board.engine.select([]);
				this.board.refresh();
			}
		};
		this._selection_done = done;
		// Clear button only deselects — no refresh needed (unlike Edit/Assign/etc.)
		this.$selection_bar.find(".kn-sel-clear").on("click", () => this.clear_selection());
		this.$selection_bar.find(".kn-sel-edit").on("click", () => this.bulk_edit(done));
		this.$selection_bar
			.find(".kn-sel-assign")
			.on("click", () => this.bulk().assign(this.selected_ids, done));
		this.$selection_bar
			.find(".kn-sel-tags")
			.on("click", () => this.bulk().add_tags(this.selected_ids, done));
		this.$selection_bar
			.find(".kn-sel-delete")
			.on("click", () => this.confirm_delete(this.selected_ids, done));

		// Escape clears the selection — use Frappe's key pipeline (the same one
		// dialogs/dropdowns use) so it fires reliably. key_map only emits "escape".
		frappe.ui.keys.on("escape", () => {
			if (this.selected_ids.length) this.clear_selection();
		});
		// The bar lives on <body>, so hide it when navigating away from this
		// board — otherwise it lingers over the next page (e.g. the form).
		frappe.router.on("change", () => {
			const board_on_route = this.get_board_name_from_route();
			if (board_on_route !== this.current_board) {
				this.update_selection_bar([]);
				this.teardown_board(true);
			}
		});
	}

	/** Destroy the mounted board (drops its realtime subscription). When
	 * `clear_route` is true, also forget the current board so the next visit
	 * remounts from scratch (used when navigating away from the page). */
	teardown_board(clear_route = false) {
		if (this.board) {
			try {
				this.board.destroy();
			} catch (e) {
				// ignore
			}
			this.board = null;
		}
		if (clear_route) this.current_board = null;
		if (clear_route) {
			this.cleanup_board_height_sync();
			// Fully restore the shared page shell when leaving the new Kanban page;
			// otherwise the List view (same page instance) inherits kanban layout.
			this.restore_page_shell();
		}
	}

	/** Fit the board container to the remaining viewport height. */
	sync_board_height() {
		if (!this.$container || !this.$container.length) return;
		const rect = this.$container[0].getBoundingClientRect();
		if (!rect) return;
		const bottom_gap = 8;
		const available = Math.max(
			220,
			Math.floor(window.innerHeight - Math.max(0, rect.top) - bottom_gap)
		);
		this.$container[0].style.setProperty("--kanban-v2-height", `${available}px`);
	}

	setup_board_height_sync() {
		if (this._board_height_sync_bound) return;
		this._board_height_sync_bound = true;

		this._on_board_height_sync = () => this.sync_board_height();
		window.addEventListener("resize", this._on_board_height_sync, { passive: true });
	}

	cleanup_board_height_sync() {
		if (this._on_board_height_sync) {
			window.removeEventListener("resize", this._on_board_height_sync);
		}
		this._on_board_height_sync = null;
		this._board_height_sync_bound = false;
	}

	clear_selection() {
		if (this.board) this.board.engine.select([]);
		this.update_selection_bar([]);
	}

	bulk() {
		if (!this._bulk || this._bulk.doctype !== this.doctype) {
			this._bulk = new frappe.kanban_v2.BulkOperations({ doctype: this.doctype });
		}
		return this._bulk;
	}

	/**
	 * Confirm, then permanently delete the given docs (same wording as list view).
	 * Used by the card context menu and the bulk selection bar.
	 */
	confirm_delete(docnames, done) {
		const ids = (docnames || []).filter(Boolean);
		if (!ids.length) return;
		const message =
			ids.length === 1
				? __("Delete {0} item permanently?", [1], "Title of confirmation dialog")
				: __(
						"Delete {0} items permanently?",
						[ids.length],
						"Title of confirmation dialog"
				  );
		frappe.confirm(message, () => this.bulk().delete(ids, done));
	}

	is_field_editable(df) {
		return (
			df.fieldname &&
			frappe.model.is_value_type(df) &&
			df.fieldtype !== "Read Only" &&
			!df.hidden &&
			!df.read_only &&
			!df.is_virtual
		);
	}

	bulk_edit(done) {
		if (!this.selected_ids.length) return;
		const field_mappings = {};
		frappe.meta.get_docfields(this.doctype).forEach((df) => {
			if (this.is_field_editable(df)) {
				field_mappings[`${__(df.label)} (${this.doctype})`] = Object.assign({}, df, {
					is_child_field: false,
				});
			}
		});
		this.bulk().edit(this.selected_ids, field_mappings, done);
	}

	update_selection_bar(ids) {
		this.selected_ids = ids || [];
		if (this.selected_ids.length) {
			this.$selection_bar
				.find(".kn-sel-count")
				.text(__("{0} selected", [this.selected_ids.length]));
			// Bulk Assign follows the board's "Show Assigned To" setting.
			this.$selection_bar.find(".kn-sel-assign").toggle(this.show_assigned_to !== false);
			this.refresh_bulk_actions();
			this.$selection_bar.css("display", "flex");
		} else {
			this.$selection_bar.hide();
		}
	}

	/**
	 * Rebuild developer bulk buttons from settings.bulk_actions. Defaults
	 * (Edit / Assign / Tags / Delete / Clear) stay; extras sit between Tags
	 * and Delete. Called whenever the selection bar is shown so condition()
	 * and the current ids stay fresh.
	 */
	refresh_bulk_actions() {
		const $slot = this.$selection_bar.find(".kn-sel-custom");
		$slot.empty();

		const s = this.settings || {};
		if (typeof s.bulk_actions !== "function") return;

		const done = this._selection_done || (() => {});
		const actions = s.bulk_actions(this.selected_ids, this) || [];
		actions.forEach((action) => {
			if (!action || !action.label) return;
			if (typeof action.condition === "function" && !action.condition()) return;

			const $btn = $(
				frappe.ui.button.html({
					label: action.label,
					icon: action.icon,
					theme: action.theme,
					variant: action.variant,
				})
			);
			$btn.on("click", () => {
				if (typeof action.onclick === "function") {
					action.onclick(this.selected_ids, this, done);
				}
			});
			$slot.append($btn);
		});
	}

	/** Load the board named in the route (or last-used) and mount it. */
	async load_from_route() {
		// Re-apply the page shell on every route load; router-driven teardown can
		// clear it while reusing the same page instance.
		this.apply_page_shell();

		const board_name = this.get_board_name_from_route();
		if (!board_name) {
			this.show_empty({
				icon: "columns-3",
				title: __("No Kanban Board specified."),
			});
			return;
		}
		if (this.current_board === board_name && this.board) {
			// Already mounted — only rebuild if the board's config changed
			// (e.g. Card Fields / Preview Fields edited on the form meanwhile).
			this.remount_if_board_changed(board_name);
			return;
		}
		this.current_board = board_name;

		this.page.set_title(__(board_name), null, true);
		// Keep navbar left side consistent with classic views.
		frappe.breadcrumbs.add(this.doctype, board_name);
		frappe.breadcrumbs.update();

		let board;
		try {
			board = await frappe.db.get_doc("Kanban Board", board_name);
		} catch (e) {
			this.show_empty({
				icon: "columns-3",
				title: __("Kanban Board {0} not found.", [board_name]),
			});
			return;
		}

		this.board_doc = board;
		this.doctype = board.reference_doctype;
		this.field_name = board.field_name;
		this.filters = [];
		try {
			this.filters = JSON.parse(board.filters || "[]");
		} catch (e) {
			// ignore malformed filters
		}
		// The board's saved filters — used to show the "Not Saved" indicator.
		this.saved_filters = JSON.parse(JSON.stringify(this.filters));
		const page_title = __(board.kanban_board_name || board_name);
		this.page.set_title(page_title, null, true);
		frappe.breadcrumbs.add(this.doctype, board.kanban_board_name || board_name);
		frappe.breadcrumbs.update();

		await frappe.model.with_doctype(this.doctype);
		this.setup_meta();
		this.setup_toolbar();
		this.mount_board();
		// Remember for List → Kanban without a board name in the route.
		frappe.model.user_settings.save(this.doctype, "last_view", "Kanban").then(() =>
			frappe.model.user_settings.save(this.doctype, "Kanban", {
				last_kanban_board: board_name,
			})
		);
		// Keep the filter UI in step with this board (the group is reused across
		// same-doctype board switches, so it can hold the previous board's set).
		this.sync_filter_group_to_board();
		this.setup_group_button();
		this.setup_quick_filters();
	}

	/**
	 * Rebuild the mounted board when its card config changed since we loaded
	 * it, so edits on the Kanban Board form (Card Fields, Preview Fields, …)
	 * show up on the next visit without a full page reload. Only the rendering
	 * config is compared — dragging a card also saves the board, and that must
	 * not cost a remount.
	 */
	async remount_if_board_changed(board_name) {
		try {
			const config = await frappe.xcall(
				"frappe.desk.doctype.kanban_board.kanban_board.get_card_config",
				{ board_name }
			);
			if (!config || this.card_config_signature(config) === this.card_config_sig) return;

			this.current_board = null;
			this.load_from_route();
		} catch (e) {
			// Keep the existing board mounted — a failed config check must not
			// wipe the UI. Surface a soft alert so the miss isn't silent.
			console.error(e);
			frappe.ui.toast({
				message: __("Could not refresh Kanban board settings."),
				type: "warning",
			});
		}
	}

	/** Comparable form of the config that decides how a card / hover peek is rendered. */
	card_config_signature(doc) {
		const field_sig = (rows) =>
			(rows || []).map((f) => [f.fieldname, f.label || "", f.icon || ""]);
		return JSON.stringify([
			doc.title_field || "",
			doc.image_field || "",
			cint(doc.show_assigned_to, 1),
			cint(doc.show_tags_on_card, 0),
			doc.footer_date_field || "Modified",
			field_sig(doc.card_fields),
			field_sig(doc.preview_fields),
		]);
	}

	/** Resolve title/image/fields and doctype kanban settings for this board. */
	setup_meta() {
		const meta = frappe.get_meta(this.doctype);
		this.meta = meta;

		// From `{doctype}_kanban.js` and/or `doctype_kanban_js` hooks (ran in
		// init_doctype). Doctype-level config applies to every board;
		// `boards[<board name>]` overrides it for one board.
		const reg = (frappe.kanban_v2.settings || {})[this.doctype] || {};
		const board_override = (reg.boards && reg.boards[this.current_board]) || {};
		this.settings = {
			...reg,
			...board_override,
			callbacks: { ...(reg.callbacks || {}), ...(board_override.callbacks || {}) },
		};

		// Title: board config (name / Data only) → doctype title_field if Data →
		// first Data field → name. Old boards with an empty title_field use the
		// same fallback chain.
		this.title_field = this.resolve_title_field(meta);
		// Image thumb: board config → doctype image_field → first Attach Image.
		// Empty means no thumb on cards.
		this.image_field = this.resolve_image_field(meta);
		// Assignees on the card + hover footer. Default on for boards that
		// predate the setting (undefined / missing → show).
		this.show_assigned_to = cint(this.board_doc.show_assigned_to, 1) === 1;
		this.show_tags_on_card = cint(this.board_doc.show_tags_on_card, 0) === 1;
		this.footer_date_field =
			String(this.board_doc.footer_date_field || "Modified").toLowerCase() === "creation"
				? "creation"
				: "modified";

		const base = [
			"name",
			"docstatus",
			"creation",
			"modified",
			"owner",
			this.title_field,
			this.field_name,
			"_assign",
			"_comments",
			"_liked_by",
			"_user_tags",
		];
		// Common optional fields, only if the doctype actually has them.
		["priority", "color", this.image_field, "exp_end_date", "end_date", "due_date"].forEach(
			(f) => {
				if (f && frappe.meta.has_field(this.doctype, f)) base.push(f);
			}
		);

		let configured = [];
		try {
			configured = JSON.parse(this.board_doc.fields || "[]")
				.map((f) => (typeof f === "string" ? f : f && f.fieldname))
				.filter(Boolean);
		} catch (e) {
			// ignore
		}
		// in_list_view fields power the "More Info" preview's field list when the
		// doctype has no preview popup configured — fetch them with the cards so
		// the popover needs no extra round-trip.
		const list_fields = meta.fields
			.filter(
				(df) =>
					df.in_list_view &&
					frappe.model.is_value_type(df.fieldtype) &&
					!df.hidden &&
					df.fieldname !== this.field_name
			)
			.map((df) => df.fieldname);
		this.fields = [...new Set([...base, ...configured, ...list_fields])];

		// Card field rows. Prefer the board's configured `card_fields` child
		// table; fall back to the doctype's in-list-view (then mandatory) fields
		// for boards created before it existed. The title is rendered as its own
		// first row, so drop it from the list here.
		this.card_field_list = this.compute_card_fields(meta);
		this.fields = [...new Set([...this.fields, ...this.card_field_list])];
		// Per-board label / icon from the child table. Icon → show it (label on
		// hover); no icon → show the label text next to the value.
		this.card_field_labels = {};
		this.card_field_icons = {};
		(this.board_doc.card_fields || []).forEach((f) => {
			if (!f.fieldname) return;
			if (f.label) this.card_field_labels[f.fieldname] = f.label;
			if (f.icon) this.card_field_icons[f.fieldname] = f.icon;
		});

		// Hover-preview fields: configured `preview_fields` → preview-api
		// (`in_preview`) → card fields. Label / icon overrides from the table.
		this.preview_field_list = this.compute_preview_fields(meta);
		this.fields = [...new Set([...this.fields, ...this.preview_field_list])];
		this.preview_field_labels = {};
		this.preview_field_icons = {};
		(this.board_doc.preview_fields || []).forEach((f) => {
			if (!f.fieldname) return;
			if (f.label) this.preview_field_labels[f.fieldname] = f.label;
			if (f.icon) this.preview_field_icons[f.fieldname] = f.icon;
		});
		// A text field for the preview's description snippet, if the doctype has one.
		this.desc_field = ["description", "content", "notes"].find((f) =>
			frappe.meta.has_field(this.doctype, f)
		);
		if (this.desc_field) this.fields = [...new Set([...this.fields, this.desc_field])];
		this.card_config_sig = this.card_config_signature(this.board_doc);

		// Group-by (swimlane) options: "Assigned To" first when the board shows
		// assignees, then the board's configured Group By Fields. No fallback — an
		// empty list simply hides the Group button. Keep the active choice only if
		// it is still a valid option for this board.
		this.group_by_options = this.compute_group_by_options();
		if (
			this.group_by_field &&
			!this.group_by_options.some((o) => o.fieldname === this.group_by_field)
		) {
			this.group_by_field = null;
		}

		const s = this.settings || {};
		// Clicking the card title opens the document. Turn off where not wanted.
		this.open_on_title_click =
			s.open_on_title_click !== undefined ? s.open_on_title_click : true;
		// Select badge styling: the shared defaults, with this doctype's
		// overrides layered on top (keys lowercased so lookups are exact).
		this.select_styles = { ...SELECT_STYLES };
		Object.entries(s.select_styles || {}).forEach(([value, style]) => {
			this.select_styles[value.toLowerCase()] =
				typeof style === "string" ? { theme: style } : style;
		});
	}

	/** Fields to render as card rows (configured table, else auto), sans title. */
	compute_card_fields(meta) {
		const configured = (this.board_doc.card_fields || [])
			.map((f) => f.fieldname)
			.filter((fn) => fn && frappe.meta.has_field(this.doctype, fn));
		const list = configured.length ? configured : this.default_card_fieldnames(meta);
		// Title is its own row; image sits beside it; group-by is the column.
		return list.filter(
			(fn) =>
				fn !== this.title_field &&
				fn !== "name" &&
				fn !== this.field_name &&
				fn !== this.image_field
		);
	}

	/** Auto-pick: in-list-view fields, else mandatory. Mirrors the server seed. */
	default_card_fieldnames(meta) {
		// Checks read as "Yes/No" rows — low signal on a card, so skip them in the
		// auto-pick (users can still add them explicitly via the Card Fields table).
		const usable = (df) =>
			frappe.model.is_value_type(df.fieldtype) && !df.hidden && df.fieldtype !== "Check";
		let dfs = meta.fields.filter((df) => df.in_list_view && usable(df));
		if (!dfs.length) dfs = meta.fields.filter((df) => df.reqd && usable(df));
		return dfs.map((df) => df.fieldname).slice(0, 6);
	}

	/**
	 * Board title_field when it is name or Data; otherwise doctype title_field
	 * (Data only), first Data field, or name. Matches the server seed + old-board
	 * fallback.
	 */
	resolve_title_field(meta) {
		const configured = this.board_doc.title_field;
		if (configured === "name") return "name";
		if (configured) {
			const df = frappe.meta.get_docfield(this.doctype, configured);
			if (df && df.fieldtype === "Data" && !df.hidden) return configured;
		}
		if (meta.title_field) {
			const df = frappe.meta.get_docfield(this.doctype, meta.title_field);
			if (df && df.fieldtype === "Data" && !df.hidden) return meta.title_field;
		}
		const data = meta.fields.find((df) => df.fieldtype === "Data" && !df.hidden);
		return data ? data.fieldname : "name";
	}

	/**
	 * Board image_field when it is Attach Image; else doctype image_field; else
	 * first Attach Image. Null when none — cards render without a thumb.
	 */
	resolve_image_field(meta) {
		const is_attach_image = (fn) => {
			if (!fn) return false;
			const df = frappe.meta.get_docfield(this.doctype, fn);
			return df && df.fieldtype === "Attach Image";
		};
		// Board config: trust explicit selection (user chose it knowingly)
		if (is_attach_image(this.board_doc.image_field)) return this.board_doc.image_field;
		// Doctype image_field: always allow (it's meant for display elsewhere)
		if (is_attach_image(meta.image_field)) return meta.image_field;
		// Fallback: first non-hidden Attach Image
		const first = meta.fields.find((df) => df.fieldtype === "Attach Image" && !df.hidden);
		return first ? first.fieldname : null;
	}

	/**
	 * Preview fields to render, in order:
	 * 1. Board's configured `preview_fields`
	 * 2. Doctype preview-api fields (`in_preview`, else mandatory — same as
	 *    `frappe.desk.link_preview.get_preview_data`)
	 * 3. Card fields, so the peek still has something when neither is set
	 */
	compute_preview_fields(meta) {
		const configured = (this.board_doc.preview_fields || [])
			.map((f) => f.fieldname)
			.filter((fn) => fn && frappe.meta.has_field(this.doctype, fn));
		const preview_api = this.default_preview_fieldnames(meta);
		const list = configured.length
			? configured
			: preview_api.length
			? preview_api
			: this.card_field_list || [];
		// Title, image and the group-by field head/own the preview elsewhere.
		return list.filter(
			(fn) =>
				fn !== this.title_field &&
				fn !== "name" &&
				fn !== this.field_name &&
				fn !== this.image_field
		);
	}

	/**
	 * Preview-api fieldnames for the doctype: `in_preview`, else mandatory.
	 * Mirrors `frappe.desk.link_preview.get_preview_data` (without title/image,
	 * which the hover card renders in the header).
	 */
	default_preview_fieldnames(meta) {
		const skip = new Set([this.title_field, this.image_field, "name"]);
		const usable = (df) =>
			frappe.model.is_value_type(df.fieldtype) &&
			!df.hidden &&
			df.fieldtype !== "Check" &&
			!skip.has(df.fieldname);
		let dfs = meta.fields.filter((df) => df.in_preview && usable(df));
		if (!dfs.length) dfs = meta.fields.filter((df) => df.reqd && usable(df));
		return dfs.map((df) => df.fieldname).slice(0, 6);
	}

	/** Primary action, view switcher, refresh, save filters, filter bar. */
	setup_toolbar() {
		const page = this.page;
		// "+ Add <Doctype>" (primary) — same construction as the list view:
		// { label, short_label } + the "plus" icon. Replaces, never duplicates.
		page.set_primary_action(
			{ label: __("Add {0}", [__(this.doctype)]), short_label: __("Add") },
			() => frappe.new_doc(this.doctype),
			"plus"
		);

		if (this._toolbar_for === this.doctype) return; // static bits already built
		this._toolbar_for = this.doctype;

		// Use the common view switcher component (same as List View / old Kanban).
		// Shows current board name + dropdown with all views and boards.
		this.setup_view_menu();

		page.add_action_icon(
			"refresh-cw",
			() => this.board && this.board.refresh(),
			"",
			__("Reload")
		);

		page.add_menu_item(__("Save Filters"), () => this.save_filters());

		this.setup_filter_bar();
	}

	/**
	 * Reuse the exact shared list-view switcher path (same as old Kanban).
	 */
	setup_view_menu() {
		this.show_saved_layout_menu = false;
		frappe.views.BaseList.prototype.setup_view_menu.call(this);
	}

	/**
	 * Group-by options for the Group button: "Assigned To" first (only when the
	 * board shows assignees), then the board's configured Group By Fields. No
	 * auto-fallback — an empty list hides the Group button entirely.
	 */
	compute_group_by_options() {
		const options = [];
		if (this.show_assigned_to) {
			options.push({ fieldname: "_assign", label: __("Assigned To") });
		}
		(this.board_doc.group_by_fields || []).forEach((f) => {
			if (!f.fieldname || !frappe.meta.has_field(this.doctype, f.fieldname)) return;
			const df = frappe.meta.get_docfield(this.doctype, f.fieldname);
			options.push({
				fieldname: f.fieldname,
				label: __(f.label || (df && df.label) || f.fieldname),
			});
		});
		return options;
	}

	/**
	 * Build the filter bar below the topbar with Filter + Group buttons.
	 * Similar to List View's FilterArea but placed in our dedicated $filter_bar.
	 */
	setup_filter_bar() {
		const $filter_section = this.$filter_section;
		$filter_section.empty(); // clear if rebuilding

		this.setup_filter_button($filter_section);
		this.setup_group_button($filter_section);
		this.setup_settings_button($filter_section);
		this.sync_board_height();
	}

	/**
	 * Quick filters on the left of the header — the doctype's `in_standard_filter`
	 * fields (same source as List View), excluding the column field and the active
	 * swimlane field, capped at 4 so the single-row header never wraps. Applied at
	 * query time alongside the Filter popover.
	 */
	setup_quick_filters() {
		const page = this.page;
		if (!this.$quick_filters) {
			this.$quick_filters = $(
				'<div class="standard-filter-section kanban-v2-quick-filters flex"></div>'
			).insertBefore(this.$filter_section);
		}
		// Preserve any active values so re-rendering (board/swimlane change) does
		// not silently drop the filters the user has typed.
		const preserved = {};
		(this._quick_filter_fields || []).forEach((fn) => {
			const f = page.fields_dict[fn];
			if (f) {
				const v = f.get_value();
				if (v) preserved[fn] = v;
				f.$wrapper && f.$wrapper.remove();
				delete page.fields_dict[fn];
			}
		});
		this.$quick_filters.empty();
		this._quick_filter_fields = [];

		const excluded = new Set([this.field_name, this.group_by_field].filter(Boolean));
		const meta = frappe.get_meta(this.doctype);
		const dfs = (meta?.fields || [])
			.filter(
				(df) =>
					df.in_standard_filter &&
					frappe.model.is_value_type(df.fieldtype) &&
					!excluded.has(df.fieldname) &&
					frappe.perm.has_perm(this.doctype, df.permlevel)
			)
			.slice(0, 4); // keep the header a single row

		dfs.forEach((df) => {
			page.add_field(this.quick_filter_config(df), this.$quick_filters);
			this._quick_filter_fields.push(df.fieldname);
		});

		this.seed_quick_filters();

		// Restore preserved values for fields that are still present.
		this._seeding_quick = true;
		try {
			Object.keys(preserved).forEach((fn) => {
				const field = page.fields_dict[fn];
				if (field) field.set_value(preserved[fn]);
			});
		} finally {
			this._seeding_quick = false;
		}
	}

	/** Page-field config for a quick filter (mirrors List View's standard filters). */
	quick_filter_config(df) {
		let fieldtype = df.fieldtype;
		let condition = "=";
		let options = df.options;
		if (
			[
				"Text",
				"Small Text",
				"Text Editor",
				"HTML Editor",
				"Markdown Editor",
				"Data",
				"Code",
				"Phone",
				"JSON",
				"Read Only",
			].includes(fieldtype)
		) {
			fieldtype = "Data";
			condition = "like";
		}
		if (df.fieldtype === "Select" && df.options) {
			options = df.options.split("\n");
			if (options.length && options[0] !== "") options.unshift("");
			options = options.join("\n");
		}
		return {
			fieldtype,
			label: __(df.label, null, df.parent),
			options,
			fieldname: df.fieldname,
			condition,
			is_filter: 1,
			ignore_link_validation: fieldtype === "Dynamic Link",
			onchange: () => this.on_quick_filter_change(),
		};
	}

	/** Reflect any active board filter on a quick-filter field back into its input. */
	seed_quick_filters() {
		const set = new Set(this._quick_filter_fields || []);
		this._seeding_quick = true;
		try {
			(this.filters || []).forEach(([, fn, cond, val]) => {
				if (!set.has(fn)) return;
				const field = this.page.fields_dict[fn];
				if (!field) return;
				let v = val;
				if (cond === "like" && typeof v === "string") v = v.replace(/^%+|%+$/g, "");
				field.df.match_type = cond === "like" ? "like" : "=";
				field.set_value(v);
			});
		} finally {
			this._seeding_quick = false;
		}
	}

	/** Current quick-filter inputs as filter tuples (List View get_standard_filters). */
	get_quick_filters() {
		const out = [];
		(this._quick_filter_fields || []).forEach((fn) => {
			const field = this.page.fields_dict[fn];
			if (!field) return;
			let value = field.get_value();
			// Skip empty/falsy values (matches List View); also lets Check/0 clear.
			if (!value) return;
			const match = field.df.match_type || field.df.condition || "=";
			let condition = "=";
			if (match === "like") {
				condition = "like";
				if (typeof value === "string" && !value.includes("%")) value = "%" + value + "%";
			} else if (match === "=") {
				if (typeof value === "string") value = value.replace(/^%+|%+$/g, "");
			} else {
				condition = field.df.condition || match;
			}
			out.push([this.doctype, fn, condition, value]);
		});
		return out;
	}

	/** Popover filters + quick filters + any extras. A quick filter overrides a
	 * popover filter on the same field only when it actually has a value, so a
	 * popover filter on a quick-filter field is not dropped when the input is empty. */
	get_effective_filters(extra) {
		const quick = this.get_quick_filters();
		const active = new Set(quick.map((f) => f[1]));
		const base = (this.filters || []).filter((f) => !active.has(f[1]));
		const eff = base.concat(quick);
		return extra && extra.length ? eff.concat(extra) : eff;
	}

	on_quick_filter_change() {
		if (this._seeding_quick) return;
		this._quick_reload =
			this._quick_reload || frappe.utils.debounce(() => this.reload_board_filters(), 300);
		this._quick_reload();
	}

	/** Reload the board for the current effective filter set. */
	reload_board_filters() {
		// Quick filters aren't part of this.filters, so clear apply_filters'
		// change-detection key to keep a later popover edit from being skipped.
		this._loaded_key = null;
		if (this.group_by_field) {
			this.mount_board(); // swimlanes depend on the filtered set
			return;
		}
		if (!this.provider) return;
		this.provider.setFilters(this.get_effective_filters());
		this.board.refresh();
	}

	/** Settings button — opens Board Settings (kanban_settings.bundle.js). */
	setup_settings_button($parent) {
		// Espresso button (Filter stays Bootstrap for FilterGroup chrome).
		this.$settings_btn = frappe.ui.button({
			label: __("Settings"),
			icon: "settings",
			size: "sm",
			css_class: "settings-button mr-0",
			title: __("Settings"),
			onclick: () =>
				frappe.require("kanban_settings.bundle.js", () =>
					frappe.views.open_kanban_settings(this)
				),
		});
		$parent.append(this.$settings_btn);
	}

	/**
	 * (Re)build the "Group" button in the filter bar — espresso Dropdown with
	 * layers icon + label + chevrons. Hidden when there are no group-by options.
	 */
	setup_group_button($parent) {
		const options = this.group_by_options || [];
		if (!options.length) {
			if (this.$group_dropdown) {
				this.$group_dropdown.destroy();
				this.$group_dropdown = null;
			}
			if (this.$group_wrapper) {
				this.$group_wrapper.remove();
				this.$group_wrapper = null;
			}
			return;
		}

		const active = options.find((o) => o.fieldname === this.group_by_field);
		const label_text = active ? active.label : __("Group");
		const button_opts = {
			label: label_text,
			icon: "layers",
			icon_right: "chevrons-up-down",
			size: "sm",
			css_class: "group-button",
		};

		if (!this.$group_wrapper || !this.$group_wrapper.closest(".filter-section").length) {
			this.$group_wrapper = $('<div class="group-selector">');
			this.$group_dropdown = new frappe.ui.Dropdown({
				button: button_opts,
				options: () => this.get_group_dropdown_options(),
			});
			this.$group_wrapper.append(this.$group_dropdown.$trigger);
			($parent || this.$filter_section).append(this.$group_wrapper);
		} else {
			frappe.ui.button.dress(this.$group_dropdown.$trigger, button_opts);
		}
	}

	get_group_dropdown_options() {
		const options = this.group_by_options || [];
		const items = [];

		items.push({
			label: __("None"),
			selected: !this.group_by_field,
			onclick: () => this.set_group_by(null),
		});

		options.forEach((opt) => {
			items.push({
				label: opt.label,
				selected: this.group_by_field === opt.fieldname,
				onclick: () => this.set_group_by(opt.fieldname),
			});
		});

		return items;
	}

	/** Set the active group-by field (null = ungrouped), re-render, update the menu. */
	set_group_by(fieldname) {
		const next = fieldname || null;
		if (next === (this.group_by_field || null)) return;
		this.group_by_field = next;
		this.setup_group_button(); // update the dropdown checkmarks + label
		this.setup_quick_filters(); // drop the now-active swimlane field from quick filters
		this.sync_board_height();
		this.mount_board(); // swap between the flat board and swimlanes
	}

	/**
	 * Build the Filter button in the filter bar.
	 * Uses the same FilterGroup component as List View.
	 */
	setup_filter_button($parent) {
		try {
			// Same markup + wiring as the list view's FilterArea.make_filter_list:
			// a .filter-selector with the funnel Filter button + the ✕ clear button,
			// both handed to FilterGroup so it manages the "Filters N" label and the
			// ✕ visibility/clear itself.
			const $selector = $(`
				<div class="filter-selector">
					<div class="btn-group">
						<button class="btn btn-default btn-sm filter-button">
							<span class="filter-icon button-icon">${frappe.utils.icon("funnel")}</span>
							<span class="button-label hidden-xs">${__("Filter")}</span>
						</button>
						<button class="btn btn-default btn-sm filter-x-button" title="${__("Clear all filters")}">
							<span class="filter-icon button-icon">${frappe.utils.icon("x")}</span>
						</button>
					</div>
				</div>`);

			if ($parent) {
				$parent.append($selector);
			} else {
				this.$filter_section.append($selector);
			}

			this.filter_group = new frappe.ui.FilterGroup({
				parent: $selector,
				doctype: this.doctype,
				filter_button: $selector.find(".filter-button"),
				filter_x_button: $selector.find(".filter-x-button"),
				default_filters: [],
				on_change: () => this.apply_filters(),
			});
			// FilterGroup's ✕ clears its filters but (outside a list view) doesn't
			// fire on_change — reload after it clears.
			$selector
				.find(".filter-x-button")
				.on("click", () => setTimeout(() => this.apply_filters(), 0));
			if (this.filters && this.filters.length) {
				this.filter_group.add_filters_to_filter_group(this.filters);
			}
			this.sync_filter_ui();
		} catch (e) {
			console.warn("[kanban-v2] filter setup skipped", e);
		}
	}

	/**
	 * Point the (per-doctype) filter group at the current board's filters. The
	 * filter group is built once per doctype, so switching between two boards of
	 * the same doctype otherwise leaves the previous board's filters in the UI —
	 * and opening the popover would then apply them to the new board.
	 */
	sync_filter_group_to_board() {
		if (!this.filter_group) return;
		const desired = JSON.stringify(this.filters || []);
		if (JSON.stringify(this.filter_group.get_filters() || []) === desired) {
			this.sync_filter_ui();
			return;
		}
		// Suppress the on_change → apply_filters reload while we rewrite the group;
		// mount_board already loads with this board's filters.
		this._syncing_filters = true;
		try {
			this.filter_group.clear_filters();
			if (this.filters && this.filters.length) {
				this.filter_group.add_filters_to_filter_group(this.filters);
			}
		} finally {
			this._syncing_filters = false;
		}
		this.sync_filter_ui();
	}

	/** Sync the Filter button label ("Filters N") + the "Not Saved" indicator. */
	sync_filter_ui() {
		try {
			// Also updates the button label/highlight. The ✕ button stays visible
			// as part of the group at all times, like the classic list view.
			this.filter_group.update_filter_button();
		} catch (e) {
			// ignore
		}
		this.update_saved_indicator();
	}

	/** Show "Not Saved" next to the title when filters differ from the saved set. */
	update_saved_indicator() {
		const changed =
			JSON.stringify(this.saved_filters || []) !== JSON.stringify(this.filters || []);
		if (changed) this.page.set_indicator(__("Not Saved"), "orange");
		else this.page.clear_indicator();
	}

	/** Apply filter-group filters and remount if they changed. */
	apply_filters() {
		if (this._syncing_filters) return; // programmatic re-sync, not a user edit
		if (!this.filter_group) return;
		this.filters = this.filter_group.get_filters();
		this.sync_filter_ui(); // always keep the button/indicator in sync (no reload)
		// Only reload data when the filter set actually changed (kills the blink on
		// popover open/close, which fires on_change without changing filters).
		const key = JSON.stringify(this.filters || []);
		if (key === this._loaded_key) return;
		this._loaded_key = key;
		if (this.group_by_field) {
			// Swimlanes depend on the filtered set (which lanes exist), so re-mount.
			this.mount_board();
			return;
		}
		if (!this.provider) return;
		this.provider.setFilters(this.get_effective_filters());
		this.board.refresh();
	}

	/** Persist current filters onto the Kanban Board doc. */
	save_filters() {
		frappe.db
			.set_value(
				"Kanban Board",
				this.current_board,
				"filters",
				JSON.stringify(this.filters || [])
			)
			.then(() => {
				this.saved_filters = JSON.parse(JSON.stringify(this.filters || []));
				this.update_saved_indicator();
				frappe.ui.toast({ message: __("Filters saved"), type: "success" });
			});
	}

	/** Remount the engine for the current board (flat or swimlanes). */
	mount_board() {
		// Bumped every mount so a slow async swimlane load can tell it is stale.
		this._mount_seq = (this._mount_seq || 0) + 1;
		this.teardown_board();
		this.$container.empty();
		this._loaded_key = JSON.stringify(this.filters || []); // filters the board reflects
		if (this.group_by_field) {
			this.mount_grouped_board(this._mount_seq);
		} else {
			this.mount_flat_board();
		}
	}

	/** A data provider, optionally with extra (swimlane) filters merged in. */
	make_provider(extra_filters) {
		const filters = this.get_effective_filters(extra_filters);
		return new frappe.kanban_v2.FrappeDataProvider({
			doctype: this.doctype,
			board_name: this.current_board,
			reportview_args: {
				doctype: this.doctype,
				fields: JSON.stringify(this.fields),
				order_by: "modified desc",
				filters: JSON.stringify(filters),
			},
		});
	}

	/** Engine options shared by the flat board and every swimlane board. */
	board_options(provider, opts = {}) {
		const s = this.settings || {};
		// Developer callbacks from settings are merged on top: onSelectionChange runs
		// BOTH (so the selection bar keeps working); everything else the developer
		// supplies overrides the default.
		const base_callbacks = {
			onCardOpen: (card) => frappe.set_route("Form", this.doctype, card.name),
			onSelectionChange: opts.onSelectionChange || ((ids) => this.update_selection_bar(ids)),
			onMoveError: (mv, err) => {
				frappe.ui.toast({
					message: __("Could not move {0}", [mv.cardId]),
					type: "error",
				});
				console.error("[kanban-v2] move failed", err);
			},
			// "+ Add {Doctype}" opens the new-document form, pre-filled with the
			// column's group-by value + active "=" filters.
			onAddCard: (columnId) => this.add_document(columnId),
		};
		return {
			provider,
			groupBy: this.field_name,
			pageLength: opts.pageLength || 20,
			// Swimlane boards are sized to their content (no inner scroll), so a
			// virtualized window would under-render — the caller turns it off.
			virtualization: opts.virtualization !== undefined ? opts.virtualization : true,
			selection: "multi",
			// Loading-skeleton column count — the board config already lists them
			// (excluding archived, to match the columns the provider returns).
			skeletonColumns:
				(this.board_doc?.columns || []).filter((c) => c.status !== "Archived").length || 3,
			addCardLabel: __("Add {0}", [__(this.doctype)]),
			renderCard: s.renderCard
				? (card, el, ctx) => s.renderCard(card, el, ctx, this)
				: (card, el) => this.render_card(card, el),
			renderColumnHeader: s.renderColumnHeader,
			renderEmptyState: s.renderEmptyState,
			callbacks: this.merge_callbacks(base_callbacks, s.callbacks || {}),
			// Any extra engine options (e.g. addColumn, pageLength overrides).
			...(s.options || {}),
		};
	}

	/** Mount a single ungrouped board. */
	mount_flat_board() {
		const provider = this.make_provider();
		this.provider = provider; // kept so filter changes reload in place
		this.board = new frappe.kanban_v2.KanbanVanilla(
			this.$container[0],
			this.board_options(provider)
		);
	}

	/**
	 * Swimlane view: split the board into horizontal bands by `group_by_field`.
	 * Each lane is an independent board of that group's cards, so the engine is
	 * reused untouched and there is no cross-lane drag — grouping is view-only.
	 */
	async mount_grouped_board(seq) {
		const field = this.group_by_field;
		this.$container.html(
			`<div class="text-ink-gray-5 text-sm p-4">${__("Loading groups…")}</div>`
		);
		let data;
		try {
			data = await frappe.xcall(
				"frappe.desk.doctype.kanban_board.kanban_board.get_kanban_group_values",
				{
					board_name: this.current_board,
					group_by: field,
					filters: JSON.stringify(this.filters || []),
				}
			);
		} catch (e) {
			if (seq === this._mount_seq) {
				this.show_empty({
					icon: "alert-circle",
					title: __("Could not load groups."),
				});
			}
			return;
		}
		// A newer mount (board switch, group change, filter reload) superseded us.
		if (seq !== this._mount_seq || this.group_by_field !== field) return;

		const lanes = (data.lanes || []).slice();
		if (data.unset) {
			lanes.push({ value: null, label: __("Not set"), count: data.unset, unset: true });
		}
		this.$container.empty();
		if (!lanes.length) {
			this.show_empty({
				icon: "layers",
				title: __("No cards to group."),
			});
			return;
		}
		this.board = new frappe.views.KanbanV2GroupedBoard(this, field, lanes);
	}

	/** Provider filter restricting a board to one swimlane's cards. */
	lane_filter(field, lane) {
		if (field === "_assign") {
			return lane.unset
				? [[this.doctype, "_assign", "is", "not set"]]
				: [[this.doctype, "_assign", "like", `%${lane.value}%`]];
		}
		return lane.unset
			? [[this.doctype, field, "is", "not set"]]
			: [[this.doctype, field, "=", lane.value]];
	}

	/** Human label for a swimlane header. */
	lane_label(field, lane) {
		if (lane.unset) return __("Not set");
		if (field === "_assign") return frappe.user_info(lane.value).fullname || lane.value;
		return __(lane.label != null ? lane.label : lane.value);
	}

	/**
	 * Merge developer callbacks over the page's internal ones. onSelectionChange
	 * composes (both run) so the selection bar keeps working; for every other key
	 * the developer's callback wins, and brand-new callbacks are just added.
	 */
	merge_callbacks(base, custom) {
		const out = {};
		const compose = new Set(["onSelectionChange"]);
		for (const k of new Set([...Object.keys(base), ...Object.keys(custom)])) {
			const b = base[k];
			const c = custom[k];
			if (b && c && compose.has(k)) {
				out[k] = (...args) => {
					b(...args);
					return c(...args);
				};
			} else {
				out[k] = c || b;
			}
		}
		return out;
	}

	/** Open a new doc prefilled with this column's group-by value. */
	add_document(columnId) {
		// Prefill the column's group-by value + any active "=" filters.
		const values = { [this.field_name]: columnId };
		(this.filters || []).forEach((f) => {
			if (f[2] === "=") values[f[1]] = f[3];
		});

		// Doctypes with a custom create route: use the standard flow.
		if (frappe.create_routes && frappe.create_routes[this.doctype]) {
			frappe.route_options = { ...values };
			return frappe.new_doc(this.doctype, values);
		}

		// route_options / get_new_doc DROP no_copy fields (e.g. Task.status), so
		// frappe.new_doc alone can't preset the column value. Build the doc, set
		// the values directly on it, then open quick-entry / the full form with
		// that prepared doc — same idea as the classic kanban's inline add.
		frappe.route_options = { ...values };
		frappe.model.with_doctype(this.doctype, () => {
			const doc = frappe.model.get_new_doc(this.doctype, null, null, true);
			Object.assign(doc, values);
			frappe.ui.form.make_quick_entry(this.doctype, null, null, doc);
		});
	}

	/** Paint card title, fields, and footer into `el`. */
	render_card(card, el) {
		// Optional color accent (left border) from a `color` field.
		if (card.color) el.style.borderLeft = `3px solid ${card.color}`;

		const rows = document.createElement("div");
		// Slightly more air between fields than a form list — title still
		// sits a touch above the pack (see .kn-title-row margin).
		rows.className = "flex flex-col gap-1";

		// Title row — always first, as a clickable link.
		rows.appendChild(this.title_row(card));

		// Configured field rows — icon (label on hover) when set on the child
		// row, otherwise the label text beside the value.
		for (const fieldname of this.card_field_list) {
			const df = frappe.meta.get_docfield(this.doctype, fieldname);
			if (df) rows.appendChild(this.field_row(card, df));
		}
		el.appendChild(rows);
		el.appendChild(this.card_footer(card));

		// Right-click context menu — defaults + settings.card_context_menu.
		this.bind_context_menu(el, card);
	}

	/** The card's last row: assignees + tags on left, date on right. */
	card_footer(card) {
		const foot = document.createElement("div");
		foot.className = "flex items-center justify-between gap-2 mt-3";

		const left = document.createElement("div");
		left.className = "inline-flex items-center gap-2 min-w-0";

		if (this.show_assigned_to) {
			left.appendChild(this.assign_button(card));
		}
		const tags = this.card_tags(card);
		if (tags) left.appendChild(tags);

		if (left.childNodes.length) foot.appendChild(left);

		const age = this.age_badge(card);
		if (age) {
			if (!left.childNodes.length) age.classList.add("ms-auto");
			foot.appendChild(age);
		}

		if (!foot.childNodes.length) return document.createDocumentFragment();
		return foot;
	}

	/** Standard badge tags on cards. Shows 1 tag (truncated) + "+N" with hover tooltip. */
	card_tags(card) {
		if (!this.show_tags_on_card) return null;
		const tags = String(card._user_tags || "")
			.split(",")
			.map((t) => t.trim())
			.filter(Boolean);
		if (!tags.length) return null;

		const wrap = document.createElement("div");
		wrap.className = "inline-flex items-center gap-1";

		// Show first tag as simple badge.
		wrap.appendChild(this.tag_badge(tags[0], "lg"));

		// "+N" count with tooltip showing remaining tags.
		if (tags.length > 1) {
			const more = document.createElement("span");
			more.className = "text-xs text-ink-gray-5 cursor-default";
			more.textContent = `+${tags.length - 1}`;
			const rest = tags.slice(1).join(", ");
			frappe.ui.tooltip(more, { text: rest, side: "top", delay: 100 });
			wrap.appendChild(more);
		}

		return wrap;
	}

	/** Hash a string into a stable espresso theme colour (badge / avatar). */
	hash_theme(str, themes = ["blue", "green", "amber", "red", "violet"]) {
		let hash = 0;
		const s = String(str || "");
		for (let i = 0; i < s.length; i++) {
			hash = (hash * 31 + s.charCodeAt(i)) % 997;
		}
		return themes[hash % themes.length];
	}

	/** Standard frappe badge element for a tag. */
	tag_badge(tag, size = "md") {
		// Truncate tag text to prevent overflow; full tag shown via tooltip.
		const MAX_TAG_CHARS = 15;
		const label = tag.length > MAX_TAG_CHARS ? tag.slice(0, MAX_TAG_CHARS) + "…" : tag;
		const $badge = frappe.ui.badge({
			label,
			theme: this.hash_theme(tag),
			size,
			title: tag, // Full tag in tooltip
		});
		return $badge[0];
	}

	/** One assignee es-avatar: user photo, or a colour-themed initial fallback. */
	assignee_avatar(user, size = "md") {
		const info = frappe.user_info(user);
		return frappe.ui.avatar({
			image: info.image || undefined,
			label: info.fullname || user,
			theme: this.hash_theme(user),
			size,
		})[0];
	}

	/**
	 * How long since the chosen footer timestamp (modified or creation), e.g.
	 * "12 d" — exact time on hover. Ghost badge: no fill, so it reads as quiet
	 * text next to the assignees while the component keeps the icon and text
	 * in step.
	 */
	age_badge(card) {
		const when = card[this.footer_date_field] || card.modified || card.creation;
		if (!when) return null;
		const $badge = frappe.ui.badge({
			icon: "clock",
			label: frappe.datetime.prettyDate(when, true),
			variant: "ghost",
			size: "sm",
		});
		const tip =
			this.footer_date_field === "creation"
				? __("Created {0}", [frappe.datetime.str_to_user(when)])
				: __("Updated {0}", [frappe.datetime.str_to_user(when)]);
		frappe.ui.tooltip($badge, { text: tip });
		return $badge[0];
	}

	/**
	 * Title as the card's only loud line — medium weight + darkest ink so the
	 * field rows below can stay quiet without competing. Optional image thumb
	 * sits in front when the board has an image field and the card has a value.
	 */
	title_row(card) {
		const row = document.createElement("div");
		row.className = "kn-frow kn-title-row flex items-center gap-2 min-w-0 mb-0.5";

		const title_df = frappe.meta.get_docfield(this.doctype, this.title_field);
		const title_text =
			this.plain_text(card[this.title_field], title_df && title_df.fieldtype) || card.name;
		const image_url = this.image_field && card[this.image_field];
		if (this.image_field) {
			// Shared Avatar handles both image and initials fallback.
			row.appendChild(
				frappe.ui.avatar({
					image: image_url || undefined,
					label: title_text || "?",
					size: "md",
					shape: "square",
				})[0]
			);
		}

		const title = document.createElement("div");
		title.className = "kn-card-title text-sm-medium text-ink-gray-9 min-w-0";
		title.textContent = title_text;
		if (this.open_on_title_click) {
			title.classList.add("cursor-pointer");
			title.setAttribute("role", "link");
			title.setAttribute("tabindex", "0");
			const open = (e) => {
				e.stopPropagation();
				frappe.set_route("Form", this.doctype, card.name);
			};
			title.addEventListener("click", open);
			title.addEventListener("keydown", (e) => {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					open(e);
				}
			});
		}
		row.appendChild(title);
		// Hovering the title reveals the document preview (frappe.ui.HoverCard).
		this.bind_more_info_hovercard(title, card);
		return row;
	}

	/**
	 * One field row. Always horizontal: icon (or text label) on the left,
	 * value on the right. Empty rows show "Set {label}…" for icon mode,
	 * or a dash for text-label mode.
	 */
	field_row(card, df) {
		const label = this.field_label(df);
		const icon = (this.card_field_icons || {})[df.fieldname];
		const row = document.createElement("div");

		// Both icon and text-label rows are horizontal: label/icon on the left, value on the right.
		row.className = "kn-frow flex items-center gap-2 min-w-0";
		if (icon) {
			row.appendChild(this.row_icon(icon, label));
		} else {
			const text = document.createElement("span");
			text.className = "text-xs text-ink-gray-5 shrink-0";
			text.textContent = label + ":";
			text.title = label;
			row.appendChild(text);
		}

		const value = this.field_value(card, df);
		if (value) {
			row.appendChild(value);
		} else {
			const hint = document.createElement("div");
			hint.className = "kn-fempty text-sm text-ink-gray-4 truncate";
			hint.textContent = icon ? __("Set {0}…", [label]) : "—";
			row.appendChild(hint);
		}
		return row;
	}

	/** The board's own label for a field, else the doctype's. */
	field_label(df) {
		const custom = (this.card_field_labels || {})[df.fieldname];
		return __(custom || df.label || df.fieldname);
	}

	/**
	 * A muted leading icon that names its field on hover. Uses the espresso
	 * tooltip instead of a `title` attribute — the icon is an inline SVG, and
	 * a native tooltip on its wrapper does not reliably appear when hovering
	 * the SVG itself.
	 */
	row_icon(icon, label) {
		const span = document.createElement("span");
		span.className =
			"kn-ficon inline-flex items-center justify-center shrink-0 size-4 text-ink-gray-4";
		span.setAttribute("aria-label", label);
		span.innerHTML = this.safe_icon(icon);
		frappe.ui.tooltip(span, { text: label, side: "top", delay: 200 });
		return span;
	}

	/**
	 * SVG markup for a lucide icon name, but only for names that look like a
	 * lucide id ([a-z0-9-]). Card/preview icon names come from the board's config
	 * (user-editable child table) and are fed to innerHTML, so an unvalidated
	 * name like `x"><img onerror=…>` would break out of the `href` attribute.
	 * Returns "" for anything else.
	 */
	safe_icon(icon) {
		const name = String(icon || "").trim();
		if (!name || !/^[a-z0-9-]+$/i.test(name)) return "";
		return frappe.utils.icon(name, "sm");
	}

	/** Fieldtypes whose stored value is markup or markdown, not display text. */
	is_rich_text(fieldtype) {
		return ["Text Editor", "Markdown Editor", "HTML", "HTML Editor", "Comment"].includes(
			fieldtype
		);
	}

	/**
	 * Prep a rich-text value for markdown rendering: decode literal escape
	 * sequences (\n, \t, \*) and convert legacy textile headings ("h4. …") to
	 * markdown. Only used for rich-text fields, never plain field values.
	 */
	normalize_rich_text(raw) {
		let text = String(raw);
		if (text.includes("\\n")) {
			text = text
				.replace(/\\n/g, "\n")
				.replace(/\\t/g, "\t")
				.replace(/\\([*_`])/g, "$1");
		}
		return text.replace(/^\s*h([1-6])\.\s+/gm, (_m, n) => "#".repeat(+n) + " ");
	}

	/**
	 * Readable single-line text for a value that may carry markup: markdown is
	 * turned into HTML first, then tags are dropped and entities decoded, and
	 * the line breaks / indentation the markup leaves behind are squashed into
	 * single spaces so it fits one card row.
	 * @param {string} [fieldtype] Field's type — decides whether markdown is
	 * rendered first and keeps Code values byte-for-byte.
	 */
	plain_text(value, fieldtype) {
		let text = value == null ? "" : String(value);
		if (!text) return "";
		// Markdown is nearly plain already, but "## Title" / "**bold**" is noise
		// on a card — render it (rich-text fields only), then strip it like any HTML.
		if (fieldtype === "Markdown Editor" || this.is_rich_text(fieldtype)) {
			text = frappe.markdown(this.normalize_rich_text(text));
		}
		// Code is text by definition: "<div>" in it is content, not markup.
		// html2text also decodes entities (&amp; → &), which stripping cannot.
		if (fieldtype !== "Code" && /<[a-z!/][^>]*>/i.test(text)) {
			text = frappe.utils.html2text(text);
		}
		return text.replace(/\s+/g, " ").trim();
	}

	/**
	 * Type-aware value element for a field, or null when empty. Link→User shows
	 * an avatar + name; Select shows a badge on the card (plain text in the
	 * hover preview); rich text is flattened to one readable line; everything
	 * else is formatted with frappe.format.
	 * Metadata stays one step quieter than the title (ink-gray-6).
	 * @param {{ plain_select?: boolean }} [opts] When true, Select values render
	 * as text instead of a badge (used by the hover preview).
	 */
	field_value(card, df, opts = {}) {
		const val = card[df.fieldname];
		if (val === undefined || val === null || val === "") return null;

		const el = document.createElement("div");
		el.className = "text-sm text-ink-gray-6 truncate min-w-0";

		if (df.fieldtype === "Link" && df.options === "User") {
			// A 16px avatar keeps the row on the same rhythm as the icon column.
			// The provider has already cached these users, so the name is here.
			const info = frappe.user_info(val);
			el.className = "inline-flex items-center gap-1.5 text-sm text-ink-gray-6 min-w-0";
			el.innerHTML = `${frappe.ui.avatar.html({
				image: info.image || undefined,
				label: info.fullname || val,
				theme: this.hash_theme(val),
				size: "xs",
				css_class: "shrink-0",
			})}<span class="truncate">${frappe.utils.escape_html(info.fullname || val)}</span>`;
			this.tip_if_long(el, info.fullname || val);
			return el;
		}

		if (df.fieldtype === "Select") {
			// Card: badge only when we have a known icon (priority/status). Other
			// Select values stay plain muted text so they match Link/Data rows.
			// Hover preview: always plain text — more room, less noise.
			if (opts.plain_select) {
				el.textContent = __(val);
				this.tip_if_long(el, __(val));
				return el;
			}
			const style = this.select_style(val);
			if (style.icon) {
				el.className = "min-w-0";
				el.innerHTML = frappe.ui.badge.html({
					label: __(val),
					size: "md",
					theme: style.theme,
					icon: style.icon,
				});
			} else {
				el.textContent = __(val);
				this.tip_if_long(el, __(val));
			}
			return el;
		}

		if (df.fieldtype === "Check") {
			el.textContent = val ? __("Yes") : __("No");
			return el;
		}

		// Dates stay short on the card; the row icon/label already names the field.
		if (df.fieldtype === "Date" || df.fieldtype === "Datetime") {
			let text;
			if (df.fieldtype === "Datetime") {
				const [date_part, time_part] = String(val).split(" ");
				text =
					!time_part || time_part.startsWith("00:00:00")
						? frappe.datetime.str_to_user(date_part, false, true)
						: frappe.datetime.str_to_user(val);
			} else {
				text = frappe.datetime.str_to_user(val, false, true);
			}
			el.textContent = text;
			frappe.ui.tooltip(el, {
				text: frappe.datetime.str_to_user(val),
				side: "top",
			});
			return el;
		}

		// Rich text (and Code) would inject whole blocks of markup into a row, so
		// render it as one plain line and keep the longer text on hover.
		if (this.is_rich_text(df.fieldtype) || df.fieldtype === "Code") {
			const text = this.plain_text(val, df.fieldtype);
			if (!text) return null;
			el.textContent = text;
			this.tip_if_long(el, text);
			return el;
		}

		el.innerHTML = frappe.format(val, df, { inline: true }, card);
		// Truncated values still reveal the full string on hover.
		this.tip_if_long(el, this.plain_text(val, df.fieldtype) || String(val));
		return el;
	}

	/** Attach a tooltip when the value is long enough to likely ellipsize. */
	tip_if_long(el, text) {
		if (!text || String(text).length <= 28) return;
		frappe.ui.tooltip(el, {
			text: frappe.ellipsis(String(text), 280),
			side: "top",
			delay: 200,
		});
	}

	/**
	 * Badge theme + icon for a Select value (priority signal bars, status
	 * circles, etc.). Falls back to frappe.utils.guess_colour for unknown
	 * values — a badge-compatible theme name, no icon.
	 */
	select_style(value) {
		const style = this.select_styles[String(value).trim().toLowerCase()];
		if (typeof style === "string") return { theme: style };
		return style || { theme: frappe.utils.guess_colour(value) };
	}

	/** Attach a frappe.ui.ContextMenu to a card (right-click). */
	bind_context_menu(el, card) {
		// Pass a function so the menu (esp. "Move to") reflects the card's
		// current column each time it opens, even after the card is moved.
		new frappe.ui.ContextMenu({
			target: $(el),
			options: () => this.card_context_menu_items(card),
		});
	}

	/** Columns this card can be moved to (every column except its current one). */
	move_to_items(card) {
		const cols = (this.board && this.board.engine.state.columns) || [];
		const current = card[this.field_name];
		return cols
			.filter((c) => c.id !== current)
			.map((c) => ({
				label: __(c.title || c.id),
				onclick: () => this.board.engine.applyMove(card.name, current, c.id, 0),
			}));
	}

	/** Default card menu items, plus settings.card_context_menu extras. */
	card_context_menu_items(card) {
		const move_targets = this.move_to_items(card);
		const items = [
			{
				label: __("Open in New Tab"),
				icon: "external-link",
				onclick: () =>
					window.open(
						`/app/${frappe.router.slug(this.doctype)}/${encodeURIComponent(card.name)}`
					),
			},
			{
				label: __("Copy Link"),
				icon: "link",
				onclick: () => {
					frappe.utils.copy_to_clipboard(
						`${frappe.urllib.get_base_url()}/app/${frappe.router.slug(
							this.doctype
						)}/${encodeURIComponent(card.name)}`
					);
				},
			},
			{
				label: __("Move to"),
				icon: "move-right",
				submenu: move_targets,
				condition: () => move_targets.length > 0,
			},
			{
				label: __("Delete"),
				icon: "trash-2",
				theme: "red",
				onclick: () => this.confirm_delete([card.name], () => this.board.refresh()),
			},
		];

		// Extras from frappe.kanban_v2.settings[doctype] (any app via hook).
		const s = this.settings || {};
		if (typeof s.card_context_menu === "function") {
			const extra = s.card_context_menu(card, this) || [];
			if (Array.isArray(extra)) items.push(...extra);
		}
		return items;
	}

	/** Reveal the document preview when hovering the card title. */
	bind_more_info_hovercard(title, card) {
		const hc = new frappe.ui.HoverCard(title, {
			side: "right",
			align: "start",
			css_class: "kn-mi-hc",
			content: () => this.more_info_content(card, () => hc.close()),
		});
	}

	/**
	 * Hover-preview body — a record peek, distinct from the card: doctype icon +
	 * title + id, an optional cover image and description, a two-column grid of
	 * the configured preview fields (type-aware values, Select → icon badge), and
	 * a footer band gathering people & activity (assignees · tags · comments ·
	 * likes) when any of those are present. Built entirely from data already
	 * fetched with the cards.
	 */
	more_info_content(card, close) {
		const wrap = document.createElement("div");
		wrap.className = "kn-mi flex flex-col w-full";

		// Cover image (board image field), when present.
		// Uses blur-fill technique: blurred bg (cover) + sharp fg (contain) for a
		// seamless look regardless of aspect ratio.
		const image = this.image_field && card[this.image_field];
		if (image) {
			const banner = document.createElement("div");
			banner.className = "kn-mi-banner w-full";
			// JSON.stringify quotes/escapes so ', (, ) in the URL can't break url(...).
			const url = `url(${JSON.stringify(String(image))})`;
			// Blurred background layer.
			const bg = document.createElement("div");
			bg.className = "kn-mi-banner-bg";
			bg.style.backgroundImage = url;
			banner.appendChild(bg);
			// Sharp foreground layer (contained).
			const fg = document.createElement("div");
			fg.className = "kn-mi-banner-fg";
			fg.style.backgroundImage = url;
			banner.appendChild(fg);
			wrap.appendChild(banner);
		}

		// Header: icon · title (link) · id.
		const header = document.createElement("div");
		header.className = "kn-mi-header flex items-start gap-2 px-4 pt-3 w-full";
		// Only show an icon when the doctype actually has a usable one — a blank
		// square says nothing.
		const icon_html = this.doctype_icon_html();
		if (icon_html) {
			const icon = document.createElement("span");
			icon.className = "inline-flex items-center shrink-0 mt-1 text-ink-gray-6";
			icon.innerHTML = icon_html;
			header.appendChild(icon);
		}

		const header_text = document.createElement("div");
		header_text.className = "min-w-0 flex-1";
		const title = document.createElement("div");
		title.className = "kn-mi-title text-base-semibold text-ink-gray-9 cursor-pointer";
		const title_df = frappe.meta.get_docfield(this.doctype, this.title_field);
		title.textContent =
			this.plain_text(card[this.title_field], title_df && title_df.fieldtype) || card.name;
		title.addEventListener("click", () => {
			close && close();
			frappe.set_route("Form", this.doctype, card.name);
		});
		header_text.appendChild(title);
		const id = document.createElement("div");
		id.className = "text-xs text-ink-gray-5 mt-1";
		id.textContent = card.name;
		header_text.appendChild(id);
		header.appendChild(header_text);
		wrap.appendChild(header);

		// Check if preview_fields includes a rich-text field — if so, skip built-in desc_field
		// to avoid duplication. Rich text fields in preview are rendered separately below.
		const preview_has_rich_text = this.preview_field_list.some((fn) => {
			const df = frappe.meta.get_docfield(this.doctype, fn);
			return df && this.is_rich_text(df.fieldtype);
		});
		if (this.desc_field && !preview_has_rich_text) {
			const d = this.description_el(card);
			if (d) wrap.appendChild(d);
		}

		// Split preview fields into short (grid) and rich-text (full-width below).
		const short_fields = [];
		const rich_fields = [];
		for (const fn of this.preview_field_list) {
			const df = frappe.meta.get_docfield(this.doctype, fn);
			if (!df) continue;
			if (this.is_rich_text(df.fieldtype)) {
				rich_fields.push({ fn, df });
			} else {
				short_fields.push({ fn, df });
			}
		}

		// Two-column property grid — only short fields that have a value.
		const props = document.createElement("div");
		props.className = "kn-mi-props px-4 pt-3 w-full";
		for (const { fn, df } of short_fields) {
			const value = this.field_value(card, df, { plain_select: true });
			if (!value) continue;
			const cell = document.createElement("div");
			cell.className = "min-w-0";
			const label = this.preview_field_labels[fn] || __(df.label || df.fieldname);
			const icon = (this.preview_field_icons || {})[fn];
			const k = document.createElement("div");
			// Fixed hovercard width — labels can truncate; full name on title.
			k.className = "text-sm text-ink-gray-5 flex items-center gap-1 min-w-0";
			if (icon) {
				// No tooltip — the label sits next to the icon in the preview.
				const span = document.createElement("span");
				span.className =
					"kn-ficon inline-flex items-center justify-center shrink-0 size-4 text-ink-gray-4";
				span.innerHTML = this.safe_icon(icon);
				k.appendChild(span);
			}
			const text = document.createElement("span");
			text.className = "truncate";
			text.textContent = label;
			text.title = label;
			k.appendChild(text);
			cell.appendChild(k);
			value.classList.add("mt-1", "kn-mi-val");
			value.classList.remove("truncate");
			cell.appendChild(value);
			props.appendChild(cell);
		}
		if (props.childNodes.length) wrap.appendChild(props);

		// Rich-text fields — render as sanitized HTML, full width, below the grid.
		for (const { fn, df } of rich_fields) {
			const val = card[fn];
			if (val === undefined || val === null || val === "") continue;
			const section = this.rich_text_preview_section(val, df, fn);
			if (section) wrap.appendChild(section);
		}

		const foot = this.preview_footer(card);
		if (foot) {
			wrap.appendChild(foot);
		} else if (wrap.lastElementChild) {
			// No footer — give the last body section room above the card edge.
			wrap.lastElementChild.classList.add("pb-3");
		}
		return wrap;
	}

	/**
	 * Render a rich-text field as a full-width section with label and sanitized HTML.
	 * Used for Text Editor, HTML, Markdown fields in preview — they get their own
	 * block instead of being crammed into the 2-column grid.
	 */
	rich_text_preview_section(val, df, fieldname) {
		// Always render as markdown (handles both pure markdown and mixed HTML).
		const html = frappe.markdown(this.normalize_rich_text(val));
		if (!html || !html.trim()) return null;

		const section = document.createElement("div");
		section.className = "kn-mi-rich px-4 pt-3 w-full";

		// Label header with icon if configured.
		const label = this.preview_field_labels[fieldname] || __(df.label || df.fieldname);
		const icon = (this.preview_field_icons || {})[fieldname];
		const header = document.createElement("div");
		header.className = "text-sm text-ink-gray-5 flex items-center gap-1 mb-1";
		if (icon) {
			const span = document.createElement("span");
			span.className =
				"kn-ficon inline-flex items-center justify-center shrink-0 size-4 text-ink-gray-4";
			span.innerHTML = this.safe_icon(icon);
			header.appendChild(span);
		}
		const text = document.createElement("span");
		text.textContent = label;
		header.appendChild(text);
		section.appendChild(header);

		// Sanitized HTML content — clamped to ~3 lines via CSS.
		const content = document.createElement("div");
		content.className = "kn-mi-rich-content text-p-sm text-ink-gray-6";
		content.innerHTML = this.safe_html(html);
		section.appendChild(content);

		return section;
	}

	/**
	 * The doctype's own icon for the preview header. A doctype icon may be a
	 * lucide name, a legacy Font Awesome class (e.g. "fa fa-check"), or an emoji;
	 * render each correctly and fall back to a generic doc icon.
	 */
	doctype_icon_html() {
		const icon = (this.meta.icon || "").trim();
		// No usable doctype icon → show none (a blank square says nothing). Legacy
		// Font Awesome classes usually aren't loaded in desk, so treat them as none.
		if (!icon || /(^|\s)(fa|fas|far|fab|glyphicon)(\s|-)/.test(icon)) return "";
		// A real lucide name resolves to <use href="#icon-<name>">.
		const html = frappe.utils.icon(icon, "sm");
		if (html.includes(`#icon-${icon}"`)) return html;
		// An emoji or symbol shows as text; anything else, show nothing.
		if (![...icon].every((c) => /[a-z0-9-]/i.test(c))) {
			return `<span class="text-base">${frappe.utils.escape_html(icon)}</span>`;
		}
		return "";
	}

	/**
	 * Sanitize markup before innerHTML. remove_script_and_style only drops
	 * <script>/<style>/… tags and returns the string verbatim when none are
	 * present — so onerror / javascript: URIs would still run. Strip those too.
	 * (Server sanitize_html covers normal saves; this is the client last line.)
	 */
	safe_html(html) {
		const root = document.createElement("div");
		root.innerHTML = frappe.dom.remove_script_and_style(html || "");
		root.querySelectorAll("*").forEach((el) => {
			for (const attr of [...el.attributes]) {
				const name = attr.name.toLowerCase();
				if (name.startsWith("on")) {
					el.removeAttribute(attr.name);
					continue;
				}
				if (!["href", "src", "action", "formaction", "xlink:href"].includes(name)) {
					continue;
				}
				// Match browser URL parsing: drop tab/newline/CR anywhere, then
				// leading C0 controls, before testing the scheme.
				const bare = String(attr.value)
					.replace(/[\t\n\r]/g, "")
					.replace(/^[\u0000-\u0020]+/, "");
				if (/^(javascript|vbscript):/i.test(bare)) {
					el.removeAttribute(attr.name);
				} else if (/^data:/i.test(bare) && !/^data:image\//i.test(bare)) {
					el.removeAttribute(attr.name);
				}
			}
		});
		return root.innerHTML;
	}

	/**
	 * The description snippet. For editor fields (Text Editor / HTML / Markdown)
	 * the stored value is markup, so render it — sanitized — and let CSS clamp
	 * and flatten it. Plain fields fall back to a text excerpt.
	 */
	description_el(card) {
		const df = frappe.meta.get_docfield(this.doctype, this.desc_field);
		const val = card[this.desc_field];
		if (val === undefined || val === null || val === "") return null;
		const ft = df && df.fieldtype;
		const d = document.createElement("div");
		d.className = "kn-mi-desc text-p-sm text-ink-gray-6 px-4 pt-2 w-full";
		if (ft === "Markdown Editor" || this.is_rich_text(ft)) {
			// frappe.markdown handles both pure markdown and mixed HTML+markdown.
			d.innerHTML = this.safe_html(frappe.markdown(this.normalize_rich_text(val)));
		} else {
			d.textContent = frappe.ellipsis(this.plain_text(val, ft), 160);
		}
		return d;
	}

	/**
	 * Footer band: assignees · tags · comments · likes.
	 * Omitted entirely when there is nothing to show — no empty strip or divider.
	 */
	preview_footer(card) {
		const assignees = this.preview_assignees(card);
		const tags = String(card._user_tags || "")
			.split(",")
			.map((t) => t.trim())
			.filter(Boolean);
		const comments = this.parse_json_list(card._comments).length;
		const likes = this.parse_json_list(card._liked_by).length;
		// Nothing on either side → skip the footer so the card ends on content.
		if (!assignees && !tags.length && !comments && !likes) return null;

		const foot = document.createElement("div");
		// Single row: assignees (left, fixed) | tags + stats (right, wrapping).
		foot.className = "kn-mi-foot flex items-start gap-3 px-4 pb-2 mt-3 w-full";

		// Assignees on the left, don't shrink.
		if (assignees) {
			assignees.classList.add("shrink-0");
			foot.appendChild(assignees);
		}

		// Right side: tags (wrapping) + stats, taking remaining space.
		const right = document.createElement("div");
		right.className = `flex flex-wrap items-center gap-1.5 min-w-0${
			assignees ? " flex-1 justify-end" : " ms-auto"
		}`;

		// Tags with icon.
		if (tags.length) {
			const icon = document.createElement("span");
			icon.className = "text-ink-gray-5 shrink-0";
			icon.innerHTML = frappe.utils.icon("tag", "sm");
			right.appendChild(icon);
			tags.forEach((tag) => right.appendChild(this.tag_badge(tag, "md")));
		}

		// Stats (comments/likes) after tags.
		if (comments || likes) {
			const stats = document.createElement("span");
			stats.className = "inline-flex items-center gap-2 text-ink-gray-5 shrink-0";
			if (comments) stats.appendChild(this.preview_stat("message-square", comments));
			if (likes) stats.appendChild(this.preview_stat("heart", likes));
			right.appendChild(stats);
		}

		if (right.childNodes.length) foot.appendChild(right);
		return foot;
	}

	/** Read-only assignee stack for the preview footer; null when unassigned. */
	preview_assignees(card) {
		if (!this.show_assigned_to) return null;
		return this.assign_stack(card, { interactive: false });
	}

	preview_stat(icon, n) {
		const span = document.createElement("span");
		span.className = "inline-flex items-center gap-1 text-xs";
		span.innerHTML = `${frappe.utils.icon(icon, "sm")}${n}`;
		return span;
	}

	/**
	 * Overlapping assignee avatar stack. Interactive mode wires hovercards and
	 * always ends with a "+" add chip (even when the card has no assignees).
	 */
	assign_stack(card, { interactive = false } = {}) {
		const users = this.parse_json_list(card._assign);
		if (!interactive && !users.length) return null;

		const group = document.createElement("div");
		// Overlap + ring live in .kn-assign-group (no negative-margin utility).
		group.className = "kn-assign-group inline-flex items-center";
		if (interactive) {
			group.addEventListener("click", (e) => e.stopPropagation());
		}

		const shown = users.slice(0, 2);
		const extra = users.slice(2);
		shown.forEach((user) => {
			const av = this.assignee_avatar(user, "md");
			av.classList.add("kn-stack-av");
			group.appendChild(av);
			if (interactive) this.bind_assignee_hovercard(av, user, card);
		});

		if (extra.length) {
			const more = frappe.ui.avatar({ size: "md", label: "" })[0];
			more.classList.add("kn-stack-av");
			more.querySelector(".es-avatar__fallback").textContent = `+${extra.length}`;
			more.title = extra.map((u) => frappe.user_info(u).fullname || u).join(", ");
			group.appendChild(more);
		}

		if (interactive) {
			const add = frappe.ui.avatar({ size: "md", label: "" })[0];
			add.querySelector(".es-avatar__fallback").innerHTML = frappe.utils.icon("plus", "sm");
			add.classList.add("kn-stack-av", "kn-assign-add", "cursor-pointer");
			add.title = users.length ? __("Add assignee") : __("Assign");
			add.addEventListener("click", (e) => {
				e.stopPropagation();
				this.open_assign(card);
			});
			group.appendChild(add);
		}

		return group;
	}

	/** Assignees on the card footer: stack + "+" add chip. */
	assign_button(card) {
		return this.assign_stack(card, { interactive: true });
	}

	/** Open Frappe's assign dialog for this card (add/remove multiple people). */
	open_assign(card) {
		this.bulk().assign([card.name], () => this.board.refresh());
	}

	/** Hovercard on an assignee avatar: photo · name · email · Unassign. */
	bind_assignee_hovercard(el, user, card) {
		const hovercard = new frappe.ui.HoverCard(el, {
			side: "bottom",
			align: "start",
			css_class: "kn-assignee-popover",
			// content is built fresh on each open, so `hovercard` is defined by then.
			content: () => this.assignee_hovercard(user, card, hovercard),
		});
	}

	assignee_hovercard(user, card, hovercard) {
		// Full name comes from frappe.user_info (populated from the server);
		// only show the email line when it differs from the name.
		const info = frappe.user_info(user);
		const fullname = info.fullname || user;
		const wrap = document.createElement("div");
		wrap.className = "kn-assignee-card";

		const head = document.createElement("div");
		head.className = "flex items-center gap-2";
		const email_line =
			fullname === user
				? ""
				: `<div class="text-xs text-ink-gray-5" style="word-break:break-all">${frappe.utils.escape_html(
						user
				  )}</div>`;
		head.innerHTML = `${frappe.ui.avatar.html({
			image: info.image || undefined,
			label: fullname,
			theme: this.hash_theme(user),
			size: "lg",
		})}
			<div class="min-w-0">
				<div class="text-sm-semibold text-ink-gray-8">${frappe.utils.escape_html(fullname)}</div>
				${email_line}
			</div>`;
		wrap.appendChild(head);

		const foot = document.createElement("div");
		foot.className = "kn-assignee-actions flex mt-2 pt-2 border-t";
		foot.innerHTML = frappe.ui.button.html({
			label: __("Unassign"),
			icon: "x",
			variant: "ghost",
			theme: "red",
			size: "xs",
		});
		foot.querySelector(".es-button").addEventListener("click", () =>
			this.unassign(card, user, hovercard)
		);
		wrap.appendChild(foot);

		return wrap;
	}

	/** Remove a single assignee (frappe.desk.form.assign_to.remove), with confirm. */
	unassign(card, user, hovercard) {
		hovercard && hovercard.close(); // don't leave the card floating over the dialog
		const label = frappe.user_info(user).fullname || user;
		frappe.confirm(__("Unassign {0} from {1}?", [label, card.name]), () => {
			frappe
				.xcall("frappe.desk.form.assign_to.remove", {
					doctype: this.doctype,
					name: card.name,
					assign_to: user,
				})
				.then(() => {
					frappe.ui.toast({
						message: __("Unassigned {0}", [label]),
						type: "success",
					});
					this.board.refresh();
				});
		});
	}

	parse_json_list(v) {
		if (!v) return [];
		try {
			const list = JSON.parse(v);
			return Array.isArray(list) ? list : [];
		} catch (e) {
			return [];
		}
	}
};

/**
 * Swimlane container: renders one collapsible horizontal band per group value,
 * each band a full (reused) Kanban board of that group's cards. Because the
 * bands are independent engines there is no cross-lane drag — grouping is
 * view-only; dragging within a lane still changes the card's column (status).
 *
 * Lane boards mount lazily (visible lanes first, max 2 concurrent) so a
 * high-cardinality group does not fan out N board loads on first paint.
 *
 * Exposes the small `destroy` / `refresh` / `engine` surface the page's toolbar,
 * selection bar and card menu already call, so those work unchanged.
 */
frappe.views.KanbanV2GroupedBoard = class KanbanV2GroupedBoard {
	constructor(page, field, lanes) {
		this.page = page;
		this.field = field;
		this.boards = [];
		this._active_sel_lane = null;
		this._mount_queue = [];
		this._mounting_count = 0;
		this._max_concurrent_mounts = 2;
		this._destroyed = false;
		this.$root = $('<div class="kn-swimlanes flex flex-col gap-2 py-2">').appendTo(
			page.$container
		);
		lanes.forEach((lane, index) => this.build_lane(lane, index));
		this.setup_lazy_mount();
	}

	build_lane(lane, index) {
		// Shell only — the Kanban engine mounts when the lane is visible or
		// expanded. Layout / text / colour use shared utilities; the count is
		// the badge component. Collapse positioning lives in kanban_v2.scss.
		const $lane = $(`
			<div class="kn-swimlane border-b pb-2">
				<div
					class="kn-swimlane-head relative flex items-center py-1 gap-2 cursor-pointer"
					role="button"
					tabindex="0"
					aria-expanded="true"
				>
					<span class="kn-swimlane-caret inline-flex items-center shrink-0 text-ink-gray-6">${frappe.utils.icon(
						"chevron-down",
						"sm"
					)}</span>
					<span class="kn-swimlane-label text-sm-semibold text-ink-gray-8 truncate"></span>
				</div>
				<div class="kn-swimlane-body">
					<div class="kn-swimlane-placeholder text-ink-gray-5 text-sm p-4">${__("Loading...")}</div>
				</div>
			</div>`).appendTo(this.$root);
		const $head = $lane.find(".kn-swimlane-head");
		$head.find(".kn-swimlane-label").text(this.page.lane_label(this.field, lane));
		frappe.ui.badge({ label: String(lane.count), size: "sm", theme: "gray" }).appendTo($head);
		const toggle = () => {
			$lane.toggleClass("kn-collapsed");
			const collapsed = $lane.hasClass("kn-collapsed");
			$head.attr("aria-expanded", collapsed ? "false" : "true");
			// Expanding a never-mounted lane must fetch its board immediately.
			if (!collapsed) this.ensure_lane_mounted(index);
		};
		$head.on("click", toggle);
		$head.on("keydown", (e) => {
			if (e.key === "Enter" || e.key === " ") {
				e.preventDefault();
				toggle();
			}
		});
		// Assignee lanes lead with the person's avatar, like Jira swimlanes.
		if (this.field === "_assign" && !lane.unset) {
			const info = frappe.user_info(lane.value);
			frappe.ui
				.avatar({
					image: info.image || undefined,
					label: info.fullname || lane.value,
					theme: this.page.hash_theme(lane.value),
					size: "sm",
				})
				.insertAfter($head.find(".kn-swimlane-caret"));
		}

		this.boards.push({ board: null, $lane, lane, index });
	}

	/**
	 * Mount lane boards as they enter the swimlane scrollport (and on expand).
	 * Caps concurrent mounts so the first paint stays responsive.
	 */
	setup_lazy_mount() {
		// First two lanes are almost always on screen; mount them now so the
		// grouped view isn't an empty shell while the observer catches up.
		this.boards.slice(0, 2).forEach((_, i) => this.ensure_lane_mounted(i));

		if (typeof IntersectionObserver === "undefined") {
			this.boards.forEach((_, i) => this.ensure_lane_mounted(i));
			return;
		}
		this._observer = new IntersectionObserver(
			(entries) => {
				if (this._destroyed) return;
				entries.forEach((entry) => {
					if (!entry.isIntersecting) return;
					const index = cint(entry.target.dataset.laneIndex);
					this.ensure_lane_mounted(index);
					this._observer.unobserve(entry.target);
				});
			},
			{ root: this.$root[0], rootMargin: "120px 0px", threshold: 0 }
		);
		this.boards.forEach((b) => {
			b.$lane[0].dataset.laneIndex = String(b.index);
			this._observer.observe(b.$lane[0]);
		});
	}

	/** Queue a lane for mounting if it has no board yet. */
	ensure_lane_mounted(index) {
		if (this._destroyed) return;
		const entry = this.boards[index];
		if (!entry || entry.board || entry._queued) return;
		entry._queued = true;
		this._mount_queue.push(index);
		this.drain_mount_queue();
	}

	/**
	 * Drain the mount queue up to `_max_concurrent_mounts` in flight.
	 * Each slot is held briefly after creating the engine so loadBoard
	 * requests stagger instead of all starting in one tick.
	 */
	drain_mount_queue() {
		if (this._destroyed) return;
		while (this._mounting_count < this._max_concurrent_mounts && this._mount_queue.length) {
			const index = this._mount_queue.shift();
			this._mounting_count++;
			this.mount_lane_board(index);
			// Hold the concurrency slot across a frame so N intersecting lanes
			// don't open N network loads in the same tick.
			requestAnimationFrame(() => {
				this._mounting_count--;
				this.drain_mount_queue();
			});
		}
	}

	/** Create the KanbanVanilla engine for one swimlane body. */
	mount_lane_board(index) {
		if (this._destroyed) return;
		const entry = this.boards[index];
		if (!entry || entry.board) return;
		const provider = this.page.make_provider(this.page.lane_filter(this.field, entry.lane));
		// replaceChildren inside KanbanCore.mount clears the Loading placeholder.
		entry.board = new frappe.kanban_v2.KanbanVanilla(
			entry.$lane.find(".kn-swimlane-body")[0],
			this.page.board_options(provider, {
				onSelectionChange: (ids) => this.on_lane_selection(index, ids),
			})
		);
	}

	/** Keep a single lane "active" for the bulk bar — selecting in one clears the rest. */
	on_lane_selection(index, ids) {
		if (ids.length) {
			this._active_sel_lane = index;
			this.page.update_selection_bar(ids);
			this.boards.forEach((b, j) => {
				if (j !== index && b.board && b.board.engine.state.selection.length)
					b.board.engine.select([]);
			});
		} else if (this._active_sel_lane === index) {
			this._active_sel_lane = null;
			this.page.update_selection_bar([]);
		}
	}

	refresh() {
		// Reload each mounted lane in place. Unmounted lanes load fresh on
		// next visibility / expand. Lane set itself only changes with filters
		// (page remount), so this stays light.
		this.boards.forEach((b) => {
			if (!b.board) return;
			try {
				b.board.refresh();
			} catch (e) {
				// ignore
			}
		});
	}

	destroy() {
		this._destroyed = true;
		this._mount_queue = [];
		if (this._observer) {
			this._observer.disconnect();
			this._observer = null;
		}
		this.boards.forEach((b) => {
			if (!b.board) return;
			try {
				b.board.destroy();
			} catch (e) {
				// ignore
			}
		});
		this.boards = [];
		this.$root && this.$root.remove();
		this.$root = null;
	}

	/** Facade so the page's selection bar and card "Move to" work across lanes. */
	get engine() {
		const boards = this.boards;
		return {
			select: (ids) =>
				boards.forEach((b) => {
					if (b.board) b.board.engine.select(ids);
				}),
			get state() {
				const hit = boards.find((b) => b.board);
				return (hit && hit.board.engine.state) || { columns: [], selection: [] };
			},
			applyMove: (cardId, from, to, index) => {
				const hit = boards.find((b) => b.board && b.board.engine.findCard(cardId));
				if (hit) hit.board.engine.applyMove(cardId, from, to, index);
			},
		};
	}
};

frappe.views.KanbanV2View = class KanbanV2View {
	static load_last_view() {
		return frappe.views.KanbanView.load_last_view();
	}

	constructor(opts) {
		this.doctype = opts.doctype;
		this.parent = opts.parent;
		this.page = this.parent.page;
		this._kanban = new frappe.views.KanbanV2Page(this.parent);
		this.show();
	}

	show() {
		return frappe.views.KanbanView.get_kanbans(this.doctype).then((kanbans) => {
			frappe.route_options = {};
			if (!kanbans.length) {
				return frappe.views.KanbanView.show_kanban_dialog(this.doctype, true);
			}
			if (frappe.get_route().length !== 4) {
				const last_board = frappe.get_user_settings(this.doctype)["Kanban"]
					?.last_kanban_board;
				const names = (kanbans || []).map((k) => k.name || k);
				if (last_board && names.includes(last_board)) {
					frappe.set_route("List", this.doctype, "Kanban", last_board);
					return;
				}
				const first = kanbans[0];
				frappe.set_route("List", this.doctype, "Kanban", first.name || first);
				return;
			}
			return this._kanban.load_from_route();
		});
	}
};
