import KanbanSettings from "./kanban_settings";

frappe.provide("frappe.views");

/*
 * Kanban list view — loads card data from the server.
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
				console.error("Kanban refresh failed:", err);
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

	/*
	 * Per-column state — which cards are loaded in memory.
	 *
	 * Old behaviour: open board → load ALL cards for ALL columns (very slow on big boards).
	 * New behaviour: load 50 per column first, load more on scroll, keep max 500 in memory.
	 *
	 * Steps:
	 *   1. First load — totals + 50 cards per column (refresh_kanban_pages).
	 *   2. Scroll down — load next 50 (prefetch_kanban_column).
	 *   3. Over 500 in memory — remove oldest cards (enforce_column_memory_cap).
	 *   4. Scroll up — load cards that were removed (prefetch_kanban_column_back).
	 *
	 * Key fields per column:
	 *   total_count  — how many cards exist (shown in column header).
	 *   window_start — index of the first card we still have in memory.
	 *   offset       — where to start the next server request.
	 *   loaded_names — card names currently in this.data for this column.
	 *
	 * kanban_board.bundle.js only draws visible cards on screen; this file controls
	 * which card data exists in memory at all.
	 */
	/** Reset paging state for every column. */
	build_column_state() {
		const next = {};
		this.get_active_kanban_columns().forEach((col) => {
			next[col.column_name] = this.new_kanban_column_state();
		});
		this.kanban_column_state = next;
	}

	new_kanban_column_state() {
		return {
			loaded: 0,
			offset: 0,
			window_start: 0,
			total_count: null,
			inflight: false,
			loaded_names: [],
			last_prefetch_offset: -1,
			last_backward_fetch_start: -1,
		};
	}

	parse_column_order(order) {
		if (!order) return [];
		try {
			const parsed = typeof order === "string" ? JSON.parse(order) : order;
			return Array.isArray(parsed) ? parsed : [];
		} catch {
			return [];
		}
	}

	/** Rebuild in-memory card names for a column from this.data and saved board order. */
	rebuild_column_loaded_names(column, field_name) {
		const saved = this.parse_column_order(column.order);
		const in_column = (this.data || []).filter((d) => d[field_name] === column.title);
		const in_set = new Set(in_column.map((d) => d.name));
		const names = [];

		for (const name of saved) {
			if (in_set.has(name)) names.push(name);
		}
		for (const doc of in_column) {
			if (!names.includes(doc.name)) names.push(doc.name);
		}
		return names;
	}

	/** Keep loaded/offset and prefetch guards aligned with what is actually in memory. */
	reconcile_column_pagination_state(state, column_title) {
		if (!state) return;

		if (column_title != null && state.total_count != null) {
			this.prune_stale_column_cards(column_title, state.total_count);
		}

		const memory_end = state.window_start + state.loaded_names.length;
		if (state.total_count != null) {
			if (state.loaded >= state.total_count && memory_end < state.total_count) {
				state.loaded = memory_end;
			} else {
				state.loaded = Math.min(Math.max(state.loaded, memory_end), state.total_count);
			}
		} else {
			state.loaded = Math.max(state.loaded, memory_end);
		}
		state.offset = state.loaded;
		state.last_prefetch_offset = -1;
		state.last_backward_fetch_start = -1;
	}

	/** Drop extra in-memory cards when the server total is smaller than our window. */
	prune_stale_column_cards(column_title, total_count) {
		const field_name = this.board?.field_name;
		const state = this.kanban_column_state?.[column_title];
		if (!field_name || !state || total_count == null) return;

		if (state.window_start >= total_count) {
			state.window_start = Math.max(0, total_count - state.loaded_names.length);
		}

		const max_names = Math.max(0, total_count - state.window_start);
		if (state.loaded_names.length <= max_names) return;

		const removed = state.loaded_names.splice(max_names);
		const removed_set = new Set(removed);
		this.data = (this.data || []).filter(
			(doc) => !(doc[field_name] === column_title && removed_set.has(doc.name))
		);
	}

	/** Refresh paging state after another tab changes board order or card positions. */
	sync_kanban_column_state_from_board(columns) {
		const field_name = this.board?.field_name;
		if (!field_name || !this.kanban_column_state) {
			return Promise.resolve();
		}

		const board_names = new Set();
		for (const col of columns) {
			if (col.status === "Archived") continue;
			this.parse_column_order(col.order).forEach((name) => board_names.add(name));
		}

		return frappe
			.call({
				method: "frappe.desk.doctype.kanban_board.kanban_board.get_kanban_board_data",
				args: this.get_kanban_api_args(),
				freeze: false,
			})
			.then(({ message }) => {
				const data_map = new Map((this.data || []).map((doc) => [doc.name, doc]));

				for (const [title, column_data] of Object.entries(message?.columns || {})) {
					const rows = this.parse_kanban_cards(column_data.cards);
					rows.forEach((row) => data_map.set(row.name, row));
				}

				this.data = Array.from(data_map.values()).filter((doc) =>
					board_names.has(doc.name)
				);

				for (const col of columns) {
					if (col.status === "Archived") continue;
					const state = this.kanban_column_state[col.title];
					if (!state) continue;

					const column_data = message?.columns?.[col.title];
					if (column_data) {
						state.total_count = column_data.total ?? 0;
					}
					state.loaded_names = this.rebuild_column_loaded_names(col, field_name);
					this.reconcile_column_pagination_state(state, col.title);
				}
			})
			.catch(() => {});
	}

	/** How many cards we have in memory for this column (not the total on the server). */
	get_column_memory_count(column_title) {
		return this.kanban_column_state[column_title]?.loaded_names?.length || 0;
	}

	get_column_total_count(column_title) {
		return this.kanban_column_state[column_title]?.total_count ?? 0;
	}

	get_prefetch_trigger_distance() {
		return this.kanban_prefetch_trigger;
	}

	/** Build API request with the same fields and filters as list view. */
	get_kanban_api_args(extra = {}) {
		const args = { ...this.get_call_args().args };
		args.board_name = this.board_name;
		args.kanban_page_length = this.kanban_page_size;
		delete args.start;
		delete args.page_length;
		return { ...args, ...extra };
	}

	/** Turn server response into a list of card objects. */
	parse_kanban_cards(cards) {
		if (!cards) return [];
		if (Array.isArray(cards)) return cards;
		return frappe.utils.dict(cards.keys, cards.values);
	}

	/** Re-sort loaded_names to match saved board order after fetch or drag. */
	align_column_loaded_names(column_title) {
		const col = this.get_active_kanban_columns().find((c) => c.column_name === column_title);
		const state = this.kanban_column_state?.[column_title];
		const field_name = this.board?.field_name;
		if (!col || !state || !field_name) return;
		state.loaded_names = this.rebuild_column_loaded_names(col, field_name);
	}

	/** Keep pagination loaded_names aligned with persisted order after drag. */
	sync_column_order_after_drag(column_title, order_names) {
		const state = this.kanban_column_state?.[column_title];
		if (!state || !order_names?.length) return;

		const memory = new Set(state.loaded_names);
		state.loaded_names = order_names.filter((name) => memory.has(name));
		this.reconcile_column_pagination_state(state, column_title);
	}

	/** Add new cards at the end of a column (user scrolled down).

	At 500 cards, removes the oldest from memory and moves window_start forward.
	User can load them again by scrolling up.
	*/
	merge_kanban_cards_for_column(column_title, rows) {
		if (!rows?.length) return 0;

		const state = this.kanban_column_state[column_title];
		const map = new Map((this.data || []).map((d) => [d.name, d]));

		rows.forEach((row) => {
			map.set(row.name, row);
			if (state && !state.loaded_names.includes(row.name)) {
				state.loaded_names.push(row.name);
			}
		});

		let evicted = 0;
		if (state) {
			evicted = this.enforce_column_memory_cap(column_title, map, "top");
			if (evicted) {
				state.window_start += evicted;
				state.last_backward_fetch_start = -1;
			}
		}

		this.data = Array.from(map.values());
		this.align_column_loaded_names(column_title);
		return evicted;
	}

	/** Add cards at the start of a column (user scrolled up).

	Moves window_start back. May remove newest cards from the bottom to stay under 500.
	*/
	prepend_kanban_cards_for_column(column_title, rows) {
		if (!rows?.length) return 0;

		const state = this.kanban_column_state[column_title];
		const map = new Map((this.data || []).map((d) => [d.name, d]));
		let added = 0;

		for (let i = rows.length - 1; i >= 0; i--) {
			const row = rows[i];
			map.set(row.name, row);
			if (state && !state.loaded_names.includes(row.name)) {
				state.loaded_names.unshift(row.name);
				added++;
			}
		}

		let evicted = 0;
		if (state) {
			state.window_start = Math.max(0, state.window_start - added);
			evicted = this.enforce_column_memory_cap(column_title, map, "bottom");
			if (evicted) {
				state.offset = Math.max(
					state.window_start + state.loaded_names.length,
					state.offset - evicted
				);
				state.loaded = state.offset;
			}
			if (added) {
				state.last_prefetch_offset = -1;
			}
		}

		this.data = Array.from(map.values());
		this.align_column_loaded_names(column_title);
		return evicted;
	}

	/** Remove extra cards when a column has more than 500 in memory.

	Only removes cards that are not on screen (checked via column_registry),
	so the scroll position does not jump.

	@param edge - "top" = scrolling down (drop oldest), "bottom" = scrolling up (drop newest).
	*/
	enforce_column_memory_cap(column_title, data_map, edge = "top") {
		if (this.kanban_drag_in_progress) {
			return 0;
		}
		const state = this.kanban_column_state[column_title];
		const field_name = this.board?.field_name;
		const max_cards = this.kanban_max_column_cards;
		if (!state) return 0;

		if (field_name) {
			state.loaded_names = state.loaded_names.filter((name) => {
				const doc = data_map.get(name);
				return doc && doc[field_name] === column_title;
			});
		}

		let evicted = 0;
		while (state.loaded_names.length > max_cards) {
			const to_evict = state.loaded_names.length - max_cards;
			const safe_evict =
				edge === "top"
					? this.kanban?.get_column_safe_evict_count?.(column_title, to_evict) ??
					  to_evict
					: this.kanban?.get_column_safe_evict_from_bottom?.(column_title, to_evict) ??
					  to_evict;
			if (safe_evict <= 0) {
				break;
			}
			for (let i = 0; i < safe_evict; i++) {
				const evicted_name =
					edge === "top" ? state.loaded_names.shift() : state.loaded_names.pop();
				data_map.delete(evicted_name);
				evicted++;
			}
		}
		return evicted;
	}

	/** Update counts and loaded card lists after dragging a card to another column.

	@param old_index - card position in the full source column (not just visible cards).
	@param new_index - card position in the full destination column.
	*/
	on_kanban_card_moved(card_name, from_col, to_col, old_index, new_index) {
		if (!card_name || from_col === to_col) return;

		const from_state = this.kanban_column_state[from_col];
		const to_state = this.kanban_column_state[to_col];

		if (from_state) {
			from_state.loaded_names = from_state.loaded_names.filter((name) => name !== card_name);
			if (from_state.total_count != null) {
				from_state.total_count = Math.max(0, from_state.total_count - 1);
			}
			if (old_index != null) {
				if (old_index < from_state.window_start) {
					from_state.window_start = Math.max(0, from_state.window_start - 1);
				}
				if (old_index < from_state.offset) {
					from_state.loaded = Math.max(
						from_state.window_start + from_state.loaded_names.length,
						from_state.offset - 1
					);
					from_state.offset = from_state.loaded;
				}
			}
			from_state.last_prefetch_offset = -1;
		}
		if (to_state) {
			const already_in_memory = to_state.loaded_names.includes(card_name);
			const was_at_fetch_end =
				to_state.total_count != null && to_state.loaded >= to_state.total_count;

			if (!already_in_memory) {
				if (new_index != null) {
					if (
						new_index >= to_state.window_start &&
						new_index <= to_state.window_start + to_state.loaded_names.length
					) {
						const local_index = new_index - to_state.window_start;
						to_state.loaded_names.splice(local_index, 0, card_name);
					} else if (new_index > to_state.window_start + to_state.loaded_names.length) {
						to_state.loaded_names.push(card_name);
					}
				} else {
					to_state.loaded_names.push(card_name);
				}
			}
			if (to_state.total_count != null) {
				to_state.total_count += 1;
			}
			if (new_index != null) {
				if (new_index < to_state.window_start) {
					to_state.window_start += 1;
				}
				if (new_index < to_state.offset) {
					to_state.loaded += 1;
					to_state.offset = to_state.loaded;
				} else if (was_at_fetch_end) {
					to_state.loaded = to_state.total_count;
					to_state.offset = to_state.total_count;
				}
			} else if (was_at_fetch_end) {
				to_state.loaded = to_state.total_count;
				to_state.offset = to_state.total_count;
			}
			to_state.last_prefetch_offset = -1;
		}

		this.reconcile_column_pagination_state(from_state, from_col);
		this.reconcile_column_pagination_state(to_state, to_col);
	}

	/** Can we load more cards when scrolling down? (not at end, room to remove old ones). */
	can_prefetch_column_forward(column_title) {
		const state = this.kanban_column_state[column_title];
		if (!state || state.inflight) return false;
		if (state.total_count !== null && state.loaded >= state.total_count) return false;
		if (state.loaded_names.length < this.kanban_max_column_cards) return true;

		const to_evict = state.loaded_names.length - this.kanban_max_column_cards + 1;
		const safe_evict =
			this.kanban?.get_column_safe_evict_count?.(column_title, to_evict) ?? to_evict;
		return safe_evict > 0;
	}

	/** Save the result of a column page API call into memory. */
	apply_kanban_column_result(column_title, { total, cards }) {
		const state = this.kanban_column_state[column_title];
		if (!state) return { rows: [], evicted: 0 };

		const rows = this.parse_kanban_cards(cards);
		if (total != null) {
			state.total_count = total;
		}

		if (!rows.length) {
			if (total != null) {
				this.reconcile_column_pagination_state(state, column_title);
			}
			return { rows: [], evicted: 0 };
		}

		state.loaded += rows.length;
		state.offset = state.loaded;
		if (total != null && rows.length < this.kanban_page_size) {
			state.loaded = total;
			state.offset = total;
		}

		const evicted = this.merge_kanban_cards_for_column(column_title, rows);
		if (total != null) {
			this.reconcile_column_pagination_state(state, column_title);
		}
		return { rows, evicted };
	}

	/** First load: get total count + first 50 cards for each column.

	Example: 4 columns load 200 cards, not the whole board.
	*/
	async refresh_kanban_pages() {
		if (!this.board?.columns?.length) {
			return;
		}

		this.build_column_state();
		this.data = [];

		const { message } = await frappe.call({
			method: "frappe.desk.doctype.kanban_board.kanban_board.get_kanban_board_data",
			args: this.get_kanban_api_args(),
		});

		Object.entries(message?.columns || {}).forEach(([column_title, column_data]) => {
			const state = this.kanban_column_state[column_title];
			if (!state) return;
			const rows = this.parse_kanban_cards(column_data.cards);
			state.total_count = column_data.total ?? 0;
			state.loaded = rows.length;
			state.offset = rows.length;
			state.window_start = 0;
			state.loaded_names = [];
			this.merge_kanban_cards_for_column(column_title, rows);
			this.align_column_loaded_names(column_title);
		});
	}

	/** Load the next 50 cards when user nears the bottom of a column.

	Triggered from kanban_board.bundle.js before user runs out of cards, so scroll feels smooth.
	*/
	async prefetch_kanban_column(column_title) {
		if (this.kanban_drag_in_progress) {
			return;
		}
		const state = this.kanban_column_state[column_title];
		if (!this.can_prefetch_column_forward(column_title)) {
			return;
		}
		if (state.last_prefetch_offset === state.offset) {
			return;
		}

		state.inflight = true;
		const fetch_offset = state.offset;

		try {
			const { message } = await frappe.call({
				method: "frappe.desk.doctype.kanban_board.kanban_board.get_kanban_column_page",
				args: this.get_kanban_api_args({
					column_name: column_title,
					kanban_start: fetch_offset,
				}),
				freeze: false,
			});
			const { rows, evicted } = this.apply_kanban_column_result(column_title, message);
			state.last_prefetch_offset = fetch_offset;

			if (!rows.length) {
				return;
			}

			if (this.kanban) {
				requestAnimationFrame(() => {
					this.kanban.append_column_cards(rows, column_title, evicted, "top");
				});
			}
		} finally {
			state.inflight = false;
		}
	}

	/** Load older cards when user scrolls up (cards that were removed from memory). */
	async prefetch_kanban_column_back(column_title) {
		if (this.kanban_drag_in_progress) {
			return;
		}
		const state = this.kanban_column_state[column_title];
		if (!state || state.inflight || state.window_start <= 0) {
			return;
		}

		const fetch_start = Math.max(0, state.window_start - this.kanban_page_size);
		const page_length = state.window_start - fetch_start;
		if (page_length <= 0) return;
		if (state.last_backward_fetch_start === fetch_start) {
			return;
		}

		state.inflight = true;

		try {
			const { message } = await frappe.call({
				method: "frappe.desk.doctype.kanban_board.kanban_board.get_kanban_column_page",
				args: this.get_kanban_api_args({
					column_name: column_title,
					kanban_start: fetch_start,
					kanban_page_length: page_length,
				}),
				freeze: false,
			});

			const rows = this.parse_kanban_cards(message?.cards);

			if (message?.total != null) {
				state.total_count = message.total;
				this.prune_stale_column_cards(column_title, message.total);
				this.reconcile_column_pagination_state(state, column_title);
			}

			if (!rows.length) return;

			state.last_backward_fetch_start = fetch_start;
			state.last_prefetch_offset = -1;
			const evicted = this.prepend_kanban_cards_for_column(column_title, rows);

			if (this.kanban) {
				requestAnimationFrame(() => {
					this.kanban.append_column_cards(rows, column_title, evicted, "bottom");
				});
			}
		} finally {
			state.inflight = false;
		}
	}

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
				console.error("Kanban board refresh failed:", err);
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
				this.kanban.sync_from_realtime(this.data, columns, this._changed_card_names);
				this._changed_card_names = null;
				return this.sync_kanban_column_state_from_board(columns);
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
		// Optional: image and color if doctype has them
		if (this.meta.image_field) this._add_field(this.meta.image_field);
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

		if (this.meta.title_field) {
			title_field = frappe.meta.get_field(this.doctype, this.meta.title_field);
		}

		this.meta.fields.forEach((df) => {
			const is_valid_field =
				["Data", "Text", "Small Text", "Text Editor"].includes(df.fieldtype) && !df.hidden;

			if (is_valid_field && !title_field) {
				// can be mapped to textarea
				title_field = df;
			}
		});

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

		return {
			quick_entry: quick_entry,
			title_field: title_field,
		};
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
			kanban_boards.forEach((board) => {
				let route = `/desk/${frappe.router.slug(board.reference_doctype)}/view/kanban/${
					board.name
				}`;
				kanbans.push({ name: board.name, route: route });
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

	function make_kanban_board(board_name, field_name, project) {
		return frappe.call({
			method: "frappe.desk.doctype.kanban_board.kanban_board.quick_kanban_board",
			args: {
				doctype,
				board_name,
				field_name,
				project,
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
				make_kanban_board(values.board_name, values.field_name, values.project).then(
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
