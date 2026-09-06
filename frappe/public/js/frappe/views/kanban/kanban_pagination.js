/** Kanban column pagination — lazy-loaded with kanban_board.bundle.js. */
export const kanban_pagination = {
	// Per-column paging: 50 cards per fetch, max 500 in memory, prefetch on scroll.
	build_column_state() {
		const next = {};
		this.get_active_kanban_columns().forEach((col) => {
			next[col.column_name] = this.new_kanban_column_state();
		});
		this.kanban_column_state = next;
	},

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
	},

	parse_column_order(order) {
		if (!order) return [];
		try {
			const parsed = typeof order === "string" ? JSON.parse(order) : order;
			return Array.isArray(parsed) ? parsed : [];
		} catch {
			return [];
		}
	},

	rebuild_column_loaded_names(column, field_name) {
		// Callers pass either a mapped board column (has `title`) or a raw Kanban
		// Board child row (has `column_name`); resolve either so `loaded_names` is
		// rebuilt correctly. If this stays empty the memory cap never engages.
		const column_title = column.title ?? column.column_name;
		const saved = this.parse_column_order(column.order);
		const in_column = (this.data || []).filter((d) => d[field_name] === column_title);
		const in_set = new Set(in_column.map((d) => d.name));
		const names = [];

		for (const name of saved) {
			if (in_set.has(name)) names.push(name);
		}
		for (const doc of in_column) {
			if (!names.includes(doc.name)) names.push(doc.name);
		}
		return names;
	},

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
	},

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
	},

	sync_kanban_column_state_from_board(columns, extra_keep_names = []) {
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
				const keep_names = new Set(board_names);

				for (const [title, column_data] of Object.entries(message?.columns || {})) {
					const rows = this.parse_kanban_cards(column_data.cards);
					rows.forEach((row) => {
						data_map.set(row.name, row);
						keep_names.add(row.name);
					});
				}

				// Keep cards already in the column memory window (pagination beyond first page).
				for (const col of columns) {
					if (col.status === "Archived") continue;
					const state = this.kanban_column_state[col.title];
					state?.loaded_names?.forEach((name) => keep_names.add(name));
				}

				(extra_keep_names || []).forEach((name) => keep_names.add(name));

				// Do not drop freshly fetched or in-memory cards that are not yet in saved column order.
				this.data = Array.from(data_map.values()).filter((doc) =>
					keep_names.has(doc.name)
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
	},

	get_column_memory_count(column_title) {
		return this.kanban_column_state[column_title]?.loaded_names?.length || 0;
	},

	get_column_total_count(column_title) {
		return this.kanban_column_state[column_title]?.total_count ?? 0;
	},

	get_prefetch_trigger_distance() {
		return this.kanban_prefetch_trigger;
	},

	get_kanban_api_args(extra = {}) {
		const args = { ...this.get_call_args().args };
		args.board_name = this.board_name;
		args.kanban_page_length = this.kanban_page_size;
		delete args.start;
		delete args.page_length;
		return { ...args, ...extra };
	},

	parse_kanban_cards(cards) {
		if (!cards) return [];
		if (Array.isArray(cards)) return cards;
		return frappe.utils.dict(cards.keys, cards.values);
	},

	align_column_loaded_names(column_title) {
		const col = this.get_active_kanban_columns().find((c) => c.column_name === column_title);
		const state = this.kanban_column_state?.[column_title];
		const field_name = this.board?.field_name;
		if (!col || !state || !field_name) return;
		state.loaded_names = this.rebuild_column_loaded_names(col, field_name);
	},

	sync_column_order_after_drag(column_title, order_names) {
		const state = this.kanban_column_state?.[column_title];
		if (!state || !order_names?.length) return;

		const memory = new Set(state.loaded_names);
		state.loaded_names = order_names.filter((name) => memory.has(name));
		this.reconcile_column_pagination_state(state, column_title);
	},

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
	},

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
	},

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
	},

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
	},

	can_prefetch_column_forward(column_title) {
		const state = this.kanban_column_state[column_title];
		if (!state || state.inflight) return false;
		if (state.total_count !== null && state.loaded >= state.total_count) return false;
		if (state.loaded_names.length < this.kanban_max_column_cards) return true;

		const to_evict = state.loaded_names.length - this.kanban_max_column_cards + 1;
		const safe_evict =
			this.kanban?.get_column_safe_evict_count?.(column_title, to_evict) ?? to_evict;
		return safe_evict > 0;
	},

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
	},

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
	},

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
	},

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
	},
};
