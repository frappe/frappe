import KanbanSettings from "./kanban_settings";

frappe.provide("frappe.views");

/*
 * Kanban list view — loads card data from the server.
 *
 * @deprecated Classic Kanban engine. Superseded by the vanilla-JS Kanban v2
 * engine in views/kanban_v2/ (frappe.views.KanbanV2View). A board renders with
 * this engine when its "Use Kanban v2" flag (Kanban Board.use_kanban_v2) is OFF
 * — the default; see list_factory.js. Kept for backward compatibility — do not
 * add features here, port them to kanban_v2 instead.
 *
 * This file fetches cards in pages and keeps them in memory (this.data).
 * The board UI (kanban_board.bundle.js) only draws the cards you can see on screen.
 *
 * See build_column_state() for how paging works.
 */

frappe.views.KanbanView = class KanbanView extends frappe.views.ListView {
	static full_page = true;
	static no_sidebar = true;

	static load_last_view() {
		const route = frappe.get_route();
		if (route.length === 3) {
			const doctype = route[1];
			const user_settings = frappe.get_user_settings(doctype)["Kanban"] || {};
			if (!user_settings.last_kanban_board) {
				return new frappe.views.KanbanView({ doctype: doctype });
			}

			route.push(user_settings.last_kanban_board);
			frappe.set_route(route);
			return true;
		}
		return false;
	}

	get view_name() {
		return "Kanban";
	}

	show() {
		frappe.views.KanbanView.get_kanbans(this.doctype).then((kanbans) => {
			frappe.route_options = {};
			if (!kanbans.length) {
				return frappe.views.KanbanView.show_kanban_dialog(this.doctype, true);
			} else if (kanbans.length && frappe.get_route().length !== 4) {
				// Try to use the last board the user used, else default to the first available board
				const last_board = frappe.get_user_settings(this.doctype)["Kanban"]
					?.last_kanban_board;
				if (last_board && kanbans.includes(last_board)) {
					frappe.set_route("List", this.doctype, "Kanban", last_board);
					return;
				} else {
					const first_board = kanbans[0];
					frappe.set_route("List", this.doctype, "Kanban", first_board.name);
					return;
				}
			} else {
				this.kanbans = kanbans;

				return frappe.run_serially([
					() => this.show_skeleton(),
					() => this.fetch_meta(),
					() => this.hide_skeleton(),
					() => this.check_permissions(),
					() => this.init(),
					() => this.before_refresh(),
					() => this.refresh(),
				]);
			}
		});
	}

	init() {
		return super.init().then(() => {
			// Same debounced path as list view: list_update + kanban_board_update → render_list.
			this.debounced_refresh = frappe.utils.debounce(
				this.process_document_refreshes.bind(this),
				500
			);
			this.pending_kanban_board_refresh = false;
			let menu_length = this.page.menu.find(".dropdown-item").length;
			if (menu_length === 1) {
				// Only 'Refresh' (hidden) is present (always), dropdown is visibly empty
				this.page.hide_menu();
			}
		});
	}

	setup_defaults() {
		return super.setup_defaults().then(() => {
			let get_board_name = () => {
				return this.kanbans.length && this.kanbans[0].name;
			};

			this.board_name = frappe.get_route()[3] || get_board_name() || null;
			this.page_title = __(this.board_name);
			this.card_meta = this.get_card_meta();
			this.page_length = 0;
			// How many cards to load and keep in memory (works with kanban_board.bundle.js):
			// kanban_page_size — cards per server request (first load + each scroll load).
			// kanban_prefetch_trigger — start loading more when user is this many cards from the bottom.
			// kanban_max_column_cards — max cards kept in memory per column; older ones are removed.
			this.kanban_page_size = 50;
			this.kanban_prefetch_trigger = 25;
			this.kanban_max_column_cards = 500;
			this.kanban_column_state = {};

			return frappe.run_serially([
				() => this.set_board_perms_and_push_menu_items(),
				() => this.get_board(),
			]);
		});
	}

	set_board_perms_and_push_menu_items() {
		// needs server-side call as client-side document instance is absent before kanban render
		return frappe.call({
			method: "frappe.client.get_doc_permissions",
			args: {
				doctype: "Kanban Board",
				docname: this.board_name,
			},
			callback: (result) => {
				this.board_perms = result.message.permissions || {};
				this.push_menu_items();
			},
		});
	}

	push_menu_items() {
		if (this.board_perms.write) {
			this.menu_items.push({
				label: __("Save filters"),
				action: () => {
					this.save_kanban_board_filters();
				},
			});
		}

		if (this.board_perms.delete) {
			this.menu_items.push({
				label: __("Delete Kanban Board"),
				action: () => {
					frappe.confirm(__("Are you sure you want to proceed?"), () => {
						frappe.db.delete_doc("Kanban Board", this.board_name).then(() => {
							frappe.show_alert(`Kanban Board ${this.board_name} deleted.`);
							frappe.set_route("List", this.doctype, "List");
						});
					});
				},
			});
		}
	}

	setup_result_container_area() {
		// pass
	}

	setup_result_area() {
		this.$result = $(`<div class="result">`);
		this.$frappe_list.append(this.$result);
	}

	setup_paging_area() {
		// pass
	}

	set_result_height() {
		// pass
	}

	toggle_result_area() {
		// Kanban should remain visible even when no cards are loaded yet,
		// so the board columns and empty state can render.
		this.$result.show();
	}

	get_board() {
		return frappe.db.get_doc("Kanban Board", this.board_name).then((board) => {
			this.board = board;
			this.board.filters_array = JSON.parse(this.board.filters || "[]");
			this.board.fields = JSON.parse(this.board.fields || "[]");
			this.filters = this.board.filters_array;
			// Re-resolve after the board loads so title_field / image_field apply.
			this.card_meta = this.get_card_meta();
			this.image_field = this.resolve_image_field();
		});
	}

	setup_page() {
		this.hide_page_form = true;
		this.hide_card_layout = true;
		this.hide_sort_selector = true;
		super.setup_page();
	}

	setup_view() {
		if (this.board.columns.filter((col) => col.status !== "Archived").length > 4) {
			this.page.container.addClass("full-width");
		}
		this.setup_realtime_updates();
		this.setup_kanban_board_realtime();
		this.setup_like();
	}

	/**
	 * Reload the board: fetch totals + first page per column, then draw it.
	 */
	refresh() {
		this.freeze(true);

		return Promise.resolve(this.load_lib)
			.then(() => this.refresh_kanban_pages())
			.then(() => {
				this.toggle_result_area();
				this.before_render();
				return this.render_kanban_board();
			})
			.then(() => {
				this.after_render();
				this.freeze(false);
			})
			.catch((err) => {
				console.error("Kanban refresh failed", err);
				this.freeze(false);
				frappe.show_alert({
					message: __("Failed to load Kanban board"),
					indicator: "red",
				});
			});
	}

	/** Columns that are not archived. */
	get_active_kanban_columns() {
		return (this.board?.columns || []).filter((col) => col.status !== "Archived");
	}

	// Column pagination lives in kanban_pagination.js (loaded with kanban_board.bundle.js).

	/** Map Kanban Board child rows to the column shape used by the board UI. */
	map_kanban_board_columns(board) {
		return (board?.columns || []).map((col) => ({
			title: col.column_name,
			status: col.status,
			order: col.order,
			indicator: col.indicator || "gray",
		}));
	}

	apply_kanban_board_doc(board) {
		this.board = board;
		this.board.filters_array = JSON.parse(this.board.filters || "[]");
		this.board.fields = JSON.parse(this.board.fields || "[]");
	}

	/** Reload card pages and column order after a cross-tab board update. */
	refresh_kanban_board_from_realtime() {
		return frappe.db
			.get_doc("Kanban Board", this.board_name)
			.then((board) => {
				this.apply_kanban_board_doc(board);
				const columns = this.map_kanban_board_columns(board);

				return this.refresh_kanban_pages().then(() => {
					if (this.kanban && !this.skip_kanban_realtime) {
						this.kanban.sync_from_realtime(this.data, columns, null);
					} else if (!this.kanban) {
						return this.render_kanban_board();
					}
				});
			})
			.catch((err) => {
				console.error("Kanban board refresh failed", err);
			});
	}

	/** Refresh when another user changes column order on this board. */
	setup_kanban_board_realtime() {
		if (this.kanban_board_realtime_setup) return;

		frappe.realtime.on("kanban_board_update", (data) => {
			if (data.board_name !== this.board_name) return;
			this.pending_kanban_board_refresh = true;
			if (this.avoid_realtime_update() || this.skip_kanban_realtime) return;
			this.debounced_refresh();
		});
		this.kanban_board_realtime_setup = true;
	}

	/** When a card changes, update it in memory and redraw (no full list re-sort). */
	process_document_refreshes() {
		const board_refresh_only =
			!this.pending_document_refreshes?.length && this.pending_kanban_board_refresh;

		if (!this.pending_document_refreshes?.length && !this.pending_kanban_board_refresh) {
			return;
		}

		if (this.skip_kanban_realtime) {
			return;
		}

		const route = frappe.get_route() || [];
		if (!cur_list || route[0] != "List" || cur_list.doctype != route[1]) {
			this.pending_document_refreshes = [];
			this.pending_kanban_board_refresh = false;
			this.disable_realtime_updates();
			return;
		}

		if (board_refresh_only) {
			this.pending_kanban_board_refresh = false;
			return this.refresh_kanban_board_from_realtime();
		}

		const names = this.pending_document_refreshes.map((d) => d.name);
		this.pending_document_refreshes = this.pending_document_refreshes.filter(
			(d) => names.indexOf(d.name) === -1
		);

		if (!names.length) {
			if (this.pending_kanban_board_refresh) {
				this.pending_kanban_board_refresh = false;
				this.render_list();
			}
			return;
		}

		const call_args = this.get_call_args();
		call_args.args.filters.push([this.doctype, "name", "in", names]);
		call_args.args.start = 0;

		frappe.call(call_args).then(({ message }) => {
			if (!message) return;
			const data = frappe.utils.dict(message.keys, message.values);

			if (!(data && data.length)) {
				this.data = this.data.filter((d) => !names.includes(d.name));
			} else {
				const index_by_name = new Map(this.data.map((doc, i) => [doc.name, i]));
				data.forEach((datum) => {
					const index = index_by_name.get(datum.name);
					if (index === undefined) {
						this.data.push(datum);
					} else {
						this.data[index] = datum;
					}
				});
			}

			// Kanban column order comes from the board — do not re-sort this.data like list view.
			this.pending_kanban_board_refresh = false;
			this.toggle_result_area();
			this.render_list(names);
		});
	}

	render_list(changed_names) {
		if (!this.kanban || this.skip_kanban_realtime) return;
		this._changed_card_names = changed_names || null;
		this._render_kanban_from_server();
	}

	/** Apply board/card realtime updates queued while a local drag is settling. */
	flush_deferred_kanban_realtime() {
		if (this.skip_kanban_realtime) return;
		if (this.pending_kanban_board_refresh || this.pending_document_refreshes?.length) {
			this.debounced_refresh();
		}
	}

	begin_kanban_local_drag_sync() {
		// Pause incoming realtime reconciliation while local drag save is in flight.
		this._local_drag_sync_count = (this._local_drag_sync_count || 0) + 1;
		this.skip_kanban_realtime = true;
	}

	end_kanban_local_drag_sync() {
		// Resume realtime only after the last local drag request settles.
		this._local_drag_sync_count = Math.max(0, (this._local_drag_sync_count || 0) - 1);
		if (this._local_drag_sync_count > 0) return;
		this.skip_kanban_realtime = false;
		// Apply any board/card events queued while realtime was paused.
		this.flush_deferred_kanban_realtime();
	}

	/** After a realtime update, load latest column order and refresh cards. */
	_render_kanban_from_server() {
		if (this._kanban_sync_in_flight) {
			this._kanban_sync_pending = true;
			return;
		}

		this._kanban_sync_in_flight = true;
		return frappe.db
			.get_doc("Kanban Board", this.board_name)
			.then((board) => {
				if (this.skip_kanban_realtime || !this.kanban) return;
				this.apply_kanban_board_doc(board);
				const columns = this.map_kanban_board_columns(board);
				const changed_card_names = this._changed_card_names;
				this.kanban.sync_from_realtime(this.data, columns, changed_card_names);
				this._changed_card_names = null;
				return this.sync_kanban_column_state_from_board(columns, changed_card_names);
			})
			.finally(() => {
				this._kanban_sync_in_flight = false;
				if (this._kanban_sync_pending) {
					this._kanban_sync_pending = false;
					this._render_kanban_from_server();
				}
			});
	}

	set_fields() {
		// Fetch only required + Kanban Board configured fields (optimization: avoid fetching all doctype fields)
		this.fields = [];
		// Core: identity and column
		this._add_field("name");
		this._add_field("creation");
		this._add_field(this.board.field_name, this.board.reference_doctype);
		this._add_field(this.card_meta.title_field);
		// Card UI: assignments, tags, like, comment count
		this._add_field("_assign");
		this._add_field("_user_tags");
		this._add_field("_liked_by");
		this._add_field("_comments");
		this._add_field("owner");
		// Kanban Board document's configured fields (card body content)
		if (this.board.fields && Array.isArray(this.board.fields)) {
			this.board.fields.forEach((field_spec) => {
				const fieldname =
					typeof field_spec === "string" ? field_spec : field_spec?.fieldname;
				if (fieldname) this._add_field(fieldname);
			});
		}
		// Optional: image and color if the board / doctype has them
		if (this.image_field) this._add_field(this.image_field);
		if (frappe.meta.has_field(this.doctype, "color")) this._add_field("color");
	}

	before_render() {
		frappe.model.user_settings.save(this.doctype, "last_view", this.view_name);
		this.save_view_user_settings({
			last_kanban_board: this.board_name,
		});
	}

	on_filter_change() {
		if (!this.board_perms.write) return; // avoid misleading ux

		if (JSON.stringify(this.board.filters_array) !== JSON.stringify(this.filter_area.get())) {
			this.page.set_indicator(__("Not Saved"), "orange");
		} else {
			this.page.clear_indicator();
		}
	}

	save_kanban_board_filters() {
		const filters = this.filter_area.get();

		frappe.db.set_value("Kanban Board", this.board_name, "filters", filters).then((r) => {
			if (r.exc) {
				frappe.show_alert({
					indicator: "red",
					message: __("There was an error saving filters"),
				});
				return;
			}
			frappe.show_alert({
				indicator: "green",
				message: __("Filters saved"),
			});

			this.board.filters_array = filters;
			this.on_filter_change();
			this.refresh();
		});
	}

	get_fields() {
		// board.field_name already added in set_fields(); just return built field list
		return super.get_fields();
	}

	render() {
		return this.render_kanban_board();
	}

	/** Wait for kanban bundle before creating/updating the board (same pattern as Gantt view). */
	render_kanban_board() {
		return Promise.resolve(this.load_lib).then(() => {
			const board_name = this.board_name;
			if (!frappe.views.KanbanBoard) {
				throw new Error("Kanban board library failed to load");
			}
			if (!this.kanban) {
				this.kanban = new frappe.views.KanbanBoard({
					doctype: this.doctype,
					board: this.board,
					board_name: board_name,
					cards: this.data,
					card_meta: this.card_meta,
					wrapper: this.$result,
					cur_list: this,
					user_settings: this.view_user_settings,
				});
			} else if (board_name === this.kanban.board_name) {
				this.$result.empty();
				this.kanban.update(this.data);
			}
		});
	}

	get_card_meta() {
		var meta = frappe.get_meta(this.doctype);
		// preserve route options erased by new doc
		let route_options = { ...frappe.route_options };
		var doc = frappe.model.get_new_doc(this.doctype);
		frappe.route_options = route_options;
		var title_field = null;
		var quick_entry = false;

		// Prefer the board's configured title (name or Data); fall back for old boards.
		const board_title = this.board && this.board.title_field;
		if (board_title === "name") {
			title_field = frappe.meta.get_field(this.doctype, "name");
		} else if (board_title) {
			const df = frappe.meta.get_field(this.doctype, board_title);
			if (df && df.fieldtype === "Data" && !df.hidden) title_field = df;
		}

		if (!title_field && this.meta.title_field) {
			const df = frappe.meta.get_field(this.doctype, this.meta.title_field);
			if (df && df.fieldtype === "Data" && !df.hidden) title_field = df;
		}

		if (!title_field) {
			title_field = this.meta.fields.find((df) => df.fieldtype === "Data" && !df.hidden);
		}

		// quick entry
		var mandatory = meta.fields.filter((df) => df.reqd && !doc[df.fieldname]);

		if (
			mandatory.some((df) => frappe.model.table_fields.includes(df.fieldtype)) ||
			mandatory.length > 1
		) {
			quick_entry = true;
		}

		if (!title_field) {
			title_field = frappe.meta.get_field(this.doctype, "name");
		}

		return { quick_entry, title_field };
	}

	/**
	 * Board image_field when Attach Image; else doctype image_field.
	 * Used by card rendering and field fetching.
	 */
	resolve_image_field() {
		const is_image = (fn) => {
			if (!fn) return null;
			const df = frappe.meta.get_field(this.doctype, fn);
			return df && df.fieldtype === "Attach Image" && !df.hidden ? fn : null;
		};
		return (
			is_image(this.board && this.board.image_field) ||
			is_image(this.meta.image_field) ||
			null
		);
	}

	get_image_url(doc) {
		const field = this.image_field || this.meta.image_field;
		return (field && doc && doc[field]) || null;
	}

	get_view_settings() {
		return {
			label: __("Kanban Settings", null, "Button in kanban view menu"),
			action: () => this.show_kanban_settings(),
			standard: true,
		};
	}

	show_kanban_settings() {
		frappe.model.with_doctype(this.doctype, () => {
			new KanbanSettings({
				kanbanview: this,
				doctype: this.doctype,
				settings: this.board,
				meta: frappe.get_meta(this.doctype),
			});
		});
	}

	get required_libs() {
		return "kanban_board.bundle.js";
	}
};

