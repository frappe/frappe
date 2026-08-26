// TODO: Refactor for better UX
//
// Kanban runs in two steps for speed:
//
// 1. Load data in pages (kanban_view.js)
//    - 50 cards per column at first, more on scroll, max 500 kept in memory.
// 2. Only draw visible cards (this file)
//    - 500 cards would still mean 500 HTML elements; we only render what you see.
//    - Columns with 30+ cards use empty spacers so scroll still feels full height.
//
// Result: fast open, less memory, smooth scroll, drag-and-drop without redrawing everything.

import { watch } from "vue";
import { createPinia, defineStore } from "pinia";
import { kanban_pagination } from "./kanban_pagination.js";

frappe.provide("frappe.views");
if (frappe.views.KanbanView) {
	Object.assign(frappe.views.KanbanView.prototype, kanban_pagination);
}

(function () {
	var method_prefix = "frappe.desk.doctype.kanban_board.kanban_board.";

	let active_board = null;
	const LARGE_BOARD_ORDER_SYNC_LIMIT = 200;
	var prepared_card_cache = {}; // Card HTML built only when shown on screen.
	var column_registry = {}; // Per-column scroll + render helpers.
	var suppress_cards_watch = false;
	var kanban_realtime_syncing = false;
	var drag_list_offsets = null; // column title -> full-order index of first visible DOM card

	const use_kanban_store = defineStore("kanban", {
		state: () => ({
			doctype: "",
			board: {},
			card_meta: {},
			cards: [],
			cards_index: null,
			columns: [],
			filters_modified: false,
			cur_list: {},
			empty_state: true,
			wrapper: null,
		}),
		// Actions reference the module-level `store` (same instance as `this`) so
		// nested non-arrow callbacks don't lose the store binding.
		actions: {
			update_state(obj) {
				const { keep_prepared_cache, ...updates } = obj;
				Object.assign(store, updates);
				if (updates.cards && store.board?.field_name) {
					store.cards_index = build_cards_index(store.cards, store.board.field_name);
					if (!keep_prepared_cache) {
						clear_prepared_card_cache();
					}
				}
			},
			init(opts) {
				store.update_state({
					empty_state: true,
				});
				var board = opts.board;
				var card_meta = opts.card_meta;
				opts.card_meta = card_meta;
				opts.board = board;
				// Keep raw list data; prepare cards lazily when rendered.
				var cards = opts.cards;
				var columns = prepare_columns(board.columns);
				store.update_state({
					doctype: opts.doctype,
					board: board,
					card_meta: card_meta,
					cards: cards,
					columns: columns,
					cur_list: opts.cur_list,
					empty_state: false,
					wrapper: opts.wrapper,
				});
			},
			update_cards(cards) {
				store.update_state({
					cards: cards.uniqBy((card) => card.name),
				});
			},
			/** Add new cards to the store without clearing the card HTML cache. */
			merge_column_cards({ cards, keep_prepared_cache }) {
				if (!cards?.length) return;
				const map = new Map(store.cards.map((c) => [c.name, c]));
				cards.forEach((card) => map.set(card.name, card));
				store.update_state({
					cards: Array.from(map.values()).uniqBy((card) => card.name),
					keep_prepared_cache: !!keep_prepared_cache,
				});
			},
			/** Replace all cards in the store (e.g. after cards removed from memory). */
			sync_cards({ cards, keep_prepared_cache }) {
				store.update_state({
					cards: (cards || []).uniqBy((card) => card.name),
					keep_prepared_cache: !!keep_prepared_cache,
				});
			},
			add_column(col) {
				if (frappe.model.can_create("Custom Field")) {
					store.update_column({ col, action: "add" });
				} else {
					frappe.msgprint({
						title: __("Not permitted"),
						message: __("You are not allowed to create columns"),
						indicator: "red",
					});
				}
			},
			archive_column(col) {
				store.update_column({ col, action: "archive" });
			},
			restore_column(col) {
				store.update_column({ col, action: "restore" });
			},
			update_column({ col, action }) {
				var doctype = store.doctype;
				var board = store.board;
				fetch_customization(doctype)
					.then(function (doc) {
						return modify_column_field_in_c11n(doc, board, col.title, action);
					})
					.then(save_customization)
					.then(function () {
						return update_kanban_board(board.name, col.title, action);
					})
					.then(
						function (r) {
							var cols = r.message;
							store.update_state({
								columns: prepare_columns(cols),
							});
						},
						function (err) {
							console.error(err);
						}
					);
			},
			add_card({ card_title, column_title }) {
				var doc = frappe.model.get_new_doc(store.doctype);
				var field = store.card_meta.title_field;
				var quick_entry = store.card_meta.quick_entry;

				var doc_fields = {};
				doc_fields[field.fieldname] = card_title;
				doc_fields[store.board.field_name] = column_title;
				store.cur_list.filter_area.get().forEach(function (f) {
					if (f[2] !== "=") return;
					doc_fields[f[1]] = f[3];
				});

				$.extend(doc, doc_fields);

				// add the card directly
				// for better ux
				const card = prepare_card(doc, store);
				card._disable_click = true;
				const cards = [...store.cards, card];
				// remember the name which we will override later
				const old_name = doc.name;
				store.update_state({ cards });

				if (field && !quick_entry) {
					return insert_doc(doc).then(function (r) {
						// update the card in place with the updated doc
						const updated_doc = r.message;
						const index = store.cards.findIndex((card) => card.name === old_name);
						const card = prepare_card(updated_doc, store);
						const new_cards = store.cards.slice();
						new_cards[index] = card;
						store.update_state({ cards: new_cards });
						const args = {
							new: 1,
							name: card.name,
							colname: updated_doc[store.board.field_name],
						};
						store.update_order_for_single_card(args);
					});
				} else {
					frappe.new_doc(store.doctype, doc);
				}
			},
			update_card(card) {
				var index = -1;
				store.cards.forEach(function (c, i) {
					if (c.name === card.name) {
						index = i;
					}
				});
				var cards = store.cards.slice();
				if (index !== -1) {
					cards.splice(index, 1, card);
				}
				store.update_state({ cards: cards });
			},
			update_order_for_single_card(card) {
				const _cards = clone_cards_state(store.cards);
				const _columns = store.columns.map((c) => ({
					...c,
					order: c.order,
				}));
				let args = {};
				let method_name = "";
				const is_optimistic_drag = !card.new && card.optimistic;

				if (card.new) {
					method_name = "add_card";
					args = {
						board_name: store.board.name,
						docname: card.name,
						colname: card.colname,
					};
				} else {
					method_name = "update_order_for_single_card";
					args = {
						board_name: store.board.name,
						docname: card.name,
						from_colname: card.from_colname,
						to_colname: card.to_colname,
					};
					if (card.from_order != null && card.to_order != null) {
						args.from_order = card.from_order;
						args.to_order = card.to_order;
					} else {
						args.old_index = card.old_index;
						args.new_index = card.new_index;
					}
				}

				if (!is_optimistic_drag) {
					frappe.dom.freeze();
				}

				return frappe
					.call({
						method: method_prefix + method_name,
						args: args,
						callback: (r) => {
							const board = r.message;
							const columns = prepare_columns(board.columns);

							if (is_optimistic_drag) {
								// Local columns were set from post-drag DOM order in apply_card_move.
								return;
							}

							const updated_cards = [
								{ name: card.name, column: card.to_colname || card.colname },
							];
							const cards = update_cards_column(updated_cards);
							store.update_state({
								cards: cards,
								columns: columns,
							});
						},
					})
					.fail(function () {
						if (is_optimistic_drag) {
							restore_drag_snapshot({ cards: _cards, columns: _columns }, card);
							return;
						}
						store.update_state({
							cards: _cards,
							columns: _columns,
						});
					})
					.always(function () {
						if (!is_optimistic_drag) {
							frappe.dom.unfreeze();
						}
					});
			},
			update_order() {
				// Skip expensive full-order sync on very large boards; drag saves still persist per-card order.
				if (store.cards.length > LARGE_BOARD_ORDER_SYNC_LIMIT) {
					return;
				}

				// cache original order
				const _cards = store.cards.slice();
				const _columns = store.columns.slice();

				// Build order from saved column order — not only in-memory cards.
				const order = {};
				const cards_index = store.cards_index;
				store.columns.forEach(function (col) {
					if (!is_active_column(col)) return;
					order[col.title] = get_column_full_order(col, cards_index);
				});

				frappe
					.call({
						method: method_prefix + "update_order",
						args: {
							board_name: store.board.name,
							order: order,
						},
						callback: (r) => {
							var board = r.message[0];
							var updated_cards = r.message[1];
							var cards = update_cards_column(updated_cards);
							var columns = prepare_columns(board.columns);
							store.update_state({
								cards: cards,
								columns: columns,
							});
						},
					})
					.fail(function () {
						// revert original order
						store.update_state({
							cards: _cards,
							columns: _columns,
						});
					});
			},
			update_column_order(order) {
				return frappe
					.call({
						method: method_prefix + "update_column_order",
						args: {
							board_name: store.board.name,
							order: order,
						},
					})
					.then(function (r) {
						var board = r.message;
						var columns = prepare_columns(board.columns);
						store.update_state({
							columns: columns,
						});
					});
			},
			set_indicator({ column, color }) {
				column_registry[column.title]?.set_indicator(color);
				return frappe
					.call({
						method: method_prefix + "set_indicator",
						args: {
							board_name: store.board.name,
							column_name: column.title,
							indicator: color,
						},
					})
					.then(function (r) {
						var board = r.message;
						var columns = prepare_columns(board.columns);
						store.update_state({
							columns: columns,
						});
					});
			},
			/** Apply card and order changes from another tab without rebuilding the whole board. */
			sync_from_realtime({ cards, columns: incoming_columns, changed_names }) {
				if (kanban_realtime_syncing) return;
				kanban_realtime_syncing = true;

				const field_name = store.board.field_name;
				const old_columns = store.columns;
				const old_index = store.cards_index;
				const columns = incoming_columns || store.columns;
				const reconciled_cards = reconcile_cards_with_board_orders(
					cards,
					columns,
					field_name
				);
				const new_index = build_cards_index(reconciled_cards, field_name);
				const columns_to_refresh = get_columns_needing_refresh(
					old_columns,
					columns,
					old_index,
					new_index,
					field_name
				);
				const changed_name_set = new Set(changed_names || []);
				if (changed_name_set.size) {
					for (const name of changed_name_set) {
						delete prepared_card_cache[name];
						const card = new_index.by_name?.[name] || old_index?.by_name?.[name];
						if (!card) continue;
						const col = get_card_column(card, field_name);
						if (col) columns_to_refresh.add(col);
					}
				}

				suppress_cards_watch = true;
				store.update_state({
					cards: reconciled_cards,
					columns,
					keep_prepared_cache: true,
				});

				columns_to_refresh.forEach((title) => {
					const col = columns.find((c) => c.title === title);
					if (!col) return;
					const registry = column_registry[title];
					if (!registry) return;

					const has_content_change = [...changed_name_set].some((name) => {
						const card = store.cards_index?.by_name?.[name];
						return card && get_card_column(card, field_name) === title;
					});
					if (has_content_change) {
						registry.refresh(true);
						return;
					}

					const names = get_column_display_order(col, store.cards_index);
					registry.apply_realtime_sync(names);
				});
				suppress_cards_watch = false;
				kanban_realtime_syncing = false;
			},
		},
	});

	// The store lives outside any Vue app, so it gets its own pinia instance.
	var store = use_kanban_store(createPinia());

	// vuex-style watch_store(); getters written as (state) => state.x keep
	// working because pinia exposes state props directly on the store.
	function watch_store(getter, callback) {
		return watch(() => getter(store), callback);
	}

	frappe.views.KanbanBoard = function (opts) {
		var self = {};
		self.wrapper = opts.wrapper;
		self.cur_list = opts.cur_list;
		self.board_name = opts.board_name;
		self.board_perms = self.cur_list.board_perms;
		self.unwatchers = [];
		self.columns = [];

		self.update = function (cards) {
			// update cards internally
			opts.cards = cards;

			if (self.wrapper.find(".kanban").length > 0) {
				store.update_cards(cards);
			} else {
				init();
			}
		};

		/** Update the board after more cards are loaded or removed from memory.

		KanbanView updates this.data, then calls here to refresh the store.
		If cards were removed, scroll position is fixed so the screen does not jump.
		*/
		self.append_column_cards = function (_cards, column_title, evicted_count, edge) {
			if (!self.wrapper.find(".kanban").length) return;

			const list = store.cur_list;
			if (list?.data && (_cards?.length || evicted_count)) {
				store.sync_cards({
					cards: list.data,
					keep_prepared_cache: true,
				});
			}
			if (evicted_count) {
				column_registry[column_title]?.on_cards_trimmed(evicted_count, edge || "top");
			}
			column_registry[column_title]?.refresh(false);
		};

		self.get_column_safe_evict_count = function (column_title, max_evict) {
			return column_registry[column_title]?.get_safe_evict_count(max_evict) ?? max_evict;
		};

		self.get_column_safe_evict_from_bottom = function (column_title, max_evict) {
			return (
				column_registry[column_title]?.get_safe_evict_from_bottom(max_evict) ?? max_evict
			);
		};

		/** Sync cards and saved column order from realtime (other browser / user). */
		self.sync_from_realtime = function (cards, columns, changed_names) {
			if (!self.wrapper.find(".kanban").length) return;
			store.sync_from_realtime({ cards, columns, changed_names });
		};

		self.teardown = function () {
			self.unwatchers.forEach((unwatch) => unwatch());
			self.unwatchers = [];
			self.columns.forEach((column) => column.unwatch && column.unwatch());
			self.columns = [];
		};

		function init() {
			// store is a shared singleton: release the previously active board's watchers
			// (this instance on re-render, or an abandoned one after switching boards)
			active_board && active_board.teardown();
			active_board = self;
			store.init(opts);
			self.unwatchers.push(
				watch_store((state) => {
					return state.columns;
				}, make_columns)
			);
			prepare();
			make_columns();
			self.unwatchers.push(
				watch_store((state) => {
					return state.cur_list;
				}, setup_restore_columns)
			);
			self.unwatchers.push(
				watch_store((state) => {
					return state.columns;
				}, setup_restore_columns)
			);
			self.unwatchers.push(
				watch_store((state) => {
					return state.empty_state;
				}, show_empty_state)
			);

			requestAnimationFrame(() => {
				store.update_order();
			});
		}

		function prepare() {
			self.$kanban_board = self.wrapper.find(".kanban");

			if (self.$kanban_board.length === 0) {
				self.$kanban_board = $(frappe.render_template("kanban_board"));
				self.$kanban_board.appendTo(self.wrapper);
			}

			self.$filter_area = self.cur_list.$page.find(".active-tag-filters");
			bind_events();
			setup_sortable();
		}

		function make_columns() {
			var columns = store.columns.filter(is_active_column);
			var $existing = self.$kanban_board.find(".kanban-column").not(".add-new-column");

			// Skip full rebuild when column structure is unchanged (e.g. update_order on load).
			if ($existing.length === columns.length && columns.length > 0) {
				let structure_matches = true;
				$existing.each(function (i) {
					if ($(this).attr("data-column-value") !== columns[i].title) {
						structure_matches = false;
					}
				});
				if (structure_matches) {
					$existing.each(function (i) {
						apply_column_indicator($(this), columns[i].indicator || "gray");
					});
					return;
				}
			}

			self.columns.forEach((column) => column.unwatch && column.unwatch());
			self.columns = [];
			self.$kanban_board.find(".kanban-column").not(".add-new-column").remove();
			clear_column_registry();
			self.columns = columns.map(function (col) {
				return frappe.views.KanbanBoardColumn(col, self.$kanban_board, self.board_perms);
			});
		}

		function bind_events() {
			bind_add_column();
			bind_clickdrag();
		}

		function setup_sortable() {
			// If no write access to board, editing board (by dragging column) should be blocked
			if (!self.board_perms.write) return;

			var sortable = new Sortable(self.$kanban_board.get(0), {
				group: "columns",
				animation: 150,
				dataIdAttr: "data-column-value",
				filter: ".add-new-column",
				handle: ".kanban-column-title",
				onEnd: function () {
					var order = sortable.toArray();
					order = order.slice(1);
					store.update_column_order(order);
				},
			});
		}

		function bind_add_column() {
			let doctype = self.cur_list.doctype;
			let fieldname = self.cur_list.board.field_name;
			const is_custom_field = frappe.meta.get_docfield(doctype, fieldname)?.is_custom_field;

			if (!self.board_perms.write || !is_custom_field) {
				// If no write access to board, editing board (by adding column) should be blocked
				// If standard field then users can't add options
				self.$kanban_board.find(".add-new-column").remove();
				return;
			}

			var $add_new_column = self.$kanban_board.find(".add-new-column"),
				$compose_column = $add_new_column.find(".compose-column"),
				$compose_column_form = $add_new_column.find(".compose-column-form").hide();

			$compose_column.on("click", function () {
				$(this).hide();
				$compose_column_form.show();
				$compose_column_form.find("input").focus();
			});

			//save on enter
			$compose_column_form.keydown(function (e) {
				if (e.which == 13) {
					e.preventDefault();
					if (!frappe.request.ajax_count) {
						// not already working -- double entry
						var title = $compose_column_form.serializeArray()[0].value;
						var col = {
							title: title.trim(),
						};
						store.add_column(col);
						$compose_column_form.find("input").val("");
						$compose_column.show();
						$compose_column_form.hide();
					}
				}
			});

			// on form blur
			$compose_column_form.find("input").on("blur", function () {
				$(this).val("");
				$compose_column.show();
				$compose_column_form.hide();
			});
		}

		function bind_clickdrag() {
			let isDown = false;
			let startX;
			let scrollLeft;
			let draggable = self.$kanban_board[0];

			draggable.addEventListener("mousedown", (e) => {
				// don't trigger scroll if one of the ancestors of the
				// clicked element matches any of these selectors
				let ignoreEl = [
					".kanban-column .kanban-column-header",
					".kanban-column .add-card",
					".kanban-column .kanban-card.new-card-area",
					".kanban-card-wrapper",
				];
				if (ignoreEl.some((el) => e.target.closest(el))) return;

				isDown = true;
				draggable.classList.add("clickdrag-active");
				startX = e.pageX - draggable.offsetLeft;
				scrollLeft = draggable.scrollLeft;
			});
			draggable.addEventListener("mouseleave", () => {
				isDown = false;
				draggable.classList.remove("clickdrag-active");
			});
			draggable.addEventListener("mouseup", () => {
				isDown = false;
				draggable.classList.remove("clickdrag-active");
			});
			draggable.addEventListener("mousemove", (e) => {
				if (!isDown) return;
				e.preventDefault();
				const x = e.pageX - draggable.offsetLeft;
				const walk = x - startX;
				draggable.scrollLeft = scrollLeft - walk;
			});
		}

		function setup_restore_columns() {
			var cur_list = store.cur_list;
			var columns = store.columns;
			var list_row_right = cur_list.$page
				.find(`[data-list-renderer='Kanban'] .list-row-right`)
				.css("margin-right", "15px");
			list_row_right.empty();

			var archived_columns = columns.filter(function (col) {
				return col.status === "Archived";
			});

			if (!archived_columns.length) return;

			var options = archived_columns.reduce(function (a, b) {
				return (
					a +
					`<li><a class='option'>" +
					"<span class='ellipsis' style='max-width: 100px; display: inline-block'>" +
					__(b.title) + "</span>" +
					"<button style='float:right;' data-column='" + b.title +
					"' class='btn btn-default btn-xs restore-column text-muted'>"
					+ __('Restore') + "</button></a></li>`
				);
			}, "");
			var $dropdown = $(
				"<div class='dropdown pull-right'>" +
					"<a class='text-muted dropdown-toggle' data-toggle='dropdown'>" +
					"<span class='dropdown-text'>" +
					__("Archived Columns") +
					"</span><i class='caret'></i></a>" +
					"<ul class='dropdown-menu'>" +
					options +
					"</ul>" +
					"</div>"
			);

			list_row_right.html($dropdown);

			$dropdown.find(".dropdown-menu").on("click", "button.restore-column", function () {
				var column_title = $(this).data().column;
				var col = {
					title: column_title,
					status: "Archived",
				};
				store.restore_column(col);
			});
		}

		function show_empty_state() {
			var empty_state = store.empty_state;

			if (empty_state) {
				self.$kanban_board.find(".kanban-column").hide();
				self.$kanban_board.find(".kanban-empty-state").show();
			} else {
				self.$kanban_board.find(".kanban-column").show();
				self.$kanban_board.find(".kanban-empty-state").hide();
			}
		}

		init();

		return self;
	};

	frappe.views.KanbanBoardColumn = function (column, wrapper, board_perms) {
		var self = {};
		var filtered_cards = [];

		/*
		 * Which cards are drawn on screen for this column.
		 *
		 * ordered_names — full list of card names in this column (from memory).
		 * virt_start / virt_end — which cards are actually drawn (e.g. cards 20–40 of 500).
		 * Top/bottom spacers — empty blocks that keep scroll bar the right size.
		 * card_height — height of one card (used for math).
		 * buffer_cards — draw a few extra cards above/below so scroll does not flicker.
		 * virtualization_disabled — turned off while dragging so the card stays under the cursor.
		 * min_cards_to_virtualize — under 30 cards, just draw them all (simpler).
		 */
		var virt_state = {
			card_height: 108,
			buffer_cards: 8,
			total_cards: 0,
			virt_start: 0,
			virt_end: 0,
			scroll_listener_attached: false,
			scroll_raf_pending: false,
			suppress_scroll_render: false,
			ordered_names: [],
			virtualization_disabled: false,
			variable_height_threshold: 24,
			has_variable_height_cards: false,
			min_cards_to_virtualize: 30,
		};

		function init() {
			make_dom();
			setup_sortable();
			init_virtualization();
			// Paint column chrome first, then cards on the next frame.
			requestAnimationFrame(() => make_cards());
			self.unwatch = watch_store(
				(state) => {
					const column_cards = state.cards_index?.by_column[column.title] || [];
					return column_cards.map((card) => card.name).join("\u0001");
				},
				function () {
					if (suppress_cards_watch) return;
					make_cards();
				}
			);
			bind_add_card();
			bind_options();

			column_registry[column.title] = {
				// Links memory cleanup (KanbanView) with what is on screen (virt_state).
				/** Full saved-order index of the first card currently rendered in this column. */
				get_dom_list_offset() {
					return get_column_dom_list_offset(self.$kanban_cards);
				},
				/** Redraw the column. force=true resets which cards are considered visible. */
				refresh(force) {
					if (force) {
						virt_state.virt_start = -1;
						virt_state.virt_end = -1;
					}
					make_cards();
				},
				/** How many cards above the screen can be removed from memory safely. */
				get_safe_evict_count(max_evict) {
					if (!max_evict) return 0;
					const buffer = virt_state.buffer_cards;
					const above_viewport = Math.max(0, virt_state.virt_start - buffer);
					return Math.min(max_evict, above_viewport);
				},
				/** Fix scroll position after cards are removed from memory. */
				on_cards_trimmed(evicted_count, edge) {
					if (!evicted_count) return;
					const card_height = virt_state.card_height || 108;
					if (edge === "bottom") {
						virt_state.virt_end = Math.max(
							virt_state.virt_start,
							virt_state.virt_end - evicted_count
						);
						const scroll_top =
							(self.$kanban_cards.scrollTop() || 0) + evicted_count * card_height;
						virt_state.suppress_scroll_render = true;
						self.$kanban_cards.scrollTop(scroll_top);
					} else {
						virt_state.virt_start = Math.max(0, virt_state.virt_start - evicted_count);
						virt_state.virt_end = Math.max(
							virt_state.virt_start,
							virt_state.virt_end - evicted_count
						);
						const scroll_top = Math.max(
							0,
							(self.$kanban_cards.scrollTop() || 0) - evicted_count * card_height
						);
						virt_state.suppress_scroll_render = true;
						self.$kanban_cards.scrollTop(scroll_top);
					}
					requestAnimationFrame(() => {
						virt_state.suppress_scroll_render = false;
					});
				},
				/** How many cards below the screen can be removed from memory safely. */
				get_safe_evict_from_bottom(max_evict) {
					if (!max_evict) return 0;
					const buffer = virt_state.buffer_cards;
					const below_viewport = Math.max(
						0,
						virt_state.total_cards - virt_state.virt_end - buffer
					);
					return Math.min(max_evict, below_viewport);
				},
				set_indicator(indicator) {
					apply_column_indicator(self.$kanban_column, indicator);
				},
				/** Update card order in memory during drag. */
				sync_order(names) {
					virt_state.ordered_names = names;
					virt_state.total_cards = names.length;
					column.order = JSON.stringify(names);
					update_column_count(names.length);
					// Keep sortable index helpers accurate while drag defers re-render.
					if (virt_state.virtualization_disabled) {
						self.$kanban_cards.data({
							"virt-start": virt_state.virt_start || 0,
							"virt-end": virt_state.virt_end || names.length,
							virtualized: names.length >= virt_state.min_cards_to_virtualize,
						});
					}
				},
				/** Redraw column after another user/tab changed card order. */
				apply_realtime_sync(names) {
					if (names_array_equal(names, virt_state.ordered_names)) {
						return;
					}
					virt_state.ordered_names = names;
					virt_state.total_cards = names.length;
					update_column_count(names.length);
					if (virt_state.virtualization_disabled) {
						return;
					}
					virt_state.virt_start = -1;
					virt_state.virt_end = -1;
					render_virtual_cards(true);
				},
				/** Scroll so the dropped card is visible after drag-and-drop. */
				scroll_to_card_index(card_index) {
					if (card_index == null || card_index < 0) return;
					if (!should_virtualize()) return;

					const card_height = virt_state.card_height || 108;
					const buffer = virt_state.buffer_cards;
					virt_state.virt_start = -1;
					virt_state.virt_end = -1;
					self.$kanban_cards.scrollTop(Math.max(0, (card_index - buffer) * card_height));
					render_virtual_cards(true);
				},
			};
		}

		function update_column_count(count) {
			const total = store.cur_list?.get_column_total_count?.(column.title);
			self.$kanban_column?.find(".kanban-column-count").text(total || count);
		}

		function make_dom() {
			self.$kanban_column = $(
				frappe.render_template("kanban_column", {
					title: column.title,
					doctype: store.doctype,
					indicator: frappe.scrub(column.indicator, "-"),
				})
			).appendTo(wrapper);
			// add task, archive
			self.$kanban_cards = self.$kanban_column.find(".kanban-cards");
		}

		function init_virtualization() {
			if (!virt_state.scroll_listener_attached) {
				self.$kanban_cards.on("scroll", function () {
					if (virt_state.suppress_scroll_render) return;
					if (virt_state.scroll_raf_pending) return;
					virt_state.scroll_raf_pending = true;
					requestAnimationFrame(function () {
						virt_state.scroll_raf_pending = false;
						render_virtual_cards();
					});
				});

				virt_state.scroll_listener_attached = true;
			}
		}

		/** Use virtual scrolling only when the column has 30+ cards. */
		function should_virtualize() {
			return (
				!virt_state.virtualization_disabled &&
				!virt_state.has_variable_height_cards &&
				virt_state.total_cards >= virt_state.min_cards_to_virtualize
			);
		}

		function measure_card_height() {
			const $cards = self.$kanban_cards.children(".kanban-card-wrapper");
			if (!$cards.length) return;

			const sample_size = Math.min(8, $cards.length);
			let min_height = Infinity;
			let max_height = 0;
			let total_height = 0;
			let measured_count = 0;

			$cards.each(function (index) {
				if (index >= sample_size) return false;
				const height = Math.round($(this).outerHeight(true) || 0);
				if (!height) return;
				min_height = Math.min(min_height, height);
				max_height = Math.max(max_height, height);
				total_height += height;
				measured_count++;
			});

			if (!measured_count) return;

			virt_state.card_height = Math.max(1, Math.round(total_height / measured_count));
			virt_state.has_variable_height_cards =
				measured_count > 1 &&
				max_height - min_height > virt_state.variable_height_threshold;
		}

		function append_kanban_card(name) {
			const card = get_prepared_card(name, store);
			if (!card) return;
			try {
				frappe.views.KanbanBoardCard(card, self.$kanban_cards);
			} catch (e) {
				console.error("Kanban card render failed", e);
			}
		}

		function render_all_cards() {
			self.$kanban_cards.empty();
			virt_state.ordered_names.forEach(append_kanban_card);
			measure_card_height();
		}

		function get_store_column() {
			return store.columns.find((c) => c.title === column.title) || column;
		}

		function make_cards() {
			const cards_index = store.cards_index;
			const current_column = get_store_column();
			filtered_cards = cards_index?.by_column[current_column.title] || [];
			virt_state.ordered_names = get_ordered_names(current_column, cards_index);
			virt_state.total_cards = virt_state.ordered_names.length;
			virt_state.has_variable_height_cards = false;
			update_column_count(virt_state.total_cards);

			// Force render when card data changes (not only on scroll).
			render_virtual_cards(true);
		}

		/** Draw only the cards visible on screen (+ spacers + load more on scroll).

		On scroll:
		  1. Work out which card indexes are visible (virt_start to virt_end).
		  2. Draw those cards; use empty spacers for the rest.
		  3. Ask KanbanView to load more data if user is near the top or bottom.

		force=true means data changed — redraw but do not trigger a new server load.
		*/
		function render_virtual_cards(force) {
			if (virt_state.virtualization_disabled) return;

			const scroll_top = self.$kanban_cards.scrollTop() || 0;
			const container_height =
				self.$kanban_cards.innerHeight() || self.$kanban_cards.height() || 400;

			measure_card_height();

			if (!should_virtualize()) {
				if (
					!force &&
					self.$kanban_cards.children(".kanban-card-wrapper").length ===
						virt_state.total_cards
				) {
					return;
				}
				virt_state.suppress_scroll_render = true;
				render_all_cards();
				self.$kanban_cards.scrollTop(scroll_top);
				virt_state.virt_start = 0;
				virt_state.virt_end = virt_state.total_cards;
				self.$kanban_cards.data({
					"virt-start": 0,
					"virt-end": virt_state.total_cards,
					virtualized: false,
				});
				requestAnimationFrame(() => {
					virt_state.suppress_scroll_render = false;
				});
				return;
			}

			const card_height = virt_state.card_height;
			const buffer = virt_state.buffer_cards;

			let virt_start = Math.max(0, Math.floor(scroll_top / card_height) - buffer);
			let virt_end = Math.min(
				virt_state.total_cards,
				Math.ceil((scroll_top + container_height) / card_height) + buffer
			);

			if (virt_end <= virt_start) {
				virt_end = Math.min(
					virt_state.total_cards,
					virt_start + Math.ceil(container_height / card_height) + buffer
				);
			}

			if (
				!force &&
				virt_start === virt_state.virt_start &&
				virt_end === virt_state.virt_end
			) {
				return;
			}

			virt_state.virt_start = virt_start;
			virt_state.virt_end = virt_end;

			const top_spacer_height = virt_start * card_height;
			const bottom_spacer_height = (virt_state.total_cards - virt_end) * card_height;

			virt_state.suppress_scroll_render = true;
			self.$kanban_cards.empty();

			if (top_spacer_height > 0) {
				self.$kanban_cards.append(
					$(
						`<div class="kanban-virtual-spacer" style="height: ${top_spacer_height}px;"></div>`
					)
				);
			}

			for (let i = virt_start; i < virt_end; i++) {
				append_kanban_card(virt_state.ordered_names[i]);
			}

			if (bottom_spacer_height > 0) {
				self.$kanban_cards.append(
					$(
						`<div class="kanban-virtual-spacer" style="height: ${bottom_spacer_height}px;"></div>`
					)
				);
			}

			measure_card_height();
			self.$kanban_cards.data({
				"virt-start": virt_state.virt_start,
				"virt-end": virt_state.virt_end,
				virtualized: true,
			});
			self.$kanban_cards.scrollTop(scroll_top);
			// Only prefetch when user scrolls — not when we redraw after data changes.
			if (!force) {
				maybe_prefetch_more();
				maybe_prefetch_backward();
			}
			requestAnimationFrame(() => {
				virt_state.suppress_scroll_render = false;
			});
		}

		/** Ask server for the next page when user is near the bottom. */
		function maybe_prefetch_more() {
			const list = store.cur_list;
			if (!list?.prefetch_kanban_column) return;
			if (!list.can_prefetch_column_forward?.(column.title)) return;

			const trigger = list.get_prefetch_trigger_distance?.() ?? 25;
			const near_render_end = virt_state.total_cards - virt_state.virt_end <= trigger;

			if (near_render_end) {
				list.prefetch_kanban_column(column.title);
			}
		}

		/** Ask server for older cards when user scrolls near the top. */
		function maybe_prefetch_backward() {
			const list = store.cur_list;
			if (!list?.prefetch_kanban_column_back) return;

			const col_state = list.kanban_column_state?.[column.title];
			if (!col_state || col_state.inflight || col_state.window_start <= 0) return;

			const trigger = list.get_prefetch_trigger_distance?.() ?? 25;
			if (virt_state.virt_start <= trigger) {
				list.prefetch_kanban_column_back(column.title);
			}
		}

		function setup_sortable() {
			// Block card dragging/record editing without 'write' access to reference doctype
			if (!frappe.model.can_write(store.doctype)) return;

			// Drag with only part of the column on screen:
			// - onStart: stop redrawing while dragging.
			// - onEnd: convert screen position to full column index, save order, redraw columns.
			Sortable.create(self.$kanban_cards.get(0), {
				group: "cards",
				animation: 150,
				dataIdAttr: "data-name",
				filter: ".kanban-virtual-spacer",
				onStart: function () {
					virt_state.virtualization_disabled = true;
					capture_all_drag_list_offsets();
					const list = store.cur_list;
					if (list) {
						list.kanban_drag_in_progress = true;
					}
				},
				onEnd: function (e) {
					const $from = $(e.from);
					const $to = $(e.to);
					const from_colname = $from.parents(".kanban-column").attr("data-column-value");
					const to_colname = $to.parents(".kanban-column").attr("data-column-value");
					const card_name = decodeURIComponent($(e.item).attr("data-name"));
					// Target column keeps virtualizing during drag; recompute offset at drop.
					refresh_drag_list_offsets_for($from);
					refresh_drag_list_offsets_for($to);
					const old_index = get_sortable_full_index($from, e.oldIndex);
					const new_index = get_sortable_full_index($to, e.newIndex);

					const enable_virtualization = function () {
						virt_state.virtualization_disabled = false;
						clear_drag_list_offsets();
						const list = store.cur_list;
						if (list) {
							list.kanban_drag_in_progress = false;
						}
					};

					if (from_colname === to_colname && old_index === new_index) {
						enable_virtualization();
						return;
					}

					const move = {
						name: card_name,
						from_colname,
						to_colname,
						old_index,
						new_index,
						optimistic: true,
						$from,
						$to,
					};
					const snapshot = capture_drag_snapshot();
					const cur_list = store.cur_list;

					suppress_cards_watch = true;
					if (cur_list) {
						cur_list.disable_list_update = true;
						// Scope realtime suppression to this drag request lifecycle.
						cur_list.begin_kanban_local_drag_sync?.();
					}

					// Keep virtual scrolling off until drag is saved.
					const orders = apply_card_move(move);
					move.from_order = orders.from_order;
					move.to_order = orders.to_order;

					// Wrapped in a native promise (as vuex dispatch did): the deferred's
					// .done/.fail/.always are intentionally not exposed to the handlers below.
					const request = Promise.resolve(store.update_order_for_single_card(move));
					const affected_columns =
						from_colname === to_colname ? [from_colname] : [from_colname, to_colname];

					const reset_drag_controls = function () {
						suppress_cards_watch = false;
						if (cur_list) {
							cur_list.disable_list_update = false;
							// Re-enable realtime only when local drag save has fully settled.
							cur_list.end_kanban_local_drag_sync?.();
						}
						enable_virtualization();
					};

					const refresh_affected_columns = function () {
						// Watch was suppressed during drag — redraw columns after save or rollback.
						affected_columns.forEach((col) => column_registry[col]?.refresh(true));
					};

					if (request && request.done) {
						request.done(function () {
							if (cur_list) {
								cur_list.sync_column_order_after_drag?.(
									from_colname,
									move.from_order
								);
								if (from_colname !== to_colname) {
									cur_list.sync_column_order_after_drag?.(
										to_colname,
										move.to_order
									);
									cur_list.on_kanban_card_moved?.(
										card_name,
										from_colname,
										to_colname,
										old_index,
										new_index
									);
								}
							}
							column_registry[to_colname]?.scroll_to_card_index?.(new_index);
						});
					}
					if (request && request.fail) {
						request.fail(function () {
							restore_drag_snapshot(snapshot, move);
						});
					}
					if (request && request.always) {
						request.always(function () {
							reset_drag_controls();
							refresh_affected_columns();
						});
					} else {
						reset_drag_controls();
						refresh_affected_columns();
					}
				},
			});
		}

		function bind_add_card() {
			var $wrapper = self.$kanban_column;
			var $btn_add = $wrapper.find(".add-card");
			var $new_card_area = $wrapper.find(".new-card-area");

			if (!frappe.model.can_create(store.doctype)) {
				// Block record/card creation without 'create' access to reference doctype
				$btn_add.remove();
				$new_card_area.remove();
				return;
			}

			var $textarea = $new_card_area.find("textarea");

			//Add card button
			$new_card_area.hide();
			$btn_add.on("click", function () {
				$btn_add.hide();
				$new_card_area.show();
				$textarea.focus();
			});

			//save on enter
			$new_card_area.keydown(function (e) {
				if (e.which == 13) {
					e.preventDefault();
					if (!frappe.request.ajax_count) {
						// not already working -- double entry
						e.preventDefault();
						var card_title = $textarea.val();
						$new_card_area.hide();
						$textarea.val("");
						// add_card returns undefined on the quick-entry path, so
						// normalize to a promise (as vuex dispatch did).
						Promise.resolve(
							store.add_card({
								card_title,
								column_title: column.title,
							})
						).then(() => {
							$btn_add.show();
						});
					}
				}
			});

			// on textarea blur
			$textarea.on("blur", function () {
				$(this).val("");
				$btn_add.show();
				$new_card_area.hide();
			});
		}

		function bind_options() {
			if (!board_perms.write) {
				// If no write access to board, column options should be hidden
				self.$kanban_column.find(".column-options").remove();
				return;
			}

			self.$kanban_column
				.find(".column-options .dropdown-menu")
				.on("click", "[data-action]", function () {
					var $btn = $(this);
					var action = $btn.data().action;

					if (action === "archive") {
						store.archive_column(column);
					} else if (action === "indicator") {
						var color = $btn.data().indicator;
						store.set_indicator({ column, color });
					}
				});

			get_column_indicators(function (indicators) {
				let html = `<li class="button-group">${indicators
					.map((indicator) => {
						let classname = frappe.scrub(indicator, "-");
						return `<div data-action="indicator" data-indicator="${indicator}" class="btn btn-default btn-xs indicator-pill ${classname}"></div>`;
					})
					.join("")}</li>`;
				self.$kanban_column.find(".column-options .dropdown-menu").append(html);
			});
		}

		init();

		return self;
	};

	const FIELD_TYPE_ICONS = {
		Data: "type",
		"Small Text": "text-align-start",
		Text: "text-align-start",
		"Long Text": "text-align-start",
		"Text Editor": "text-align-start",
		Code: "code",
		Link: "link",
		"Dynamic Link": "link",
		Select: "list",
		Date: "calendar",
		Datetime: "calendar-clock",
		Time: "clock",
		Currency: "banknote",
		Float: "hash",
		Int: "hash",
		Percent: "percent",
		Check: "square-check",
		Phone: "phone",
		Rating: "star",
		Color: "palette",
		Duration: "timer",
		Attach: "paperclip",
		"Attach Image": "image",
		Geolocation: "map-pin",
	};

	function get_field_icon(field) {
		if (field.fieldtype === "Data" && field.options === "Email") return "mail";
		if (field.fieldtype === "Data" && field.options === "Phone") return "phone";
		return FIELD_TYPE_ICONS[field.fieldtype] || "info";
	}

	frappe.views.KanbanBoardCard = function (card, wrapper) {
		var self = {};

		function init() {
			if (!card) return;
			make_dom();
			render_card_meta();
		}

		function make_dom() {
			const title = frappe.utils.escape_html(frappe.utils.html2text(card.title));
			const image_url = cur_list.get_image_url(card);
			var opts = {
				name: card.name,
				title: title,
				disable_click: card._disable_click ? "disable-click" : "",
				creation: card.creation,
				doc_content: get_doc_content(card),
				avatar_html: image_url
					? frappe.ui.avatar.html({
							label: title,
							image: image_url,
							size: "lg",
							shape: "square",
					  })
					: "",
				form_link: frappe.utils.get_form_link(card.doctype, card.name),
			};

			self.$card = $(frappe.render_template("kanban_card", opts)).appendTo(wrapper);

			if (!frappe.model.can_write(card.doctype)) {
				// Undraggable card without 'write' access to reference doctype
				self.$card.find(".kanban-card-body").css("cursor", "default");
			}
		}

		function get_doc_content(card) {
			let fields = [];
			const show_labels = get_kanban_board_show_labels();
			const field_names = get_kanban_board_fields();
			for (let field_name of field_names) {
				const fieldname =
					typeof field_name === "string" ? field_name : field_name?.fieldname;
				if (!fieldname) continue;
				let field =
					frappe.meta.docfield_map[card.doctype]?.[fieldname] ||
					frappe.model.get_std_field(fieldname);
				if (!field) continue;

				let raw = card.doc[fieldname];
				if (field.fieldtype === "Data") {
					raw = frappe.utils.escape_html(raw);
				}
				let value =
					raw === null || raw === undefined || raw === ""
						? ""
						: frappe.format(raw, field);
				if (value === "" || value == null) value = "-";

				if (show_labels) {
					fields.push(`
						<div class="kanban-doc-field truncate text-muted">
							<span>${__(field.label, null, field.parent)}: </span>
							<span>${value}</span>
						</div>
					`);
				} else {
					const label = frappe.utils.escape_html(__(field.label, null, field.parent));
					const icon = frappe.utils.icon(get_field_icon(field), "sm");
					fields.push(`
						<div class="kanban-doc-field flex items-center text-muted">
							<span class="kanban-doc-icon shrink-0" title="${label}">${icon}</span>
							<span class="truncate">${value}</span>
						</div>
					`);
				}
			}

			return fields.join("");
		}

		function get_tags_html(card) {
			if (!card.tags) return "";
			const tags_array = card.tags.split(",");
			const limit = 3; // cap. at 3 tags
			const visible_tags = tags_array.slice(0, limit).join(",");
			const hidden_tags = tags_array.slice(limit).join(",");
			const hidden_tags_html = cur_list.get_tags_html(hidden_tags, null, true);
			const hidden_count = tags_array.length - limit;
			let html = `<div class="kanban-tags">
				${cur_list.get_tags_html(visible_tags, null, true)}`;

			if (hidden_count > 0) {
				html += `
					<span class="tag-pill more-tags">
						+${hidden_count}
						<span class="hidden-tags">${hidden_tags_html}</span>
					</span>`;
			}

			html += `</div>`;
			return html;
		}

		function render_card_meta() {
			let html = get_tags_html(card);

			if (card.comment_count > 0)
				html += `<span class="list-comment-count small text-muted ">
					${frappe.utils.icon("message-circle")}
					${card.comment_count}
				</span>`;

			const $assignees_group = get_assignees_group();

			html += `
				<span class="kanban-assignments"></span>
				${cur_list.get_like_html(card)}
			`;

			if (card.color && frappe.ui.color.validate_hex(card.color)) {
				// Left accent border — does not change card height (unlike a bar).
				self.$card
					.find(".kanban-card")
					.addClass("has-color")
					.css("--kanban-card-accent", card.color);
			}

			self.$card
				.find(".kanban-card-meta")
				.empty()
				.append(html)
				.find(".kanban-assignments")
				.append($assignees_group);
		}

		function get_assignees_group() {
			return frappe.avatar_group(card.assigned_list, 3, {
				css_class: "avatar avatar-small",
				action_icon: "plus",
				action: show_assign_to_dialog,
			});
		}

		function show_assign_to_dialog(e) {
			e.preventDefault();
			e.stopPropagation();
			self.assign_to = new frappe.ui.form.AssignToDialog({
				obj: self,
				method: "frappe.desk.form.assign_to.add",
				doctype: card.doctype,
				docname: card.name,
				callback: function () {
					const users = self.assign_to_dialog.get_values().assign_to;
					card.assigned_list = [...new Set(card.assigned_list.concat(users))];
					store.update_card(card);
				},
			});
			self.assign_to_dialog = self.assign_to.dialog;
			self.assign_to_dialog.show();
		}

		init();
	};

	function prepare_card(card, state, doc) {
		var assigned_list = card._assign ? JSON.parse(card._assign) : [];
		var comment_count = card._comment_count || 0;

		if (doc) {
			card = Object.assign({}, card, doc);
		}

		return {
			doctype: state.doctype,
			name: card.name,
			title: card[state.card_meta.title_field.fieldname],
			creation: moment(card.creation).format("MMM DD, YYYY"),
			_liked_by: card._liked_by,
			image: card[cur_list.meta.image_field],
			tags: card._user_tags,
			column: card[state.board.field_name],
			assigned_list: card.assigned_list || assigned_list,
			comment_count: card.comment_count || comment_count,
			color: card.color || null,
			doc: doc || card,
		};
	}

	function prepare_columns(columns) {
		return columns.map(function (col) {
			return {
				title: col.column_name,
				status: col.status,
				order: col.order,
				indicator: col.indicator || "gray",
			};
		});
	}

	function modify_column_field_in_c11n(doc, board, title, action) {
		doc.fields.forEach(function (df) {
			if (df.fieldname === board.field_name && df.fieldtype === "Select") {
				if (!df.options) df.options = "";

				if (action === "add") {
					//add column_name to Select field's option field
					if (!df.options.includes(title)) df.options += "\n" + title;
				} else if (action === "delete") {
					var options = df.options.split("\n");
					var index = options.indexOf(title);
					if (index !== -1) options.splice(index, 1);
					df.options = options.join("\n");
				}
			}
		});
		return doc;
	}

	function fetch_customization(doctype) {
		return new Promise(function (resolve) {
			frappe.model.with_doc("Customize Form", "Customize Form", function () {
				var doc = frappe.get_doc("Customize Form");
				doc.doc_type = doctype;
				frappe.call({
					doc: doc,
					method: "fetch_to_customize",
					callback: function (r) {
						resolve(r.docs[0]);
					},
				});
			});
		});
	}

	function save_customization(doc) {
		if (!doc) return;
		doc.hide_success = true;
		return frappe.call({
			doc: doc,
			method: "save_customization",
		});
	}

	function insert_doc(doc) {
		return frappe.call({
			method: "frappe.client.insert",
			args: {
				doc: doc,
			},
			callback: function () {
				frappe.model.clear_doc(doc.doctype, doc.name);
				frappe.show_alert({ message: __("Saved"), indicator: "green" }, 1);
			},
		});
	}

	function update_kanban_board(board_name, column_title, action) {
		var method;
		var args = {
			board_name: board_name,
			column_title: column_title,
		};
		if (action === "add") {
			method = "add_column";
		} else if (action === "archive" || action === "restore") {
			method = "archive_restore_column";
			args.status = action === "archive" ? "Archived" : "Active";
		}
		return frappe.call({
			method: method_prefix + method,
			args: args,
		});
	}

	function get_kanban_list() {
		return store.cur_list || (typeof cur_list !== "undefined" ? cur_list : null);
	}

	/** Parsed Kanban Board fields config (always an array). */
	function get_kanban_board_fields(board) {
		const list = get_kanban_list();
		const source = board || list?.board || store.board;
		let fields = source?.fields;
		if (Array.isArray(fields)) return fields;
		if (typeof fields === "string") {
			try {
				fields = JSON.parse(fields || "[]");
			} catch (e) {
				return [];
			}
			return Array.isArray(fields) ? fields : [];
		}
		return [];
	}

	function get_kanban_board_show_labels(board) {
		const list = get_kanban_list();
		const source = board || list?.board || store.board;
		return !!source?.show_labels;
	}

	function is_active_column(col) {
		return col.status !== "Archived";
	}

	/** Update column dot indicator without rebuilding cards. */
	function apply_column_indicator($column, indicator) {
		if (!$column?.length) return;
		const theme = frappe.scrub(indicator || "gray", "-");
		const $dot = $column.find(".kanban-col-dot");
		$dot.attr("class", `kanban-col-dot indicator ${theme}`);
	}

	/** Align card column fields with saved board column order (mutates cards in place). */
	function reconcile_cards_with_board_orders(cards, columns, field_name) {
		if (!cards?.length) return cards || [];

		const by_name = {};
		for (let i = 0; i < cards.length; i++) {
			by_name[cards[i].name] = cards[i];
		}

		for (let c = 0; c < columns.length; c++) {
			const order = parse_column_order(columns[c]);
			for (let i = 0; i < order.length; i++) {
				const card = by_name[order[i]];
				if (card && card[field_name] !== columns[c].title) {
					card[field_name] = columns[c].title;
					delete prepared_card_cache[order[i]];
				}
			}
		}

		return cards;
	}

	function names_array_equal(a, b) {
		if (!a || !b || a.length !== b.length) return false;
		for (let i = 0; i < a.length; i++) {
			if (a[i] !== b[i]) return false;
		}
		return true;
	}

	/** Columns whose saved order or card membership changed since last sync. */
	function get_columns_needing_refresh(
		old_columns,
		new_columns,
		old_index,
		new_index,
		field_name
	) {
		const to_refresh = new Set();

		for (let i = 0; i < old_columns.length; i++) {
			const old_col = old_columns[i];
			if (!is_active_column(old_col)) continue;
			const new_col = new_columns.find((c) => c.title === old_col.title);
			if (!new_col) continue;
			if (!names_array_equal(parse_column_order(old_col), parse_column_order(new_col))) {
				to_refresh.add(old_col.title);
			}
		}

		if (old_index?.by_name) {
			const old_names = old_index.by_name;
			const new_names = new_index?.by_name || {};
			for (const name in old_names) {
				const old_col = get_card_column(old_names[name], field_name);
				const new_card = new_names[name];
				const new_col = new_card ? get_card_column(new_card, field_name) : null;
				if (old_col !== new_col) {
					if (old_col) to_refresh.add(old_col);
					if (new_col) to_refresh.add(new_col);
				}
			}
			for (const name in new_names) {
				if (!old_names[name]) {
					const col = get_card_column(new_names[name], field_name);
					if (col) to_refresh.add(col);
				}
			}
		}

		return to_refresh;
	}

	function clear_prepared_card_cache() {
		prepared_card_cache = {};
	}

	function clear_column_registry() {
		Object.keys(column_registry).forEach((key) => delete column_registry[key]);
	}

	function get_kanban_column_title($kanban_cards) {
		return $kanban_cards?.parents(".kanban-column").attr("data-column-value");
	}

	function capture_all_drag_list_offsets() {
		drag_list_offsets = {};
		for (const column_title in column_registry) {
			const offset = column_registry[column_title]?.get_dom_list_offset?.();
			if (offset != null) {
				drag_list_offsets[column_title] = offset;
			}
		}
	}

	function clear_drag_list_offsets() {
		drag_list_offsets = null;
	}

	/** Live offset from DOM; ignores drag-start snapshot (target column may scroll during drag). */
	function get_column_dom_list_offset_live($kanban_cards) {
		const window_start = get_column_list_window_start($kanban_cards);
		if (!$kanban_cards?.data("virtualized")) {
			return window_start;
		}
		return window_start + ($kanban_cards.data("virt-start") || 0);
	}

	function refresh_drag_list_offsets_for($kanban_cards) {
		if (!drag_list_offsets || !$kanban_cards?.length) return;
		const column_title = get_kanban_column_title($kanban_cards);
		if (column_title) {
			drag_list_offsets[column_title] = get_column_dom_list_offset_live($kanban_cards);
		}
	}

	function get_column_list_window_start($kanban_cards) {
		const column_title = get_kanban_column_title($kanban_cards);
		return store.cur_list?.kanban_column_state?.[column_title]?.window_start || 0;
	}

	/** Map visible DOM cards to indexes in the full saved column order. */
	function get_column_dom_list_offset($kanban_cards) {
		const column_title = get_kanban_column_title($kanban_cards);
		if (drag_list_offsets && column_title && drag_list_offsets[column_title] != null) {
			return drag_list_offsets[column_title];
		}
		const window_start = get_column_list_window_start($kanban_cards);
		if (!$kanban_cards?.data("virtualized")) {
			return window_start;
		}
		return window_start + ($kanban_cards.data("virt-start") || 0);
	}

	/** Convert drag position on screen to position in the full column list.

	Only some cards are on screen; add virt_start and account for the top spacer.
	*/
	function get_sortable_full_index($kanban_cards, dom_index) {
		if (!$kanban_cards?.length) return dom_index;
		const has_top_spacer = $kanban_cards.children().first().hasClass("kanban-virtual-spacer");
		const dom_offset = Math.max(0, dom_index - (has_top_spacer ? 1 : 0));
		return get_column_dom_list_offset($kanban_cards) + dom_offset;
	}

	/** Card names currently shown on screen (ignores spacers). */
	function get_dom_card_names($kanban_cards) {
		const names = [];
		if (!$kanban_cards?.length) return names;
		$kanban_cards.children().each(function () {
			const $child = $(this);
			if ($child.hasClass("kanban-virtual-spacer")) return;
			const raw = $child.attr("data-name");
			if (raw) names.push(decodeURIComponent(raw));
		});
		return names;
	}

	/** After drag, merge on-screen order back into the full column list. */
	function rebuild_column_order_from_dom($kanban_cards, full_order) {
		const dom_names = get_dom_card_names($kanban_cards);
		if (!dom_names.length) return full_order.slice();

		if (!$kanban_cards.data("virtualized") && dom_names.length >= full_order.length) {
			return dom_names;
		}

		return patch_full_order_from_dom($kanban_cards, full_order, dom_names);
	}

	function patch_full_order_from_dom($kanban_cards, full_order, dom_names) {
		const patch_start = get_column_dom_list_offset($kanban_cards);
		const result = full_order.slice();
		for (let i = 0; i < dom_names.length; i++) {
			const idx = patch_start + i;
			if (idx < result.length) {
				result[idx] = dom_names[i];
			} else {
				result.push(dom_names[i]);
			}
		}
		return result;
	}

	/** Destination column order after a cross-column drop (card may not be in saved order yet). */
	function order_after_cross_column_drop($kanban_cards, full_order, card_name) {
		const dom_names = get_dom_card_names($kanban_cards);
		if (!dom_names.length) return full_order.filter((n) => n !== card_name);

		const insert_idx_in_dom = dom_names.indexOf(card_name);
		if (insert_idx_in_dom === -1) {
			return full_order.filter((n) => n !== card_name);
		}

		const without = full_order.filter((n) => n !== card_name);
		const full_insert_idx = get_column_dom_list_offset($kanban_cards) + insert_idx_in_dom;
		without.splice(Math.min(full_insert_idx, without.length), 0, card_name);
		return without;
	}

	function parse_column_order(column) {
		if (!column?.order) return [];
		try {
			const order =
				typeof column.order === "string" ? JSON.parse(column.order) : column.order;
			return Array.isArray(order) ? order : [];
		} catch (e) {
			return [];
		}
	}

	/** Full column order for drag/save — saved order plus loaded cards not in it yet.
	 * Deduplicated so a corrupt saved order (same card listed twice) is never
	 * re-persisted or rendered twice. */
	function get_column_full_order(column, cards_index) {
		const saved = parse_column_order(column);
		const column_cards = cards_index?.by_column[column.title] || [];

		if (!saved.length) {
			return column_cards.map((card) => card.name);
		}

		const seen = new Set();
		const ordered_names = [];
		for (let i = 0; i < saved.length; i++) {
			if (!seen.has(saved[i])) {
				seen.add(saved[i]);
				ordered_names.push(saved[i]);
			}
		}
		for (let i = 0; i < column_cards.length; i++) {
			if (!seen.has(column_cards[i].name)) {
				seen.add(column_cards[i].name);
				ordered_names.push(column_cards[i].name);
			}
		}
		return ordered_names;
	}

	/** Column card order for display / sync — saved order first, then cards missing
	 * from it. Deduplicated so a duplicated saved order never renders a card twice. */
	function get_column_display_order(column, cards_index) {
		const column_cards = cards_index?.by_column[column.title] || [];
		if (!column_cards.length) return [];

		const saved = parse_column_order(column);
		if (!saved.length) return column_cards.map((card) => card.name);

		const names_in_column = new Set(column_cards.map((card) => card.name));
		const seen = new Set();
		const ordered_names = [];

		for (let i = 0; i < saved.length; i++) {
			if (names_in_column.has(saved[i]) && !seen.has(saved[i])) {
				seen.add(saved[i]);
				ordered_names.push(saved[i]);
			}
		}
		for (let i = 0; i < column_cards.length; i++) {
			if (!seen.has(column_cards[i].name)) {
				seen.add(column_cards[i].name);
				ordered_names.push(column_cards[i].name);
			}
		}
		return ordered_names;
	}

	function clone_cards_state(cards) {
		return cards.map((card) => ({ ...card }));
	}

	function capture_drag_snapshot() {
		return {
			cards: clone_cards_state(store.cards),
			columns: store.columns.map((c) => ({ ...c, order: c.order })),
		};
	}

	function restore_drag_snapshot(snapshot, move) {
		suppress_cards_watch = true;
		store.update_state({
			cards: snapshot.cards,
			columns: snapshot.columns,
		});
		column_registry[move.from_colname]?.refresh(true);
		if (move.from_colname !== move.to_colname) {
			column_registry[move.to_colname]?.refresh(true);
		}
		suppress_cards_watch = false;
	}

	/** Update card order in memory right after drag (before server saves). */
	function apply_card_move({ name, from_colname, to_colname, $from, $to }) {
		const state = store;
		const field_name = state.board.field_name;
		const columns = state.columns.map((c) => ({ ...c, order: c.order }));
		const from_column = columns.find((c) => c.title === from_colname);
		const to_column = columns.find((c) => c.title === to_colname);
		if (!from_column || !to_column) return { from_order: [], to_order: [] };

		const from_before = get_column_full_order(from_column, state.cards_index);
		const to_before = get_column_full_order(to_column, state.cards_index);
		let from_names;
		let to_names;

		if (from_colname === to_colname) {
			from_names = rebuild_column_order_from_dom($to, from_before);
			to_names = from_names;
			from_column.order = JSON.stringify(from_names);
			column_registry[from_colname]?.sync_order(from_names);
		} else {
			const card = state.cards_index?.by_name[name];
			if (card) {
				card[field_name] = to_colname;
				delete prepared_card_cache[name];
			}
			from_names = rebuild_column_order_from_dom($from, from_before).filter(
				(n) => n !== name
			);
			to_names = order_after_cross_column_drop($to, to_before, name);
			from_column.order = JSON.stringify(from_names);
			to_column.order = JSON.stringify(to_names);
			column_registry[from_colname]?.sync_order(from_names);
			column_registry[to_colname]?.sync_order(to_names);
		}

		store.update_state({ cards: state.cards, columns });
		return { from_order: from_names, to_order: to_names };
	}

	/** Build card HTML only when it is drawn on screen; reuse if seen before. */
	function get_prepared_card(name, state) {
		if (prepared_card_cache[name]) {
			return prepared_card_cache[name];
		}
		const raw = state.cards_index?.by_name[name];
		if (!raw) return null;
		const prepared = prepare_card(raw, state);
		prepared_card_cache[name] = prepared;
		return prepared;
	}

	function get_card_column(card, field_name) {
		return card.column || card[field_name];
	}

	/** Group cards by column and name once — faster than filtering on every scroll. */
	function build_cards_index(cards, field_name) {
		const by_column = {};
		const by_name = {};
		for (let i = 0; i < cards.length; i++) {
			const card = cards[i];
			const col = get_card_column(card, field_name);
			if (!by_column[col]) by_column[col] = [];
			by_column[col].push(card);
			by_name[card.name] = card;
		}
		return { by_column, by_name };
	}

	/** Ordered card names for a column using the pre-built index. */
	function get_ordered_names(column, cards_index) {
		return get_column_display_order(column, cards_index);
	}

	function update_cards_column(updated_cards) {
		var cards = store.cards;
		const field_name = store.board?.field_name;
		cards.forEach(function (c) {
			updated_cards.forEach(function (uc) {
				if (uc.name === c.name) {
					c.column = uc.column;
					if (field_name) c[field_name] = uc.column;
					delete prepared_card_cache[c.name];
				}
			});
		});
		return cards;
	}

	var column_indicators_cache = null;
	var column_indicators_promise = null;

	function get_column_indicators(callback) {
		if (column_indicators_cache) {
			callback(column_indicators_cache);
			return;
		}

		if (!column_indicators_promise) {
			column_indicators_promise = new Promise(function (resolve) {
				frappe.model.with_doctype("Kanban Board Column", function () {
					var meta = frappe.get_meta("Kanban Board Column");
					var indicators;
					meta.fields.forEach(function (df) {
						if (df.fieldname === "indicator") {
							indicators = df.options.split("\n");
						}
					});
					if (!indicators) {
						indicators = ["green", "blue", "orange", "gray"];
					}
					column_indicators_cache = indicators;
					resolve(indicators);
				});
			});
		}

		column_indicators_promise.then(callback);
	}
})();
