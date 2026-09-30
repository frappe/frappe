import { safe_href } from "../../ui/components/utils.js";

frappe.provide("frappe.views");

// badge style per Select value (lowercase keys); unknown values get a guessed color
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
		this.wrapper = wrapper;
		this.page = wrapper.page;

		this.page.page_form.removeClass("hide row").addClass("flex").show();
		this.page.page_form.addClass("list-page-form");
		this.$filter_section = $(
			'<div class="filter-section flex ms-auto kanban-v2-filter-section"></div>'
		).appendTo(this.page.page_form);

		this.$container = $('<div class="kanban-v2-container px-4 pb-2">').appendTo(
			this.page.main
		);

		this.setup_board_height_sync();
		this.apply_page_shell();

		this.make_selection_bar();
	}

	show_empty(opts) {
		this.$container.empty().append(
			frappe.ui.empty_state({
				...opts,
				css_class: ["min-h-64", opts.css_class].filter(Boolean).join(" "),
			})
		);
	}

	apply_page_shell() {
		this.setup_board_height_sync();
		this.page.main.addClass("flex flex-col overflow-hidden p-0");
		if (this.$filter_section) this.$filter_section.show();
		if (this.$container) this.$container.show();
		$(document.body).addClass("no-list-sidebar");
		this.page.container.addClass("kanban-v2-full-width");
		this.sync_board_height();
	}

	/** Undo apply_page_shell() when leaving the board. */
	restore_page_shell() {
		this.page.main.removeClass("flex flex-col overflow-hidden p-0");
		if (this.$filter_section) this.$filter_section.hide();
		if (this.$container) this.$container.hide();
		// no-list-sidebar stays, as every list view leaves it on too
		this.page.container.removeClass("kanban-v2-full-width");
	}

	get_board_name_from_route() {
		const route = frappe.get_route();
		if (route[0] === "List" && frappe.utils.to_title_case(route[2] || "") === "Kanban") {
			return route[3] || null;
		}
		return null;
	}

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
			</div>`).appendTo(this.wrapper);

		const done = () => {
			if (this.board) {
				this.board.engine.select([]);
				this.board.refresh();
			}
		};
		this._selection_done = done;
		// Clear only deselects, so unlike the other actions it skips the refresh
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

		frappe.ui.keys.add_shortcut({
			shortcut: "escape",
			action: () => this.clear_selection(),
			condition: () => this.selected_ids.length > 0,
			description: __("Clear selection"),
			page: this.page,
		});
		// each board route has its own page, so leaving it means leaving the board
		$(this.wrapper).on("hide", () => {
			this.update_selection_bar([]);
			this.teardown_board(true);
		});
	}

	/** `clear_route` also forgets the board and undoes the page layout, for leaving the page. */
	teardown_board(clear_route = false) {
		if (this.board) {
			this.board.destroy();
			this.board = null;
		}
		if (clear_route) this.current_board = null;
		if (clear_route) {
			this.cleanup_board_height_sync();
			this.restore_page_shell();
		}
	}

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
		if (!this._bulk) {
			this._bulk = new frappe.kanban_v2.BulkOperations({ doctype: this.doctype });
		}
		return this._bulk;
	}

	/** Same wording as the list view's delete confirmation. */
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
				field_mappings[`${df.label} (${this.doctype})`] = Object.assign({}, df, {
					is_child_field: false,
					translated_label: `${__(df.label, null, this.doctype)} (${__(this.doctype)})`,
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
			this.$selection_bar.find(".kn-sel-assign").toggle(this.show_assigned_to !== false);
			this.refresh_bulk_actions();
			this.$selection_bar.css("display", "flex");
		} else {
			this.$selection_bar.hide();
		}
	}

	/** settings.bulk_actions(ids, page) returns extra buttons, shown before Delete. */
	refresh_bulk_actions() {
		const $slot = this.$selection_bar.find(".kn-sel-custom");
		$slot.empty();

		const settings = this.settings || {};
		if (typeof settings.bulk_actions !== "function") return;

		const done = this._selection_done || (() => {});
		const actions = settings.bulk_actions(this.selected_ids, this) || [];
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

	async load_from_route() {
		// the hide handler undoes the layout, so re-apply it each time the page shows
		this.apply_page_shell();

		const board_name = this.get_board_name_from_route();
		if (!board_name) {
			this.show_empty({
				icon: "columns-3",
				title: __("No Kanban Board specified."),
			});
			return;
		}
		if (this.current_board === board_name && this.board) return;
		this.current_board = board_name;

		this.page.set_title(board_name, null, true);

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
		// a standard board ships with an app, so its setup changes only in developer mode
		this.board_locked = board.is_standard === "Yes" && !frappe.boot.developer_mode;
		this.doctype = board.reference_doctype;
		this.field_name = board.field_name;
		this.filters = JSON.parse(board.filters || "[]");
		// for the "Not Saved" indicator
		this.saved_filters = JSON.parse(JSON.stringify(this.filters));
		// only boards shipped by an app have translations
		const title =
			board.is_standard === "Yes" ? __(board.kanban_board_name) : board.kanban_board_name;
		this.page.set_title(title, null, true);

		await frappe.model.with_doctype(this.doctype);
		this.setup_meta();
		this.setup_toolbar();
		this.mount_board();
		// so opening Kanban without a board name comes back here
		frappe.model.user_settings.save(this.doctype, "last_view", "Kanban").then(() =>
			frappe.model.user_settings.save(this.doctype, "Kanban", {
				last_kanban_board: board_name,
			})
		);
		this.sync_filter_group_to_board();
		this.setup_group_button();
		this.setup_quick_filters();
	}

	setup_meta() {
		const meta = frappe.get_meta(this.doctype);
		this.meta = meta;

		// settings come from `{doctype}_kanban.js` or the `doctype_kanban_js` hook;
		// `boards[board_name]` overrides them for one board
		const doctype_settings = (frappe.kanban_v2.settings || {})[this.doctype] || {};
		const board_override =
			(doctype_settings.boards && doctype_settings.boards[this.current_board]) || {};
		this.settings = {
			...doctype_settings,
			...board_override,
			callbacks: {
				...(doctype_settings.callbacks || {}),
				...(board_override.callbacks || {}),
			},
		};

		this.title_field = this.resolve_title_field(meta);
		this.image_field = this.resolve_image_field(meta);
		// boards from before this setting have no value, so show assignees by default
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
			"_liked_by",
			"_user_tags",
		];
		["priority", "color", this.image_field, "exp_end_date", "end_date", "due_date"].forEach(
			(f) => {
				if (f && frappe.meta.has_field(this.doctype, f)) base.push(f);
			}
		);

		const configured = JSON.parse(this.board_doc.fields || "[]")
			.map((f) => (typeof f === "string" ? f : f && f.fieldname))
			.filter(Boolean);
		// fetch in_list_view fields with the cards so the preview needs no extra request
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

		this.card_field_list = this.compute_card_fields(meta);
		this.fields = [...new Set([...this.fields, ...this.card_field_list])];
		this.card_field_labels = {};
		this.card_field_icons = {};
		(this.board_doc.card_fields || []).forEach((f) => {
			if (!f.fieldname) return;
			if (f.label) this.card_field_labels[f.fieldname] = f.label;
			if (f.icon) this.card_field_icons[f.fieldname] = f.icon;
		});

		this.preview_field_list = this.compute_preview_fields(meta);
		this.fields = [...new Set([...this.fields, ...this.preview_field_list])];
		this.preview_field_labels = {};
		this.preview_field_icons = {};
		(this.board_doc.preview_fields || []).forEach((f) => {
			if (!f.fieldname) return;
			if (f.label) this.preview_field_labels[f.fieldname] = f.label;
			if (f.icon) this.preview_field_icons[f.fieldname] = f.icon;
		});
		this.desc_field = ["description", "content", "notes"].find((f) =>
			frappe.meta.has_field(this.doctype, f)
		);
		if (this.desc_field) this.fields = [...new Set([...this.fields, this.desc_field])];

		this.group_by_options = this.compute_group_by_options();
		if (
			this.group_by_field &&
			!this.group_by_options.some((o) => o.fieldname === this.group_by_field)
		) {
			this.group_by_field = null;
		}

		const settings = this.settings || {};
		// settings.open_on_title_click: false stops the card title opening the doc
		this.open_on_title_click =
			settings.open_on_title_click !== undefined ? settings.open_on_title_click : true;
		// settings.select_styles: { value: theme or { theme, icon } }, layered over SELECT_STYLES
		this.select_styles = { ...SELECT_STYLES };
		Object.entries(settings.select_styles || {}).forEach(([value, style]) => {
			this.select_styles[value.toLowerCase()] =
				typeof style === "string" ? { theme: style } : style;
		});
	}

	compute_card_fields(meta) {
		const configured = (this.board_doc.card_fields || [])
			.map((f) => f.fieldname)
			.filter((fn) => fn && frappe.meta.has_field(this.doctype, fn));
		const list = configured.length ? configured : this.default_card_fieldnames(meta);
		// title, image and column field are shown elsewhere on the card
		return list.filter(
			(fn) =>
				fn !== this.title_field &&
				fn !== "name" &&
				fn !== this.field_name &&
				fn !== this.image_field
		);
	}

	/** Mirrors the server seed. */
	default_card_fieldnames(meta) {
		// Check fields read as Yes/No, which says little on a card; users can still add them
		const usable = (df) =>
			frappe.model.is_value_type(df.fieldtype) && !df.hidden && df.fieldtype !== "Check";
		let dfs = meta.fields.filter((df) => df.in_list_view && usable(df));
		if (!dfs.length) dfs = meta.fields.filter((df) => df.reqd && usable(df));
		return dfs.map((df) => df.fieldname).slice(0, 6);
	}

	/** Same fallback order as the server seed. */
	resolve_title_field(meta) {
		const is_text = (df) =>
			df &&
			["Data", "Text", "Small Text", "Text Editor"].includes(df.fieldtype) &&
			!df.hidden;
		const configured = this.board_doc.title_field;
		if (configured === "name") return "name";
		if (is_text(frappe.meta.get_docfield(this.doctype, configured))) return configured;
		if (is_text(frappe.meta.get_docfield(this.doctype, meta.title_field))) {
			return meta.title_field;
		}
		const text = meta.fields.find(is_text);
		return text ? text.fieldname : "name";
	}

	resolve_image_field(meta) {
		const is_attach_image = (fn) => {
			if (!fn) return false;
			const df = frappe.meta.get_docfield(this.doctype, fn);
			return df && df.fieldtype === "Attach Image";
		};
		if (is_attach_image(this.board_doc.image_field)) return this.board_doc.image_field;
		if (is_attach_image(meta.image_field)) return meta.image_field;
		// hidden Attach Image fields count too
		const first = meta.fields.find((df) => df.fieldtype === "Attach Image");
		return first ? first.fieldname : null;
	}

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
		// shown elsewhere in the preview
		return list.filter(
			(fn) =>
				fn !== this.title_field &&
				fn !== "name" &&
				fn !== this.field_name &&
				fn !== this.image_field
		);
	}

	/** Mirrors `frappe.desk.link_preview.get_preview_data`, minus title and image. */
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

	setup_toolbar() {
		const page = this.page;
		// runs on every load; set_primary_action replaces the previous one
		page.set_primary_action(
			{ label: __("Add {0}", [__(this.doctype)]), short_label: __("Add") },
			() => frappe.new_doc(this.doctype),
			"plus"
		);

		if (this._toolbar_for === this.doctype) return; // static bits already built
		this._toolbar_for = this.doctype;

		this.setup_view_menu();

		page.add_action_icon(
			"refresh-cw",
			() => this.board && this.board.refresh(),
			"",
			__("Reload")
		);

		if (!this.board_locked) {
			page.add_menu_item(__("Save Filters"), () => this.save_filters());
		}

		// as on the list view's menu
		const docs = safe_href(this.meta.documentation, "kanban");
		if (docs) {
			page.add_dropdown_item({
				label: __("Documentation"),
				click: () => window.open(docs, "_blank"),
				standard: true,
				parent: page.menu,
				icon_right: "external-link",
			});
		}

		this.setup_filter_bar();
	}

	setup_view_menu() {
		frappe.views.BaseList.prototype.setup_view_menu.call(this);
	}

	/** No fallback: without options the Group button is hidden. */
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

	setup_filter_bar() {
		const $filter_section = this.$filter_section;
		$filter_section.empty();

		this.setup_filter_button($filter_section);
		this.setup_group_button($filter_section);
		this.setup_settings_button($filter_section);
		this.sync_board_height();
	}

	setup_quick_filters() {
		const page = this.page;
		if (!this.$quick_filters) {
			this.$quick_filters = $(
				'<div class="standard-filter-section kanban-v2-quick-filters flex"></div>'
			).insertBefore(this.$filter_section);
		}
		// keep typed values across re-renders (board or swimlane change)
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

	/** Mirrors the list view's standard filters. */
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

	get_quick_filters() {
		const out = [];
		(this._quick_filter_fields || []).forEach((fn) => {
			const field = this.page.fields_dict[fn];
			if (!field) return;
			let value = field.get_value();
			// like the list view; also lets an unchecked Check clear the filter
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

	/** A quick filter replaces a popover filter on the same field only when it has a value. */
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

	reload_board_filters() {
		// quick filters aren't in this.filters, so reset the key or a later popover edit is skipped
		this._loaded_key = null;
		if (this.group_by_field) {
			this.mount_board(); // swimlanes depend on the filtered set
			return;
		}
		if (!this.provider) return;
		this.provider.setFilters(this.get_effective_filters());
		this.board.refresh();
	}

	setup_settings_button($parent) {
		if (this.board_locked) {
			this.$settings_btn = frappe.ui.button({
				label: __("Duplicate"),
				icon: "copy",
				size: "sm",
				css_class: "settings-button mr-0",
				tooltip: __("Copy this board to change its setup"),
				onclick: () => this.duplicate_board(),
			});
			$parent.append(this.$settings_btn);
			return;
		}
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

	set_group_by(fieldname) {
		const next = fieldname || null;
		if (next === (this.group_by_field || null)) return;
		this.group_by_field = next;
		this.setup_group_button();
		this.setup_quick_filters(); // drop the now-active swimlane field from quick filters
		this.sync_board_height();
		this.mount_board();
	}

	setup_filter_button($parent) {
		// same markup as the list view's FilterArea
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
		// outside a list view, FilterGroup's clear button doesn't fire on_change
		$selector
			.find(".filter-x-button")
			.on("click", () => setTimeout(() => this.apply_filters(), 0));
		if (this.filters && this.filters.length) {
			this.filter_group.add_filters_to_filter_group(this.filters);
		}
		this.sync_filter_ui();
	}

	/** The filter group outlives a board reload, so reset it to the board's filters. */
	sync_filter_group_to_board() {
		if (!this.filter_group) return;
		const desired = JSON.stringify(this.filters || []);
		if (JSON.stringify(this.filter_group.get_filters() || []) === desired) {
			this.sync_filter_ui();
			return;
		}
		// skip the on_change reload; mount_board already loads these filters
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

	sync_filter_ui() {
		this.filter_group.update_filter_button();
		this.update_saved_indicator();
	}

	update_saved_indicator() {
		if (this.board_locked) return;
		const changed =
			JSON.stringify(this.saved_filters || []) !== JSON.stringify(this.filters || []);
		if (changed) this.page.set_indicator(__("Not Saved"), "orange");
		else this.page.clear_indicator();
	}

	apply_filters() {
		if (this._syncing_filters) return; // programmatic re-sync, not a user edit
		if (!this.filter_group) return;
		this.filters = this.filter_group.get_filters();
		this.sync_filter_ui();
		// popover open/close fires on_change without a change, so skip the reload
		const key = JSON.stringify(this.filters || []);
		if (key === this._loaded_key) return;
		this._loaded_key = key;
		if (this.group_by_field) {
			// the lanes depend on the filtered set
			this.mount_board();
			return;
		}
		if (!this.provider) return;
		this.provider.setFilters(this.get_effective_filters());
		this.board.refresh();
	}

	duplicate_board() {
		frappe.prompt(
			{
				fieldname: "board_name",
				fieldtype: "Data",
				label: __("Kanban Board Name"),
				reqd: 1,
				default: __("{0} (Copy)", [this.board_doc.kanban_board_name]),
			},
			async ({ board_name }) => {
				const { name, owner, creation, modified, modified_by, ...fields } = this.board_doc;
				const board = await frappe.xcall("frappe.client.insert", {
					doc: {
						...fields,
						kanban_board_name: board_name,
						is_standard: "No",
						module: null,
					},
				});
				frappe.set_route("List", this.doctype, "Kanban", board.name);
			},
			__("Duplicate Kanban Board"),
			__("Duplicate")
		);
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
				frappe.ui.toast({ message: __("Filters saved"), type: "success" });
			});
	}

	mount_board() {
		// lets a slow swimlane load tell it is stale
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

	make_provider(extra_filters) {
		const filters = this.get_effective_filters(extra_filters);
		return new frappe.kanban_v2.FrappeDataProvider({
			doctype: this.doctype,
			board_name: this.current_board,
			field_name: this.field_name,
			reportview_args: {
				doctype: this.doctype,
				fields: JSON.stringify(this.fields),
				order_by: "modified desc",
				filters: JSON.stringify(filters),
				with_comment_count: 1,
			},
		});
	}

	board_options(provider, opts = {}) {
		const settings = this.settings || {};
		// settings.callbacks override these; for onSelectionChange both run
		const base_callbacks = {
			onCardOpen: (card) => frappe.set_route("Form", this.doctype, card.name),
			onSelectionChange: opts.onSelectionChange || ((ids) => this.update_selection_bar(ids)),
			onMoveError: (mv) => {
				const count = (mv.cardIds || []).length;
				frappe.ui.toast({
					message:
						count > 1
							? __("Could not move {0} cards", [count])
							: __("Could not move {0}", [mv.cardId]),
					type: "error",
				});
			},
			onAddCard: (columnId) => this.add_document(columnId),
		};
		return {
			provider,
			groupBy: this.field_name,
			columnReorder: !this.board_locked,
			pageLength: opts.pageLength || 20,
			// swimlane boards size to their content, so the caller turns virtualization off
			virtualization: opts.virtualization !== undefined ? opts.virtualization : true,
			selection: "multi",
			// skeleton column count, minus archived columns, which the provider doesn't return
			skeletonColumns:
				(this.board_doc?.columns || []).filter((c) => c.status !== "Archived").length || 3,
			addCardLabel: __("Add {0}", [__(this.doctype)]),
			renderCard: settings.renderCard
				? (card, el, ctx) => settings.renderCard(card, el, ctx, this)
				: (card, el) => this.render_card(card, el),
			renderColumnHeader: settings.renderColumnHeader,
			renderEmptyState: settings.renderEmptyState,
			callbacks: this.merge_callbacks(base_callbacks, settings.callbacks || {}),
			// settings.options: extra engine options, e.g. addColumn
			...(settings.options || {}),
		};
	}

	mount_flat_board() {
		const provider = this.make_provider();
		this.provider = provider; // kept so filter changes reload in place
		this.board = new frappe.kanban_v2.KanbanVanilla(
			this.$container[0],
			this.board_options(provider)
		);
	}

	/** Each lane is its own board, so cards can't be dragged across lanes. */
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
					icon: "circle-alert",
					title: __("Could not load groups."),
				});
			}
			return;
		}
		// a newer mount (board, group or filter change) superseded this one
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

	lane_label(field, lane) {
		if (lane.unset) return __("Not set");
		if (field === "_assign") return frappe.user_info(lane.value).fullname || lane.value;
		return __(lane.label != null ? lane.label : lane.value);
	}

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
		const values = { [this.field_name]: columnId };
		(this.filters || []).forEach((f) => {
			if (f[2] === "=") values[f[1]] = f[3];
		});

		// doctypes with a custom create route need the standard flow
		if (frappe.create_routes && frappe.create_routes[this.doctype]) {
			frappe.route_options = { ...values };
			return frappe.new_doc(this.doctype, values);
		}

		// frappe.new_doc drops no_copy fields (e.g. Task.status), so build the doc here
		frappe.route_options = { ...values };
		frappe.model.with_doctype(this.doctype, () => {
			const doc = frappe.model.get_new_doc(this.doctype, null, null, true);
			Object.assign(doc, values);
			frappe.ui.form.make_quick_entry(this.doctype, null, null, doc);
		});
	}

	render_card(card, el) {
		if (card.color) el.style.borderLeft = `3px solid ${card.color}`;

		const rows = document.createElement("div");
		rows.className = "flex flex-col gap-1";

		rows.appendChild(this.title_row(card));

		for (const fieldname of this.card_field_list) {
			const df = frappe.meta.get_docfield(this.doctype, fieldname);
			if (df) rows.appendChild(this.field_row(card, df));
		}
		el.appendChild(rows);
		el.appendChild(this.card_footer(card));

		this.bind_context_menu(el, card);
	}

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

	card_tags(card) {
		if (!this.show_tags_on_card) return null;
		const tags = String(card._user_tags || "")
			.split(",")
			.map((t) => t.trim())
			.filter(Boolean);
		if (!tags.length) return null;

		const wrap = document.createElement("div");
		wrap.className = "inline-flex items-center gap-1";

		wrap.appendChild(this.tag_badge(tags[0], "lg"));

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

	hash_theme(str) {
		const themes = ["blue", "green", "amber", "red", "violet"];
		let hash = 0;
		const s = String(str || "");
		for (let i = 0; i < s.length; i++) {
			hash = (hash * 31 + s.charCodeAt(i)) % 997;
		}
		return themes[hash % themes.length];
	}

	tag_badge(tag, size = "md") {
		const MAX_TAG_CHARS = 15;
		const label = tag.length > MAX_TAG_CHARS ? tag.slice(0, MAX_TAG_CHARS) + "…" : tag;
		const $badge = frappe.ui.badge({
			label,
			theme: this.hash_theme(tag),
			size,
			title: tag,
		});
		return $badge[0];
	}

	assignee_avatar(user, size = "md") {
		const info = frappe.user_info(user);
		return frappe.ui.avatar({
			image: info.image || undefined,
			label: info.fullname || user,
			theme: this.hash_theme(user),
			size,
		})[0];
	}

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

	title_row(card) {
		const row = document.createElement("div");
		row.className = "kn-frow kn-title-row flex items-center gap-2 min-w-0 mb-0.5";

		const title_df = frappe.meta.get_docfield(this.doctype, this.title_field);
		const title_text =
			this.plain_text(card[this.title_field], title_df && title_df.fieldtype) || card.name;
		const image_url = this.image_field && card[this.image_field];
		if (this.image_field) {
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
		this.bind_more_info_hovercard(title, card);
		return row;
	}

	field_row(card, df) {
		const label = this.field_label(df);
		const icon = (this.card_field_icons || {})[df.fieldname];
		const row = document.createElement("div");
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

	field_label(df) {
		const custom = (this.card_field_labels || {})[df.fieldname];
		return __(custom || df.label || df.fieldname);
	}

	/** Tooltip, not title: a native title is unreliable over an inline SVG. */
	row_icon(icon, label) {
		const span = document.createElement("span");
		span.className =
			"kn-ficon inline-flex items-center justify-center shrink-0 size-4 text-ink-gray-4";
		span.setAttribute("aria-label", label);
		span.innerHTML = this.safe_icon(icon);
		frappe.ui.tooltip(span, { text: label, side: "top", delay: 200 });
		return span;
	}

	/** Icon names come from user config into innerHTML, so allow only [a-z0-9-]. */
	safe_icon(icon) {
		const name = String(icon || "").trim();
		if (!name || !/^[a-z0-9-]+$/i.test(name)) return "";
		return frappe.utils.icon(name, "sm");
	}

	is_rich_text(fieldtype) {
		return ["Text Editor", "Markdown Editor", "HTML", "HTML Editor", "Comment"].includes(
			fieldtype
		);
	}

	/** Decode literal \n, \t, \* escapes and turn legacy textile headings (h4.) into markdown. */
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

	plain_text(value, fieldtype) {
		let text = value == null ? "" : String(value);
		if (!text) return "";
		// render markdown so "## Title" or "**bold**" doesn't show as-is on a card
		if (fieldtype === "Markdown Editor" || this.is_rich_text(fieldtype)) {
			text = frappe.markdown(this.normalize_rich_text(text));
		}
		// Code is content, not markup; html2text also decodes entities
		if (fieldtype !== "Code" && /<[a-z!/][^>]*>/i.test(text)) {
			text = frappe.utils.html2text(text);
		}
		return text.replace(/\s+/g, " ").trim();
	}

	field_value(card, df, opts = {}) {
		const val = card[df.fieldname];
		if (val === undefined || val === null || val === "") return null;

		const el = document.createElement("div");
		el.className = "text-sm text-ink-gray-6 truncate min-w-0";

		if (df.fieldtype === "Link" && df.options === "User") {
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
			// badge only for values with a known icon; the preview always uses plain text
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

		// flatten to one line; rich text would put whole blocks of markup in a row
		if (this.is_rich_text(df.fieldtype) || df.fieldtype === "Code") {
			const text = this.plain_text(val, df.fieldtype);
			if (!text) return null;
			el.textContent = text;
			this.tip_if_long(el, text);
			return el;
		}

		el.innerHTML = frappe.format(val, df, { inline: true }, card);
		this.tip_if_long(el, this.plain_text(val, df.fieldtype) || String(val));
		return el;
	}

	tip_if_long(el, text) {
		if (!text || String(text).length <= 28) return;
		frappe.ui.tooltip(el, {
			text: frappe.ellipsis(String(text), 280),
			side: "top",
			delay: 200,
		});
	}

	select_style(value) {
		const style = this.select_styles[String(value).trim().toLowerCase()];
		return style || { theme: frappe.utils.guess_colour(value) };
	}

	bind_context_menu(el, card) {
		// a function, so "Move to" reflects the card's current column each time
		new frappe.ui.ContextMenu({
			target: $(el),
			options: () => this.card_context_menu_items(card),
		});
	}

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

		// settings.card_context_menu(card, page) returns extra items
		const settings = this.settings || {};
		if (typeof settings.card_context_menu === "function") {
			const extra = settings.card_context_menu(card, this) || [];
			if (Array.isArray(extra)) items.push(...extra);
		}
		return items;
	}

	bind_more_info_hovercard(title, card) {
		const hc = new frappe.ui.HoverCard(title, {
			side: "right",
			align: "start",
			css_class: "kn-mi-hc",
			content: () => this.more_info_content(card, () => hc.close()),
		});
	}

	more_info_content(card, close) {
		const wrap = document.createElement("div");
		wrap.className = "kn-mi flex flex-col w-full";

		// blurred cover behind a contained copy, so any aspect ratio fills the banner
		const image = this.image_field && card[this.image_field];
		if (image) {
			const banner = document.createElement("div");
			banner.className = "kn-mi-banner w-full";
			// JSON.stringify escapes quotes and parens so the URL can't break out of url()
			const url = `url(${JSON.stringify(String(image))})`;
			const bg = document.createElement("div");
			bg.className = "kn-mi-banner-bg";
			bg.style.backgroundImage = url;
			banner.appendChild(bg);
			const fg = document.createElement("div");
			fg.className = "kn-mi-banner-fg";
			fg.style.backgroundImage = url;
			banner.appendChild(fg);
			wrap.appendChild(banner);
		}

		const header = document.createElement("div");
		header.className = "kn-mi-header flex items-start gap-2 px-4 pt-3 w-full";
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

		// a rich-text preview field would repeat the description
		const preview_has_rich_text = this.preview_field_list.some((fn) => {
			const df = frappe.meta.get_docfield(this.doctype, fn);
			return df && this.is_rich_text(df.fieldtype);
		});
		if (this.desc_field && !preview_has_rich_text) {
			const d = this.description_el(card);
			if (d) wrap.appendChild(d);
		}

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

		const props = document.createElement("div");
		props.className = "kn-mi-props px-4 pt-3 w-full";
		for (const { fn, df } of short_fields) {
			const value = this.field_value(card, df, { plain_select: true });
			if (!value) continue;
			const cell = document.createElement("div");
			cell.className = "min-w-0";
			const label = this.preview_field_labels[fn] || __(df.label || df.fieldname);
			const icon = (this.preview_field_icons || {})[fn];
			const label_el = document.createElement("div");
			// fixed hovercard width, so long labels truncate
			label_el.className = "text-sm text-ink-gray-5 flex items-center gap-1 min-w-0";
			if (icon) {
				// no tooltip: the label is right beside the icon
				const span = document.createElement("span");
				span.className =
					"kn-ficon inline-flex items-center justify-center shrink-0 size-4 text-ink-gray-4";
				span.innerHTML = this.safe_icon(icon);
				label_el.appendChild(span);
			}
			const text = document.createElement("span");
			text.className = "truncate";
			text.textContent = label;
			text.title = label;
			label_el.appendChild(text);
			cell.appendChild(label_el);
			value.classList.add("mt-1", "kn-mi-val");
			value.classList.remove("truncate");
			cell.appendChild(value);
			props.appendChild(cell);
		}
		if (props.childNodes.length) wrap.appendChild(props);

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
			wrap.lastElementChild.classList.add("pb-3");
		}
		return wrap;
	}

	rich_text_preview_section(val, df, fieldname) {
		// frappe.markdown handles mixed HTML too
		const html = frappe.markdown(this.normalize_rich_text(val));
		if (!html || !html.trim()) return null;

		const section = document.createElement("div");
		section.className = "kn-mi-rich px-4 pt-3 w-full";

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

		// clamped to ~3 lines in CSS
		const content = document.createElement("div");
		content.className = "kn-mi-rich-content text-p-sm text-ink-gray-6";
		content.innerHTML = this.safe_html(html);
		section.appendChild(content);

		return section;
	}

	/** A doctype icon may be a lucide name, a Font Awesome class or an emoji. */
	doctype_icon_html() {
		const icon = (this.meta.icon || "").trim();
		// no icon beats a blank square; Font Awesome usually isn't loaded in desk
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

	/** Strip scripts, styles, on* handlers and javascript: or non-image data: URLs. */
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
				const cleaned = String(attr.value)
					.replace(/[\t\n\r]/g, "")
					.replace(/^[\u0000-\u0020]+/, "");
				if (/^(javascript|vbscript):/i.test(cleaned)) {
					el.removeAttribute(attr.name);
				} else if (/^data:/i.test(cleaned) && !/^data:image\//i.test(cleaned)) {
					el.removeAttribute(attr.name);
				}
			}
		});
		return root.innerHTML;
	}

	description_el(card) {
		const df = frappe.meta.get_docfield(this.doctype, this.desc_field);
		const val = card[this.desc_field];
		if (val === undefined || val === null || val === "") return null;
		const ft = df && df.fieldtype;
		const d = document.createElement("div");
		d.className = "kn-mi-desc text-p-sm text-ink-gray-6 px-4 pt-2 w-full";
		if (ft === "Markdown Editor" || this.is_rich_text(ft)) {
			d.innerHTML = this.safe_html(frappe.markdown(this.normalize_rich_text(val)));
		} else {
			d.textContent = frappe.ellipsis(this.plain_text(val, ft), 160);
		}
		return d;
	}

	preview_footer(card) {
		const assignees = this.preview_assignees(card);
		const tags = String(card._user_tags || "")
			.split(",")
			.map((t) => t.trim())
			.filter(Boolean);
		const comments = cint(card._comment_count);
		const likes = this.parse_json_list(card._liked_by).length;
		if (!assignees && !tags.length && !comments && !likes) return null;

		const foot = document.createElement("div");
		foot.className = "kn-mi-foot flex items-start gap-3 px-4 pb-2 mt-3 w-full";

		if (assignees) {
			assignees.classList.add("shrink-0");
			foot.appendChild(assignees);
		}

		const right = document.createElement("div");
		right.className = `flex flex-wrap items-center gap-1.5 min-w-0${
			assignees ? " flex-1 justify-end" : " ms-auto"
		}`;

		if (tags.length) {
			const icon = document.createElement("span");
			icon.className = "text-ink-gray-5 shrink-0";
			icon.innerHTML = frappe.utils.icon("tag", "sm");
			right.appendChild(icon);
			tags.forEach((tag) => right.appendChild(this.tag_badge(tag, "md")));
		}

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

	/** Interactive mode adds hovercards and a trailing "+" chip, even with no assignees. */
	assign_stack(card, { interactive = false } = {}) {
		const users = this.parse_json_list(card._assign);
		if (!interactive && !users.length) return null;

		const group = document.createElement("div");
		// overlap and ring live in .kn-assign-group
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

	assign_button(card) {
		return this.assign_stack(card, { interactive: true });
	}

	open_assign(card) {
		this.bulk().assign([card.name], () => this.board.refresh());
	}

	bind_assignee_hovercard(el, user, card) {
		const hovercard = new frappe.ui.HoverCard(el, {
			side: "bottom",
			align: "start",
			css_class: "kn-assignee-popover",
			// built on open, so `hovercard` is set by then
			content: () => this.assignee_hovercard(user, card, hovercard),
		});
	}

	assignee_hovercard(user, card, hovercard) {
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
		return (v && JSON.parse(v)) || [];
	}
};

/**
 * Swimlanes: one independent board per group value, so no cross-lane drag.
 * Lanes mount lazily, at most 2 at a time. Exposes the destroy / refresh /
 * engine surface the page calls on a board.
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
		// shell only; the board mounts when the lane is visible or expanded
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
			// expanding a never-mounted lane must load it now
			if (!collapsed) this.ensure_lane_mounted(index);
		};
		$head.on("click", toggle);
		$head.on("keydown", (e) => {
			if (e.key === "Enter" || e.key === " ") {
				e.preventDefault();
				toggle();
			}
		});
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

	setup_lazy_mount() {
		// the first two lanes are almost always visible, so don't wait for the observer
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

	ensure_lane_mounted(index) {
		if (this._destroyed) return;
		const entry = this.boards[index];
		if (!entry || entry.board || entry._queued) return;
		entry._queued = true;
		this._mount_queue.push(index);
		this.drain_mount_queue();
	}

	drain_mount_queue() {
		if (this._destroyed) return;
		while (this._mounting_count < this._max_concurrent_mounts && this._mount_queue.length) {
			const index = this._mount_queue.shift();
			this._mounting_count++;
			this.mount_lane_board(index);
			// hold the slot for a frame so lane loads don't all start in one tick
			requestAnimationFrame(() => {
				this._mounting_count--;
				this.drain_mount_queue();
			});
		}
	}

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

	/** Selection stays in one lane: selecting in one clears the others. */
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
		// unmounted lanes load when first shown; the lane set only changes with filters, which remount
		this.boards.forEach((b) => b.board && b.board.refresh());
	}

	destroy() {
		this._destroyed = true;
		this._mount_queue = [];
		if (this._observer) {
			this._observer.disconnect();
			this._observer = null;
		}
		this.boards.forEach((b) => b.board && b.board.destroy());
		this.boards = [];
		this.$root && this.$root.remove();
		this.$root = null;
	}

	/** Lets the selection bar and "Move to" work across lanes. */
	get engine() {
		const boards = this.boards;
		return {
			select: (ids) =>
				boards.forEach((b) => {
					if (b.board) b.board.engine.select(ids);
				}),
			get state() {
				const mounted = boards.find((b) => b.board);
				return (mounted && mounted.board.engine.state) || { columns: [], selection: [] };
			},
			applyMove: (cardId, from, to, index) => {
				const hit = boards.find((b) => b.board && b.board.engine.findCard(cardId));
				if (hit) hit.board.engine.applyMove(cardId, from, to, index);
			},
		};
	}
};

frappe.views.KanbanV2View = class KanbanV2View {
	constructor(opts) {
		this.doctype = opts.doctype;
		this.view_name = "Kanban";
		this.parent = opts.parent;
		this.page = this.parent.page;
		this._kanban = new frappe.views.KanbanV2Page(this.parent);
		this.show();
	}

	show() {
		frappe.route_options = {};
		return this._kanban.load_from_route();
	}

	/** The view switcher carries these filters to the next view, as from a list view. */
	get_search_params() {
		const search_params = new URLSearchParams();
		for (const [doctype, field, operator, value] of this._kanban.get_effective_filters()) {
			const key = doctype === this.doctype ? field : `${doctype}.${field}`;
			search_params.append(
				key,
				operator === "=" ? value : JSON.stringify([operator, value])
			);
		}
		return search_params;
	}
};
