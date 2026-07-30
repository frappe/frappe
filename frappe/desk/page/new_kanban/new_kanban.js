frappe.pages["new-kanban"].on_page_load = function (wrapper) {
	frappe.new_kanban_page = new frappe.views.NewKanbanPage(wrapper);
};

frappe.pages["new-kanban"].on_page_show = function () {
	frappe.new_kanban_page && frappe.new_kanban_page.load_from_route();
};

frappe.provide("frappe.views");

/**
 * How a Select value is drawn on a card: `theme` is a frappe.ui.badge theme and
 * `icon` a lucide icon placed before the label.
 *
 * Priority uses signal bars (low → medium → high → urgent). Status prefers the
 * circle family (dashed / empty / dot / check / x) so levels read without
 * colour alone; a few waiting/blocked states use a clearer metaphor
 * (hourglass, eye, ban, clock-alert).
 *
 * Keys are matched case-insensitively; missing values fall back to
 * frappe.utils.guess_colour() — the heuristic list views already use — so
 * app-specific values keep the colour users expect elsewhere.
 *
 * Extend or override per doctype with
 * `frappe.kanban_next.settings[doctype].select_styles`, where a plain string is
 * shorthand for `{ theme }`.
 */
const SELECT_STYLES = {
	// Priority — signal bars (Linear-style).
	low: { theme: "gray", icon: "signal-low" },
	medium: { theme: "amber", icon: "signal-medium" },
	high: { theme: "red", icon: "signal-high" },
	urgent: { theme: "red", icon: "signal" },

	// Submission / docstatus-ish.
	draft: { theme: "gray", icon: "circle-dashed" },
	submitted: { theme: "blue", icon: "send" },
	cancelled: { theme: "red", icon: "circle-x" },
	canceled: { theme: "red", icon: "circle-x" },

	// Not started / waiting to run.
	"not started": { theme: "gray", icon: "circle" },
	todo: { theme: "gray", icon: "circle" },
	open: { theme: "gray", icon: "circle" },
	queued: { theme: "gray", icon: "circle-dashed" },
	scheduled: { theme: "gray", icon: "circle-dashed" },
	backlog: { theme: "gray", icon: "circle-dashed" },

	// Running.
	"in progress": { theme: "blue", icon: "circle-dot" },
	working: { theme: "blue", icon: "circle-dot" },
	running: { theme: "blue", icon: "circle-dot" },
	started: { theme: "blue", icon: "circle-dot" },
	processing: { theme: "blue", icon: "circle-dot" },

	// Blocked or waiting on a person.
	"on hold": { theme: "amber", icon: "circle-pause" },
	paused: { theme: "amber", icon: "circle-pause" },
	pending: { theme: "amber", icon: "hourglass" },
	"pending review": { theme: "amber", icon: "eye" },
	"under review": { theme: "amber", icon: "eye" },
	"awaiting approval": { theme: "amber", icon: "user-check" },
	"pending approval": { theme: "amber", icon: "user-check" },
	blocked: { theme: "red", icon: "ban" },
	retrying: { theme: "amber", icon: "loader" },

	// Finished well.
	done: { theme: "green", icon: "circle-check" },
	success: { theme: "green", icon: "circle-check" },
	completed: { theme: "green", icon: "circle-check" },
	closed: { theme: "green", icon: "circle-check" },
	approved: { theme: "green", icon: "circle-check" },
	resolved: { theme: "green", icon: "circle-check" },
	verified: { theme: "green", icon: "circle-check" },

	// Finished, but not cleanly. Listed explicitly because the fallback would
	// read "Partially Failed" as a plain failure.
	"partial success": { theme: "amber", icon: "circle-ellipsis" },
	"partially failed": { theme: "amber", icon: "circle-alert" },
	"partially completed": { theme: "amber", icon: "circle-ellipsis" },
	"timed out": { theme: "amber", icon: "clock-alert" },
	timeout: { theme: "amber", icon: "clock-alert" },

	// Finished badly.
	failed: { theme: "red", icon: "circle-x" },
	error: { theme: "red", icon: "circle-x" },
	rejected: { theme: "red", icon: "circle-x" },
	expired: { theme: "red", icon: "clock-alert" },
	overdue: { theme: "red", icon: "timer" },

	// On/off states.
	active: { theme: "green", icon: "circle-check" },
	enabled: { theme: "green", icon: "circle-check" },
	inactive: { theme: "gray", icon: "circle" },
	disabled: { theme: "gray", icon: "circle-off" },
	archived: { theme: "gray", icon: "archive" },
};