frappe.views.KanbanView.get_kanbans = function (doctype) {
	let kanbans = [];

	return get_kanban_boards().then((kanban_boards) => {
		if (kanban_boards) {
			frappe.views._kanban_engine_cache = frappe.views._kanban_engine_cache || {};
			kanban_boards.forEach((board) => {
				let route = `/desk/${frappe.router.slug(board.reference_doctype)}/view/kanban/${
					board.name
				}`;
				kanbans.push({ name: board.name, route: route });
				// Prime the engine cache so switching to this board picks the right
				// UI without another round-trip (see ListFactory.get_kanban_engine).
				frappe.views._kanban_engine_cache[board.name] = !!cint(board.use_kanban_v2);
			});
		}

		return kanbans;
	});

	function get_kanban_boards() {
		return frappe
			.call("frappe.desk.doctype.kanban_board.kanban_board.get_kanban_boards", { doctype })
			.then((r) => r.message);
	}
};

frappe.views.KanbanView.show_kanban_dialog = function (doctype) {
	let dialog = new_kanban_dialog();
	dialog.show();

	function make_kanban_board(board_name, field_name, project, use_kanban_v2) {
		return frappe.call({
			method: "frappe.desk.doctype.kanban_board.kanban_board.quick_kanban_board",
			args: {
				doctype,
				board_name,
				field_name,
				project,
				use_kanban_v2,
			},
			callback: function (r) {
				var kb = r.message;
				if (kb.filters) {
					frappe.provide("frappe.kanban_filters");
					frappe.kanban_filters[kb.kanban_board_name] = kb.filters;
				}
				frappe.set_route("List", doctype, "Kanban", kb.kanban_board_name);
			},
		});
	}

	function new_kanban_dialog() {
		/* Kanban dialog can show either "Save" or "Customize Form" option depending if any Select fields exist in the DocType for Kanban creation
		 */

		const select_fields = frappe.get_meta(doctype).fields.filter((df) => {
			return df.fieldtype === "Select" && df.fieldname !== "kanban_column";
		});
		const dialog_fields = get_fields_for_dialog(select_fields);
		const to_save = select_fields.length > 0;
		const primary_action_label = to_save ? __("Save") : __("Customize Form");
		const dialog_title = to_save ? __("New Kanban Board") : __("No Select Field Found");

		let primary_action = () => {
			if (to_save) {
				const values = dialog.get_values();
				make_kanban_board(
					values.board_name,
					values.field_name,
					values.project,
					cint(values.use_kanban_v2) // Ensure it's 0 or 1, not undefined
				).then(
					() => dialog.hide(),
					(err) => frappe.msgprint(err)
				);
			} else {
				frappe.set_route("Form", "Customize Form", { doc_type: doctype });
			}
		};

		return new frappe.ui.Dialog({
			title: dialog_title,
			fields: dialog_fields,
			primary_action_label,
			primary_action,
		});
	}

	function get_fields_for_dialog(select_fields) {
		if (!select_fields.length) {
			return [
				{
					fieldtype: "HTML",
					options: `
					<div>
						<p class="text-medium">
						${__(
							'No fields found that can be used as a Kanban Column. Use the Customize Form to add a Custom Field of type "Select".'
						)}
						</p>
					</div>
				`,
				},
			];
		}

		let fields = [
			{
				fieldtype: "Data",
				fieldname: "board_name",
				label: __("Kanban Board Name"),
				reqd: 1,
				description: ["Note", "ToDo"].includes(doctype)
					? __("This Kanban Board will be private")
					: "",
			},
			{
				fieldtype: "Select",
				fieldname: "field_name",
				label: __("Columns based on"),
				options: select_fields.map((df) => ({ label: df.label, value: df.fieldname })),
				default: select_fields[0],
				reqd: 1,
			},
			// Check field for use_kanban_v2
			{
				fieldtype: "Check",
				fieldname: "use_kanban_v2",
				label: __("Use Kanban V2 (New Experience)"),
				description: __("Enable the new Kanban experience for this board"),
			},
		];

		if (doctype === "Task") {
			fields.push({
				fieldtype: "Link",
				fieldname: "project",
				label: __("Project"),
				options: "Project",
			});
		}

		return fields;
	}
};