/**
 * Next-generation Kanban board page. Loads the framework-agnostic engine
 * (kanban_next.bundle.js) and mounts it against an existing Kanban Board via
 * FrappeDataProvider. Route: #new-kanban/<board_name>
 */
frappe.views.NewKanbanPage = class NewKanbanPage {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("New Kanban"),
			single_column: true,
		});
		// flex column so an optional filter bar + the board share the height.
		// Height = viewport − sticky page-head − bottom margin (same tokens as
		// classic kanban). No magic px — works across screen sizes.
		this.page.main.css({
			padding: "0",
			display: "flex",
			"flex-direction": "column",
			overflow: "hidden",
		});
		this.$container = $('<div class="new-kanban-container px-4">')
			.css({
				flex: "1 1 auto",
				"min-height": "0",
				height: "calc(100vh - var(--page-head-height) - var(--margin-md))",
			})
			.appendTo(this.page.main);

		this.make_selection_bar();
		this.inject_view_styles();
	}

	/**
	 * Inject tiny behavior-only CSS for states utilities cannot express cleanly
	 * (liked heart fill, icon scaling, and nested hover targets).
	 */
	inject_view_styles() {
		if (document.getElementById("kn-view-styles")) return;
		const style = document.createElement("style");
		style.id = "kn-view-styles";
		style.textContent = `
			/* Card rows sit on a quiet rhythm — short enough that a stack of
			   fields doesn't look like a form, tall enough that icons and
			   values stay aligned. Spacing/colour otherwise come from utilities. */
			.kn-frow { min-height: 24px; }
			.kn-frow.kn-title-row { min-height: 0; margin-bottom: 2px; }
			.kn-fempty { font-style: italic; }
			/* Link formatters emit <a> with desk $text-color (ink-gray-8). Match
			   the muted ink-gray-6 used for Data / plain Select values. */
			.kn-frow a,
			.kn-mi-props a { color: inherit; text-decoration: none; }
			.kn-frow a:hover,
			.kn-mi-props a:hover { text-decoration: underline; }
			/* Two-line clamp and the link underline — no utilities for either.
			   The underline only appears on hover, so a board of cards reads as
			   plain text until you point at a title. */
			.kn-card-title { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.35; }
			.kn-card-title.cursor-pointer:hover { text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 2px; text-decoration-color: currentColor; }
			/* Selection highlight — Frappe-native (blue ring + subtle blue fill),
			   overriding the engine's harder 2px outline. The colour needs
			   !important to beat the card's .border utility. */
			.new-kanban-container .kn-card.kn-selected {
				outline: none;
				border-color: var(--blue-500, #2490ef) !important;
				box-shadow: 0 0 0 1px var(--blue-500, #2490ef);
				background: var(--bg-blue, #eaf2ff);
			}
			/* "+" add chip at the end of the avatar stack — neutral, standard hover. */
			.kn-assign-add { cursor: pointer; }
			.kn-assign-add .avatar-frame { transition: background .14s; }
			.kn-assign-add:hover .avatar-frame { background: var(--fg-hover-color); }
			/* Assignee hovercard: tighten the default popover shell (256px / 16px). */
			.es-hover-card.kn-assignee-popover { width: auto; padding: 12px; }
			.kn-assignee-card { min-width: 180px; max-width: 240px; }
			.kn-assignee-actions { border-top: 1px solid var(--border-color); }
			/* pull the ghost button flush with the card's left edge */
			.kn-assignee-actions .es-button { margin-left: -8px; }
			/* Selection bar — neutral surface, but clearly lifted off the board
			   with a strong shadow, a defined border and a slide-up entrance so
			   it's easy to notice (no colour, no black). */
			.kn-selection-bar {
				border-color: var(--gray-300, #d1d8dd) !important;
				box-shadow: 0 12px 32px rgba(0,0,0,.20), 0 3px 10px rgba(0,0,0,.12) !important;
				padding: 10px 10px 10px 18px !important;
				animation: kn-sel-in .22s cubic-bezier(.2,.8,.3,1);
			}
			@keyframes kn-sel-in {
				from { opacity: 0; transform: translateX(-50%) translateY(14px); }
				to   { opacity: 1; transform: translateX(-50%) translateY(0); }
			}
			.kn-selection-bar .kn-sel-count { color: var(--ink-gray-8); }
			.kn-selection-bar .es-button { margin: 0; }
			/* Preview hovercard — width follows the field grid (not the long
			   title), so left/right padding stays equal (same px-4 both sides). */
			.es-hover-card.kn-mi-hc { width: fit-content; max-width: min(400px, calc(100vw - 32px)); padding: 0; overflow: hidden; }
			.kn-mi { display: flex; flex-direction: column; width: fit-content; max-width: 100%; }
			/* Title / desc / footer fill the props-driven width instead of expanding it. */
			.kn-mi-banner,
			.kn-mi-header,
			.kn-mi-desc,
			.kn-mi-foot { width: 0; min-width: 100%; box-sizing: border-box; }
			.kn-mi-banner { height: 116px; background-size: cover; background-position: center; background-color: var(--bg-light-gray); }
			.kn-mi-title, .kn-mi-desc { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
			.kn-mi-title:hover { text-decoration: underline; text-underline-offset: 2px; }
			/* flatten rendered editor markup into one snippet line */
			.kn-mi-desc :where(h1,h2,h3,h4,h5,h6,p,ul,ol,li,blockquote,pre) { display: inline; margin: 0; padding: 0; font: inherit; list-style: none; }
			.kn-mi-desc :where(p,li,br)::after { content: " "; }
			.kn-mi-desc :where(img,table,hr) { display: none; }
			.kn-mi-props { display: grid; grid-template-columns: auto auto; column-gap: 1.5rem; row-gap: 0.75rem; width: max-content; max-width: 100%; box-sizing: border-box; }
			/* Avatar stack is taller than badges — keep the band from collapsing. */
			.kn-mi-foot { min-height: 28px; }
		`;
		document.head.appendChild(style);
	}

	make_selection_bar() {
		this.selected_ids = [];
		this.$selection_bar = $(`
			<div class="kn-selection-bar position-fixed flex items-center gap-2 rounded-md border bg-surface-base shadow-lg px-3 py-2" style="bottom:24px;left:50%;transform:translateX(-50%);display:none;z-index:1000;">
				<span class="kn-sel-count text-sm-semibold whitespace-nowrap pe-1"></span>
				${frappe.ui.button.html({ label: __("Edit"), css_class: "kn-sel-edit" })}
				${frappe.ui.button.html({ label: __("Assign"), css_class: "kn-sel-assign" })}
				${frappe.ui.button.html({ label: __("Tags"), css_class: "kn-sel-tags" })}
				${frappe.ui.button.html({ label: __("Delete"), theme: "red", css_class: "kn-sel-delete" })}
				${frappe.ui.button.html({ label: __("Clear"), variant: "ghost", css_class: "kn-sel-clear" })}
			</div>`).appendTo(document.body);

		const done = () => {
			if (this.board) {
				this.board.engine.select([]);
				this.board.refresh();
			}
		};
		this.$selection_bar.find(".kn-sel-clear").on("click", () => done());
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
		// The bar lives on <body>, so hide it when navigating away from the
		// board — otherwise it lingers over the next page (e.g. the form).
		frappe.router.on("change", () => {
			if (frappe.get_route()[0] !== "new-kanban") this.update_selection_bar([]);
		});
	}

	/** Deselect all cards and hide the selection bar. */
	clear_selection() {
		if (this.board) this.board.engine.select([]);
		this.update_selection_bar([]);
	}

	/** Lazily create a BulkOperations helper for the current doctype. */
	bulk() {
		if (!this._bulk || this._bulk.doctype !== this.doctype) {
			this._bulk = new frappe.kanban_next.BulkOperations({ doctype: this.doctype });
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
			this.$selection_bar.css("display", "flex");
		} else {
			this.$selection_bar.hide();
		}
	}

	async load_from_route() {
		const route = frappe.get_route(); // ["new-kanban", board_name]
		const board_name = route[1];
		if (!board_name) {
			this.$container.html(
				`<div class="text-muted p-4">${__("No Kanban Board specified.")}</div>`
			);
			return;
		}
		if (this.current_board === board_name && this.board) {
			// Already mounted — only rebuild if the board's config changed
			// (e.g. Card Fields / Preview Fields edited on the form meanwhile).
			this.remount_if_board_changed(board_name);
			return;
		}
		this.current_board = board_name;

		this.page.set_title(__(board_name));
		await new Promise((resolve) => frappe.require("kanban_next.bundle.js", resolve));

		let board;
		try {
			board = await frappe.db.get_doc("Kanban Board", board_name);
		} catch (e) {
			this.$container.html(
				`<div class="text-muted p-4">${__("Kanban Board {0} not found.", [
					board_name,
				])}</div>`
			);
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
		this.page.set_title(__(board.kanban_board_name || board_name));

		frappe.model.with_doctype(this.doctype, () => {
			this.setup_meta();
			this.setup_toolbar();
			this.mount_board();
		});
	}

	/**
	 * Rebuild the mounted board when its card config changed since we loaded
	 * it, so edits on the Kanban Board form (Card Fields, Preview Fields, …)
	 * show up on the next visit without a full page reload. Only the rendering
	 * config is compared — dragging a card also saves the board, and that must
	 * not cost a remount.
	 */
	async remount_if_board_changed(board_name) {
		const config = await frappe.xcall(
			"frappe.desk.doctype.kanban_board.kanban_board.get_card_config",
			{ board_name }
		);
		if (!config || this.card_config_signature(config) === this.card_config_sig) return;

		this.current_board = null;
		this.load_from_route();
	}

	/** Comparable form of the config that decides how a card / hover peek is rendered. */
	card_config_signature(doc) {
		const field_sig = (rows) =>
			(rows || []).map((f) => [f.fieldname, f.label || "", f.icon || ""]);
		return JSON.stringify([
			doc.title_field || "",
			doc.image_field || "",
			cint(doc.show_assigned_to, 1),
			doc.footer_date_field || "Modified",
			field_sig(doc.card_fields),
			field_sig(doc.preview_fields),
		]);
	}

	setup_meta() {
		const meta = frappe.get_meta(this.doctype);
		this.meta = meta;

		// Developer customization from <doctype>_kanban.js (loaded via the meta
		// bundle before this runs). Doctype-level config applies to every board;
		// `boards[<board name>]` overrides it for one board.
		const reg = (frappe.kanban_next.settings || {})[this.doctype] || {};
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
		// Card-footer age badge: Modified (default) or Creation.
		this.footer_date_field =
			String(this.board_doc.footer_date_field || "Modified").toLowerCase() === "creation"
				? "creation"
				: "modified";

		// Quick entry: does this doctype need more than a title to be created?
		// (matches the old kanban's get_card_meta logic)
		const route_options = { ...frappe.route_options };
		const new_doc = frappe.model.get_new_doc(this.doctype);
		frappe.route_options = route_options;
		const mandatory = meta.fields.filter((df) => df.reqd && !new_doc[df.fieldname]);
		this.quick_entry =
			mandatory.some((df) => frappe.model.table_fields.includes(df.fieldtype)) ||
			mandatory.length > 1;

		const base = [
			"name",
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

		// --- card display config (overridable via frappe.kanban_next.settings) ---
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
		const is_image = (fn) => {
			if (!fn) return false;
			const df = frappe.meta.get_docfield(this.doctype, fn);
			return df && df.fieldtype === "Attach Image" && !df.hidden;
		};
		if (is_image(this.board_doc.image_field)) return this.board_doc.image_field;
		if (is_image(meta.image_field)) return meta.image_field;
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

	// --- toolbar (mirrors the normal Kanban navbar) ----------------------

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

		// Layout mirrors the classic Kanban navbar:
		// [Filter ×] [Select Kanban ▾] [⊞ Kanban View ▾]  [⟳]  [⋯]  [+ Add Doctype]

		// Filter (funnel button + clear ×)
		this.setup_filter();

		// Select Kanban + Kanban View — Select Kanban loads async, so add the view
		// switcher inside the same callback to preserve the classic order.
		frappe.views.KanbanView.get_kanbans(this.doctype).then((kanbans) => {
			const kgroup = page.add_custom_button_group(__("Select Kanban"));
			(kanbans || []).forEach((k) =>
				page.add_custom_menu_item(
					kgroup,
					k.name,
					() => frappe.set_route("new-kanban", k.name),
					false
				)
			);

			const vgroup = page.add_custom_button_group(__("Kanban View"), "square-kanban");
			page.add_custom_menu_item(
				vgroup,
				__("List"),
				() => frappe.set_route("List", this.doctype, "List"),
				false,
				null,
				"list"
			);
			page.add_custom_menu_item(
				vgroup,
				__("Report"),
				() => frappe.set_route("List", this.doctype, "Report"),
				false,
				null,
				"sheet"
			);
			page.add_custom_menu_item(
				vgroup,
				__("Classic Kanban"),
				() => frappe.set_route("List", this.doctype, "Kanban", this.current_board),
				false,
				null,
				"square-kanban"
			);
		});

		// Refresh (visible icon, like the classic navbar)
		page.add_action_icon(
			"refresh-cw",
			() => this.board && this.board.refresh(),
			"",
			__("Reload")
		);

		// Save Filters (in the ... menu, like the classic kanban)
		page.add_menu_item(__("Save Filters"), () => this.save_filters());
	}

	setup_filter() {
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
			this.$filter_section = $('<div class="filter-section flex">')
				.append($selector)
				.appendTo(this.page.custom_actions);

			this.filter_group = new frappe.ui.FilterGroup({
				parent: this.$filter_section,
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
			console.warn("[new-kanban] filter setup skipped", e);
		}
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

	apply_filters() {
		if (!this.filter_group || !this.provider) return;
		this.filters = this.filter_group.get_filters();
		this.sync_filter_ui(); // always keep the button/indicator in sync (no reload)
		// Only reload data when the filter set actually changed (kills the blink on
		// popover open/close, which fires on_change without changing filters).
		const key = JSON.stringify(this.filters || []);
		if (key === this._loaded_key) return;
		this._loaded_key = key;
		this.provider.setFilters(this.filters);
		this.board.refresh();
	}

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
				frappe.show_alert({ message: __("Filters saved"), indicator: "green" });
			});
	}

	// --- board -----------------------------------------------------------

	mount_board() {
		if (this.board) {
			try {
				this.board.destroy();
			} catch (e) {
				// ignore
			}
		}
		this.$container.empty();

		const provider = new frappe.kanban_next.FrappeDataProvider({
			doctype: this.doctype,
			board_name: this.current_board,
			reportview_args: {
				doctype: this.doctype,
				fields: JSON.stringify(this.fields),
				order_by: "modified desc",
				filters: JSON.stringify(this.filters || []),
			},
		});
		this.provider = provider; // kept so filter changes reload in place
		this._loaded_key = JSON.stringify(this.filters || []); // filters the board reflects

		const s = this.settings || {};

		// The page's own (internal) callbacks. Developer callbacks from settings are
		// merged on top: onSelectionChange runs BOTH (so the selection bar keeps
		// working); everything else the developer supplies overrides the default.
		const base_callbacks = {
			onCardOpen: (card) => frappe.set_route("Form", this.doctype, card.name),
			onSelectionChange: (ids) => this.update_selection_bar(ids),
			onMoveError: (mv, err) => {
				frappe.show_alert({
					message: __("Could not move {0}", [mv.cardId]),
					indicator: "red",
				});
				console.error("[new-kanban] move failed", err);
			},
			// "+ Add {Doctype}" opens the new-document form, pre-filled with the
			// column's group-by value + active "=" filters.
			onAddCard: (columnId) => this.add_document(columnId),
		};

		this.board = new frappe.kanban_next.KanbanVanilla(this.$container[0], {
			provider,
			groupBy: this.field_name,
			pageLength: 20,
			selection: "multi",
			addCardLabel: __("Add {0}", [__(this.doctype)]),
			renderCard: s.renderCard
				? (card, el, ctx) => s.renderCard(card, el, ctx, this)
				: (card, el) => this.render_card(card, el),
			renderColumnHeader: s.renderColumnHeader,
			renderEmptyState: s.renderEmptyState,
			callbacks: this.merge_callbacks(base_callbacks, s.callbacks || {}),
			// Any extra engine options (e.g. addColumn, pageLength overrides).
			...(s.options || {}),
		});
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

		// Right-click context menu — default items + <doctype>_kanban.js additions.
		this.bind_context_menu(el, card);
	}

	// --- footer ----------------------------------------------------------

	/** The card's last row: assignees on the left, last activity on the right. */
	card_footer(card) {
		const foot = document.createElement("div");
		// No divider: the extra top margin alone sets the footer apart, so the
		// card stays one quiet block instead of two boxed halves.
		foot.className = "flex items-center justify-between gap-2 mt-3";
		if (this.show_assigned_to) {
			foot.appendChild(this.assign_button(card));
		}
		const age = this.age_badge(card);
		if (age) {
			// Keep the date on the right when assignees are hidden.
			if (!this.show_assigned_to) age.classList.add("ms-auto");
			foot.appendChild(age);
		}
		// No assignees and no date → omit an empty strip under the fields.
		if (!foot.childNodes.length) return document.createDocumentFragment();
		return foot;
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
		row.className = "kn-frow kn-title-row flex items-center gap-2";

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
			title.addEventListener("click", (e) => {
				e.stopPropagation();
				frappe.set_route("Form", this.doctype, card.name);
			});
		}
		row.appendChild(title);
		// Hovering the title reveals the document preview (frappe.ui.HoverCard).
		this.bind_more_info_hovercard(title, card);
		return row;
	}

	/**
	 * One field row. When the child row has an Icon, show that icon (label on
	 * hover) beside the value; otherwise show the label text directly. Empty
	 * fields with an icon invite a value via "Set {label}…"; with a text label
	 * they show a dash (the label is already spelled out).
	 */
	field_row(card, df) {
		const label = this.field_label(df);
		const icon = (this.card_field_icons || {})[df.fieldname];
		const row = document.createElement("div");
		row.className = `kn-frow flex items-center ${icon ? "gap-2" : "gap-1"}`;

		if (icon) {
			row.appendChild(this.row_icon(icon, label));
		} else {
			const text = document.createElement("span");
			text.className = "text-sm text-ink-gray-5 shrink-0 whitespace-nowrap";
			text.textContent = `${label}:`;
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
		span.innerHTML = frappe.utils.icon(icon, "sm");
		frappe.ui.tooltip(span, { text: label, side: "top", delay: 200 });
		return span;
	}

	/** Fieldtypes whose stored value is markup or markdown, not display text. */
	is_rich_text(fieldtype) {
		return ["Text Editor", "Markdown Editor", "HTML", "HTML Editor", "Comment"].includes(
			fieldtype
		);
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
		// on a card — render it, then strip it like any other HTML.
		if (fieldtype === "Markdown Editor") text = frappe.markdown(text);
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
			el.className = "inline-flex items-center gap-1.5 text-sm text-ink-gray-6 min-w-0";
			el.innerHTML = `${frappe.avatar(
				val,
				"avatar-xs shrink-0"
			)}<span class="truncate">${frappe.utils.escape_html(
				frappe.user_info(val).fullname || val
			)}</span>`;
			return el;
		}

		if (df.fieldtype === "Select") {
			// Card: badge only when we have a known icon (priority/status). Other
			// Select values stay plain muted text so they match Link/Data rows.
			// Hover preview: always plain text — more room, less noise.
			if (opts.plain_select) {
				el.textContent = __(val);
				return el;
			}
			const style = this.select_style(val);
			if (style.icon) {
				el.className = "min-w-0";
				el.innerHTML = frappe.ui.badge.html({
					label: __(val),
					size: "sm",
					theme: style.theme,
					icon: style.icon,
				});
			} else {
				el.textContent = __(val);
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
			if (text.length > 40) {
				frappe.ui.tooltip(el, {
					text: frappe.ellipsis(text, 280),
					side: "top",
					delay: 200,
				});
			}
			return el;
		}

		el.innerHTML = frappe.format(val, df, { inline: true }, card);
		return el;
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

	/** Default card menu items, plus whatever <doctype>_kanban.js adds. */
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

		// Developer-added items from <doctype>_kanban.js.
		const s = this.settings || {};
		if (typeof s.card_context_menu === "function") {
			const extra = s.card_context_menu(card, this) || [];
			if (Array.isArray(extra)) items.push(...extra);
		}
		return items;
	}

	// --- document preview (hovercard on the card title) ------------------

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
		wrap.className = "kn-mi";

		// Cover image (board image field), when present.
		const image = this.image_field && card[this.image_field];
		if (image) {
			const banner = document.createElement("div");
			banner.className = "kn-mi-banner";
			// JSON.stringify quotes/escapes so ', (, ) in the URL can't break url(...).
			banner.style.backgroundImage = `url(${JSON.stringify(String(image))})`;
			wrap.appendChild(banner);
		}

		// Header: icon · title (link) · id.
		const header = document.createElement("div");
		header.className = "kn-mi-header flex items-start gap-2 px-4 pt-3";
		// Only show an icon when the doctype actually has a usable one — a blank
		// square says nothing.
		const icon_html = this.doctype_icon_html();
		if (icon_html) {
			const icon = document.createElement("span");
			icon.className = "inline-flex items-center shrink-0 mt-1 text-ink-gray-6";
			icon.innerHTML = icon_html;
			header.appendChild(icon);
		}

		const htext = document.createElement("div");
		htext.className = "min-w-0 flex-1";
		const title = document.createElement("div");
		title.className = "kn-mi-title text-base-semibold text-ink-gray-9 cursor-pointer";
		const title_df = frappe.meta.get_docfield(this.doctype, this.title_field);
		title.textContent =
			this.plain_text(card[this.title_field], title_df && title_df.fieldtype) || card.name;
		title.addEventListener("click", () => {
			close && close();
			frappe.set_route("Form", this.doctype, card.name);
		});
		htext.appendChild(title);
		const id = document.createElement("div");
		id.className = "text-xs text-ink-gray-5 mt-1";
		id.textContent = card.name;
		htext.appendChild(id);
		header.appendChild(htext);
		wrap.appendChild(header);

		// Description snippet.
		if (this.desc_field) {
			const d = this.description_el(card);
			if (d) wrap.appendChild(d);
		}

		// Two-column property grid — only fields that actually have a value.
		// Preview has room: icon (if set) + label text side by side.
		const props = document.createElement("div");
		props.className = "kn-mi-props px-4 pt-3";
		for (const fn of this.preview_field_list) {
			const df = frappe.meta.get_docfield(this.doctype, fn);
			if (!df) continue;
			const value = this.field_value(card, df, { plain_select: true });
			if (!value) continue;
			const cell = document.createElement("div");
			cell.className = "min-w-0";
			const label = this.preview_field_labels[fn] || __(df.label || df.fieldname);
			const icon = (this.preview_field_icons || {})[fn];
			const k = document.createElement("div");
			// Don't truncate labels here — the hovercard grows with content.
			k.className = "text-sm text-ink-gray-5 flex items-center gap-1";
			if (icon) {
				// No tooltip — the label sits next to the icon in the preview.
				const span = document.createElement("span");
				span.className =
					"kn-ficon inline-flex items-center justify-center shrink-0 size-4 text-ink-gray-4";
				span.innerHTML = frappe.utils.icon(icon, "sm");
				k.appendChild(span);
			}
			const text = document.createElement("span");
			text.textContent = label;
			k.appendChild(text);
			cell.appendChild(k);
			value.classList.add("mt-1");
			value.classList.remove("truncate");
			cell.appendChild(value);
			props.appendChild(cell);
		}
		if (props.childNodes.length) wrap.appendChild(props);

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
		d.className = "kn-mi-desc text-sm text-ink-gray-6 px-4 pt-2";
		if (ft === "Markdown Editor" || this.is_rich_text(ft)) {
			let raw = String(val);
			// Some data stores literal escapes (\n, \t) — decode so it isn't one blob.
			if (raw.includes("\\n")) {
				raw = raw
					.replace(/\\n/g, "\n")
					.replace(/\\t/g, "\t")
					.replace(/\\([*_`])/g, "$1");
			}
			let html;
			if (/<[a-z!/][^>]*>/i.test(raw)) {
				// Real HTML (a normal Text Editor value) — sanitize, then render.
				html = raw;
			} else {
				// Non-HTML content in a rich-text field: render as markdown so
				// headings/lists/emphasis format instead of showing their symbols.
				// Also convert legacy textile headings ("h4. …") to markdown ones.
				raw = raw.replace(/^\s*h([1-6])\.\s+/gm, (_m, n) => "#".repeat(+n) + " ");
				html = frappe.markdown(raw);
			}
			d.innerHTML = this.safe_html(html);
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
			.filter(Boolean)
			.slice(0, 3);
		const comments = this.parse_json_list(card._comments).length;
		const likes = this.parse_json_list(card._liked_by).length;
		// Nothing on either side → skip the footer so the card ends on content.
		if (!assignees && !tags.length && !comments && !likes) return null;

		const foot = document.createElement("div");
		// Spacing (not a border) separates body from footer when the band is present.
		foot.className = "kn-mi-foot flex items-center justify-between gap-3 px-4 pb-2 mt-3";
		if (assignees) foot.appendChild(assignees);

		const right = document.createElement("div");
		// Tags / comments / likes stay on the right even when assignees are off.
		right.className = `flex items-center gap-2 text-ink-gray-5 min-w-0${
			assignees ? "" : " ms-auto"
		}`;
		if (tags.length) {
			// A tag icon, then the tags: [🏷] tag1 tag2 tag3
			const group = document.createElement("span");
			group.className = "inline-flex items-center gap-1 min-w-0";
			group.innerHTML =
				frappe.utils.icon("tag", "sm") +
				tags
					.map((t) => frappe.ui.badge.html({ label: t, size: "sm", theme: "gray" }))
					.join("");
			right.appendChild(group);
		}
		if (comments) right.appendChild(this.preview_stat("message-square", comments));
		if (likes) right.appendChild(this.preview_stat("heart", likes));
		if (right.childNodes.length) foot.appendChild(right);
		return foot;
	}

	/** Read-only assignee stack for the preview footer; null when unassigned. */
	preview_assignees(card) {
		if (!this.show_assigned_to) return null;
		const users = this.parse_json_list(card._assign);
		if (!users.length) return null;
		return frappe.avatar_group(users, 3, { align: "left", overlap: true })[0];
	}

	preview_stat(icon, n) {
		const span = document.createElement("span");
		span.className = "inline-flex items-center gap-1 text-xs";
		span.innerHTML = `${frappe.utils.icon(icon, "sm")}${n}`;
		return span;
	}

	/**
	 * Assignees on the card's bottom-right: an overlapping avatar stack with a
	 * native "+N" overflow, always ending in the same "+" add chip — so the add
	 * affordance looks identical whether or not the card has assignees. Each
	 * avatar reveals a hovercard (photo · name · email · Unassign) on hover.
	 */
	assign_button(card) {
		const users = this.parse_json_list(card._assign);

		const group = document.createElement("div");
		group.className = "avatar-group overlap kn-assign-group inline-flex items-center";
		group.addEventListener("click", (e) => e.stopPropagation());

		const shown = users.slice(0, 3);
		const extra = users.slice(3);
		shown.forEach((user) => {
			const holder = document.createElement("div");
			holder.innerHTML = frappe.avatar(user, "avatar-small");
			const av = holder.firstElementChild;
			group.appendChild(av);
			this.bind_assignee_hovercard(av, user, card);
		});

		if (extra.length) {
			const more = document.createElement("span");
			more.className = "avatar avatar-small";
			more.innerHTML = `<div class="avatar-frame standard-image avatar-extra-count" title="${extra
				.map((u) => frappe.utils.escape_html(frappe.user_info(u).fullname || u))
				.join(", ")}">+${extra.length}</div>`;
			group.appendChild(more);
		}

		// "+" add chip — same element whether the card is unassigned or assigned.
		const add = document.createElement("span");
		add.className = "avatar avatar-small kn-assign-add";
		add.title = users.length ? __("Add assignee") : __("Assign");
		add.innerHTML = `<div class="avatar-frame avatar-action">${frappe.utils.icon(
			"plus",
			"sm"
		)}</div>`;
		add.addEventListener("click", (e) => {
			e.stopPropagation();
			this.open_assign(card);
		});
		group.appendChild(add);

		return group;
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
		const fullname = frappe.user_info(user).fullname || user;
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
		head.innerHTML = `${frappe.avatar(user, "avatar-medium-2")}
			<div class="min-w-0">
				<div class="text-sm-semibold text-ink-gray-8">${frappe.utils.escape_html(fullname)}</div>
				${email_line}
			</div>`;
		wrap.appendChild(head);

		const foot = document.createElement("div");
		foot.className = "kn-assignee-actions flex mt-2 pt-2";
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
					frappe.show_alert({
						message: __("Unassigned {0}", [label]),
						indicator: "green",
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
