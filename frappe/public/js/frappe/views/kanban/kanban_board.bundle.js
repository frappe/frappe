// TODO: Refactor for better UX

import { createStore } from "vuex";

frappe.provide("frappe.views");

(function () {
	var method_prefix = "frappe.desk.doctype.kanban_board.kanban_board.";

	let columns_unwatcher = null;

	let store;
	const init_store = () => {
		store = createStore({
			state: {
				doctype: "",
				board: {},
				card_meta: {},
				cards: [],
				columns: [],
				filters_modified: false,
				cur_list: {},
				empty_state: true,
			},
			mutations: {
				update_state(state, obj) {
					Object.assign(state, obj);
				},
			},
			actions: {
				init: function (context, opts) {
					context.commit("update_state", {
						empty_state: true,
					});
					var board = opts.board;
					var card_meta = opts.card_meta;
					opts.card_meta = card_meta;
					opts.board = board;
					var cards = opts.cards.map(function (card) {
						return prepare_card(card, opts);
					});
					var columns = prepare_columns(board.columns);
					context.commit("update_state", {
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
				update_cards: function (context, cards) {
					var state = context.state;
					var _cards = cards
						.map((card) => prepare_card(card, state))
						.concat(state.cards)
						.uniqBy((card) => card.name);
	
					context.commit("update_state", {
						cards: _cards,
					});
				},
				add_column: function (context, col) {
					if (frappe.model.can_create("Custom Field")) {
						store.dispatch("update_column", { col, action: "add" });
					} else {
						frappe.msgprint({
							title: __("Not permitted"),
							message: __("You are not allowed to create columns"),
							indicator: "red",
						});
					}
				},
				archive_column: function (context, col) {
					store.dispatch("update_column", { col, action: "archive" });
				},
				restore_column: function (context, col) {
					store.dispatch("update_column", { col, action: "restore" });
				},
				update_column: function (context, { col, action }) {
					var doctype = context.state.doctype;
					var board = context.state.board;
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
								context.commit("update_state", {
									columns: prepare_columns(cols, context.state.cards),
								});
							},
							function (err) {
								console.error(err); 
							}
						);
				},
				add_card: function (context, { card_title, column_title }) {
					var state = context.state;
					var doc = frappe.model.get_new_doc(state.doctype);
					var field = state.card_meta.title_field;
					var quick_entry = state.card_meta.quick_entry;
	
					var doc_fields = {};
					doc_fields[field.fieldname] = card_title;
					doc_fields[state.board.field_name] = column_title;
					state.cur_list.filter_area.get().forEach(function (f) {
						if (f[2] !== "=") return;
						doc_fields[f[1]] = f[3];
					});
	
					$.extend(doc, doc_fields);
	
					// add the card directly
					// for better ux
					const card = prepare_card(doc, state);
					card._disable_click = true;
					const cards = [...state.cards, card];
					// remember the name which we will override later
					const old_name = doc.name;
					context.commit("update_state", { cards });
	
					if (field && !quick_entry) {
						return insert_doc(doc).then(function (r) {
							// update the card in place with the updated doc
							const updated_doc = r.message;
							const index = state.cards.findIndex((card) => card.name === old_name);
							const card = prepare_card(updated_doc, state);
							const new_cards = state.cards.slice();
							new_cards[index] = card;
							context.commit("update_state", { cards: new_cards });
							const args = {
								new: 1,
								name: card.name,
								colname: updated_doc[state.board.field_name],
							};
							store.dispatch("update_order_for_single_card", args);
						});
					} else {
						frappe.new_doc(state.doctype, doc);
					}
				},
				update_card: function (context, card) {
					var index = -1;
					context.state.cards.forEach(function (c, i) {
						if (c.name === card.name) {
							index = i;
						}
					});
					var cards = context.state.cards.slice();
					if (index !== -1) {
						cards.splice(index, 1, card);
					}
					context.commit("update_state", { cards: cards });
				},
				update_order_for_single_card: function (context, card) {
					// cache original order
					const _cards = context.state.cards.slice();
					const _columns = context.state.columns.slice();
					let args = {};
					let method_name = "";
	
					if (card.new) {
						method_name = "add_card";
						args = {
							board_name: context.state.board.name,
							docname: card.name,
							colname: card.colname,
						};
					} else {
						method_name = "update_order_for_single_card";
						args = {
							board_name: context.state.board.name,
							docname: card.name,
							from_colname: card.from_colname,
							to_colname: card.to_colname,
							old_index: card.old_index,
							new_index: card.new_index,
						};
					}
					if(args.from_colname === args.to_colname) {
						context.commit("update_state", {
							cards: _cards,
							columns: _columns,
						});
						frappe.dom.unfreeze();
						return;
					}
					frappe.dom.freeze();
					frappe
						.call({
							method: method_prefix + method_name,
							args: args,
							callback: (r) => {
								let board = r.message;
								let updated_cards = [
									{ name: card.name, column: card.to_colname || card.colname },
								];
								let cards = update_cards_column(updated_cards);
								context.commit("update_state", {
									cards: cards,
								});
								store.dispatch("update_order");
								frappe.dom.unfreeze();
							},
						})
						.fail(function () {
							// revert original order
							context.commit("update_state", {
								cards: _cards,
								columns: _columns,
							});
							frappe.dom.unfreeze();
						});
				},
				update_order: function (context) {
					// cache original order
					const _cards = context.state.cards.slice();
					const _columns = context.state.columns.slice();
	
					const order = {};
					context.state.wrapper.find(".kanban-column[data-column-value]").each(function () {
						var col_name = $(this).data().columnValue;
						order[col_name] = [];
						$(this)
							.find(".kanban-card-wrapper")
							.each(function () {
								var card_name = decodeURIComponent($(this).data().name);
								order[col_name].push(card_name);
							});
					});
	
					frappe
						.call({
							method: method_prefix + "update_order",
							args: {
								board_name: context.state.board.name,
								order: order,
							},
							callback: (r) => {
								var board = r.message[0];
								var updated_cards = r.message[1];
								var cards = update_cards_column(updated_cards);
								var columns = prepare_columns(board.columns);
								context.commit("update_state", {
									cards: cards,
									columns: columns,
								});
							},
						})
						.fail(function () {
							// revert original order
							context.commit("update_state", {
								cards: _cards,
								columns: _columns,
							});
						});
				},
				update_column_order: function (context, order) {
					return frappe
						.call({
							method: method_prefix + "update_column_order",
							args: {
								board_name: context.state.board.name,
								order: order,
							},
						})
						.then(function (r) {
							var board = r.message;
							var columns = prepare_columns(board.columns);
							context.commit("update_state", {
								columns: columns,
							});
						});
				},
				set_indicator: function (context, { column, color }) {
					return frappe
						.call({
							method: method_prefix + "set_indicator",
							args: {
								board_name: context.state.board.name,
								column_name: column.title,
								indicator: color,
							},
						})
						.then(function (r) {
							var board = r.message;
							var columns = prepare_columns(board.columns, context.state.cards);
							context.commit("update_state", {
								columns: columns,
							});
						});
				},
			},
		});
	}

	frappe.views.KanbanBoard = function (opts) {
		var self = {};
		self.wrapper = opts.wrapper;
		self.cur_list = opts.cur_list;
		self.board_name = opts.board_name;
		self.board_perms = self.cur_list.board_perms;

		self.update = function (cards) {
			// update cards internally
			opts.cards = cards;

			if (self.wrapper.find(".kanban").length > 0 && self.cur_list.start !== 0) {
				store.dispatch("update_cards", cards);
			} else {
				init();
			}
		};

		function init() {
			init_store();
			store.dispatch("init", opts);
			columns_unwatcher && columns_unwatcher();
			store.watch((state) => {
				return state.columns
			}, make_columns);
			prepare();
			make_columns();
			store.watch((state) => {
				return state.cur_list;
			}, setup_restore_columns);
			columns_unwatcher = store.watch((state) => {
				return state.columns;
			}, setup_restore_columns);
			store.watch((state) => {
				return state.empty_state;
			}, show_empty_state);

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
			self.$kanban_board.find(".kanban-column").not(".add-new-column").remove();
			var columns = store.state.columns;

			columns.filter(is_active_column).map(function (col) {
				frappe.views.KanbanBoardColumn(col, self.$kanban_board, self.board_perms);
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
					store.dispatch("update_column_order", order);
				},
			});
		}

		function bind_add_column() {
			if (!self.board_perms.write) {
				// If no write access to board, editing board (by adding column) should be blocked
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
						store.dispatch("add_column", col);
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
			var cur_list = store.state.cur_list;
			var columns = store.state.columns;
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
				store.dispatch("restore_column", col);
			});
		}

		function show_empty_state() {
			var empty_state = store.state.empty_state;

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

		function init() {
			make_dom();
			setup_sortable();
			make_cards();
			store.watch((state, getters) => {
				return state.cards;
			}, make_cards);
			bind_add_card();
			bind_options();
		}

		function make_dom() {
			self.$kanban_column = $(
				frappe.render_template("kanban_column", {
					title: column.title,
					doctype: store.state.doctype,
					indicator: frappe.scrub(column.indicator, "-"),
				})
			).appendTo(wrapper);
			// add task, archive
			self.$kanban_cards = self.$kanban_column.find(".kanban-cards");
		}

		function make_cards() {
			self.$kanban_cards.empty();
			var cards = store.state.cards;
			filtered_cards = get_cards_for_column(cards, column);
			var filtered_cards_names = filtered_cards.map((card) => card.name);

			var order = column.order;
			if (order) {
				order = JSON.parse(order);
				// new cards
				filtered_cards.forEach(function (card) {
					if (order.indexOf(card.name) === -1) {
						frappe.views.KanbanBoardCard(card, self.$kanban_cards);
					}
				});
				order.forEach(function (name) {
					if (!filtered_cards_names.includes(name)) return;
					frappe.views.KanbanBoardCard(get_card(name), self.$kanban_cards);
				});
			} else {
				filtered_cards.map(function (card) {
					frappe.views.KanbanBoardCard(card, self.$kanban_cards);
				});
			}
		}

		function setup_sortable() {
			// Block card dragging/record editing without 'write' access to reference doctype
			if (!frappe.model.can_write(store.state.doctype)) return;

			Sortable.create(self.$kanban_cards.get(0), {
				group: "cards",
				animation: 150,
				dataIdAttr: "data-name",
				forceFallback: true,
				onStart: function () {
					wrapper.find(".kanban-card.add-card").fadeOut(200, function () {
						wrapper.find(".kanban-cards").height("100vh");
					});
				},
				onEnd: function (e) {
					wrapper.find(".kanban-card.add-card").fadeIn(100);
					wrapper.find(".kanban-cards").height("auto");
					// update order
					const args = {
						name: decodeURIComponent($(e.item).attr("data-name")),
						from_colname: $(e.from)
							.parents(".kanban-column")
							.attr("data-column-value"),
						to_colname: $(e.to).parents(".kanban-column").attr("data-column-value"),
						old_index: e.oldIndex,
						new_index: e.newIndex,
					};
					store.dispatch("update_order_for_single_card", args);
				},
				onAdd: function () {},
			});
		}

		function bind_add_card() {
			var $wrapper = self.$kanban_column;
			var $btn_add = $wrapper.find(".add-card");
			var $new_card_area = $wrapper.find(".new-card-area");

			if (!frappe.model.can_create(store.state.doctype)) {
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
						store
							.dispatch("add_card", {
								card_title,
								column_title: column.title,
							})
							.then(() => {
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
						store.dispatch("archive_column", column);
					} else if (action === "indicator") {
						var color = $btn.data().indicator;
						store.dispatch("set_indicator", { column, color });
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
	};

	frappe.views.KanbanBoardCard = function (card, wrapper) {
		var self = {};

		function init() {
			if (!card) return;
			make_dom();
			render_card_meta();
		}

		function make_dom() {
			var opts = {
				name: card.name,
				title: frappe.utils.html2text(card.title),
				disable_click: card._disable_click ? "disable-click" : "",
				creation: card.creation,
				doc_content: get_doc_content(card),
				client_description: frappe.utils.html2text(card.doc.client_description),
				image_url: cur_list.get_image_url(card),
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
			const render_fields = [...cur_list.board.fields]
			if (card.column === 'Request a callback'){
				render_fields.push(...['customer','callback_date', 'callback_time'])
			}
			for (let field_name of render_fields) {
				let field =
					frappe.meta.docfield_map[card.doctype]?.[field_name] ||
					frappe.model.get_std_field(field_name);
				let label = cur_list.board.show_labels ? `<span>${__(field.label)}: </span>` : "";
				let value = frappe.format(card.doc[field_name], field);
				fields.push(`
					<div class="text-muted text-truncate">
						${label}
						<span>${value}</span>
					</div>
				`);
			}

			return fields.join("");
		}

		function get_tags_html(card) {
			return card.tags
				? `<div class="kanban-tags">
					${cur_list.get_tags_html(card.tags, 3, true)}
				</div>`
				: "";
		}

		function render_card_meta() {
			let html = `<div class="center_elements"> ${get_tags_html(card)}`;

			if (card.comment_count > 0)
				html += `<span class="list-comment-count small text-muted ">
					${frappe.utils.icon("small-message")}
					${card.comment_count}
				</span>`;


			const $assignees_group = get_assignees_group();

			html += `
				<span class="kanban-assignments"></span>
				${cur_list.get_like_html(card)}
			`;

			html += getPartsIcons()
			html += getSoftwareIcons()
			html += getLoanCarIcons()

			if (card.color && frappe.ui.color.validate_hex(card.color)) {
				const $div = $("<div>");
				$("<div></div>")
					.css({
						width: "30px",
						height: "4px",
						borderRadius: "2px",
						marginBottom: "8px",
						backgroundColor: card.color,
					})
					.appendTo($div);

				self.$card.find(".kanban-card .kanban-title-area").prepend($div);
			}
			html += '</div>'
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
				action_icon: "add",
				action: show_assign_to_dialog,
			});
		}

		function getPartsIcons(){
			let html = "";
			if(card.doc.parts_status === "Waiting for parts" || !card.doc.parts_status){
				html = '<svg xmlns="http://www.w3.org/2000/svg" height="1em" viewBox="0 0 576 512"><style>svg{fill:#d1d1d1}</style><path d="M551.991 64H129.28l-8.329-44.423C118.822 8.226 108.911 0 97.362 0H12C5.373 0 0 5.373 0 12v8c0 6.627 5.373 12 12 12h78.72l69.927 372.946C150.305 416.314 144 431.42 144 448c0 35.346 28.654 64 64 64s64-28.654 64-64a63.681 63.681 0 0 0-8.583-32h145.167a63.681 63.681 0 0 0-8.583 32c0 35.346 28.654 64 64 64 35.346 0 64-28.654 64-64 0-17.993-7.435-34.24-19.388-45.868C506.022 391.891 496.76 384 485.328 384H189.28l-12-64h331.381c11.368 0 21.177-7.976 23.496-19.105l43.331-208C578.592 77.991 567.215 64 551.991 64zM240 448c0 17.645-14.355 32-32 32s-32-14.355-32-32 14.355-32 32-32 32 14.355 32 32zm224 32c-17.645 0-32-14.355-32-32s14.355-32 32-32 32 14.355 32 32-14.355 32-32 32zm38.156-192H171.28l-36-192h406.876l-40 192z"/></svg>';
			}
			if(card.doc.parts_status === "Parts are ready for pickup"){
				html = '<svg xmlns="http://www.w3.org/2000/svg" class="blink-red" height="1em" viewBox="0 0 576 512"><style>svg{fill:#00c700}</style><path d="M551.991 64H129.28l-8.329-44.423C118.822 8.226 108.911 0 97.362 0H12C5.373 0 0 5.373 0 12v8c0 6.627 5.373 12 12 12h78.72l69.927 372.946C150.305 416.314 144 431.42 144 448c0 35.346 28.654 64 64 64s64-28.654 64-64a63.681 63.681 0 0 0-8.583-32h145.167a63.681 63.681 0 0 0-8.583 32c0 35.346 28.654 64 64 64 35.346 0 64-28.654 64-64 0-17.993-7.435-34.24-19.388-45.868C506.022 391.891 496.76 384 485.328 384H189.28l-12-64h331.381c11.368 0 21.177-7.976 23.496-19.105l43.331-208C578.592 77.991 567.215 64 551.991 64zM240 448c0 17.645-14.355 32-32 32s-32-14.355-32-32 14.355-32 32-32 32 14.355 32 32zm224 32c-17.645 0-32-14.355-32-32s14.355-32 32-32 32 14.355 32 32-14.355 32-32 32zm38.156-192H171.28l-36-192h406.876l-40 192z"/></svg>';
			}
			if(card.doc.parts_status === "Parts have been picked up"){
				html = '<svg xmlns="http://www.w3.org/2000/svg" height="1em" viewBox="0 0 576 512"><defs><style>.fa-secondary{opacity:0.4;fill:#00c700;}.fa-primary{fill:#00c700;}</style></defs><path class="fa-primary" d="M218.12 352h268.42a24 24 0 0 1 23.4 29.32l-5.52 24.28a56 56 0 1 1-63.6 10.4H231.18a56 56 0 1 1-67.05-8.57L93.88 64H24A24 24 0 0 1 0 40V24A24 24 0 0 1 24 0h102.53A24 24 0 0 1 150 19.19z"/><path class="fa-secondary" d="M552 64H159.21l52.36 256h293.15a24 24 0 0 0 23.4-18.68l47.27-208a24 24 0 0 0-18.08-28.72A23.69 23.69 0 0 0 552 64z"/></svg>';
			}
			return html
		}

		function getSoftwareIcons(){
			let html = "";
			if(card.doc.software_status === "Software request" || !card.doc.software_status){
				html = '<svg xmlns="http://www.w3.org/2000/svg" height="1em" viewBox="0 0 512 512"><style>svg{fill:#d1d1d1}</style><path d="M368 0H144c-26.51 0-48 21.49-48 48v416c0 26.51 21.49 48 48 48h224c26.51 0 48-21.49 48-48V48c0-26.51-21.49-48-48-48zm16 464c0 8.822-7.178 16-16 16H144c-8.822 0-16-7.178-16-16V48c0-8.822 7.178-16 16-16h224c8.822 0 16 7.178 16 16v416zm128-358v12a6 6 0 0 1-6 6h-18v6a6 6 0 0 1-6 6h-42V88h42a6 6 0 0 1 6 6v6h18a6 6 0 0 1 6 6zm0 96v12a6 6 0 0 1-6 6h-18v6a6 6 0 0 1-6 6h-42v-48h42a6 6 0 0 1 6 6v6h18a6 6 0 0 1 6 6zm0 96v12a6 6 0 0 1-6 6h-18v6a6 6 0 0 1-6 6h-42v-48h42a6 6 0 0 1 6 6v6h18a6 6 0 0 1 6 6zm0 96v12a6 6 0 0 1-6 6h-18v6a6 6 0 0 1-6 6h-42v-48h42a6 6 0 0 1 6 6v6h18a6 6 0 0 1 6 6zM30 376h42v48H30a6 6 0 0 1-6-6v-6H6a6 6 0 0 1-6-6v-12a6 6 0 0 1 6-6h18v-6a6 6 0 0 1 6-6zm0-96h42v48H30a6 6 0 0 1-6-6v-6H6a6 6 0 0 1-6-6v-12a6 6 0 0 1 6-6h18v-6a6 6 0 0 1 6-6zm0-96h42v48H30a6 6 0 0 1-6-6v-6H6a6 6 0 0 1-6-6v-12a6 6 0 0 1 6-6h18v-6a6 6 0 0 1 6-6zm0-96h42v48H30a6 6 0 0 1-6-6v-6H6a6 6 0 0 1-6-6v-12a6 6 0 0 1 6-6h18v-6a6 6 0 0 1 6-6z"/></svg>';
			}
			if(card.doc.software_status === "Software is ready for use"){
				html = '<svg xmlns="http://www.w3.org/2000/svg" class="blink-red" height="1em" viewBox="0 0 512 512"><style>svg{fill:#00c700}</style><path d="M368 0H144c-26.51 0-48 21.49-48 48v416c0 26.51 21.49 48 48 48h224c26.51 0 48-21.49 48-48V48c0-26.51-21.49-48-48-48zm16 464c0 8.822-7.178 16-16 16H144c-8.822 0-16-7.178-16-16V48c0-8.822 7.178-16 16-16h224c8.822 0 16 7.178 16 16v416zm128-358v12a6 6 0 0 1-6 6h-18v6a6 6 0 0 1-6 6h-42V88h42a6 6 0 0 1 6 6v6h18a6 6 0 0 1 6 6zm0 96v12a6 6 0 0 1-6 6h-18v6a6 6 0 0 1-6 6h-42v-48h42a6 6 0 0 1 6 6v6h18a6 6 0 0 1 6 6zm0 96v12a6 6 0 0 1-6 6h-18v6a6 6 0 0 1-6 6h-42v-48h42a6 6 0 0 1 6 6v6h18a6 6 0 0 1 6 6zm0 96v12a6 6 0 0 1-6 6h-18v6a6 6 0 0 1-6 6h-42v-48h42a6 6 0 0 1 6 6v6h18a6 6 0 0 1 6 6zM30 376h42v48H30a6 6 0 0 1-6-6v-6H6a6 6 0 0 1-6-6v-12a6 6 0 0 1 6-6h18v-6a6 6 0 0 1 6-6zm0-96h42v48H30a6 6 0 0 1-6-6v-6H6a6 6 0 0 1-6-6v-12a6 6 0 0 1 6-6h18v-6a6 6 0 0 1 6-6zm0-96h42v48H30a6 6 0 0 1-6-6v-6H6a6 6 0 0 1-6-6v-12a6 6 0 0 1 6-6h18v-6a6 6 0 0 1 6-6zm0-96h42v48H30a6 6 0 0 1-6-6v-6H6a6 6 0 0 1-6-6v-12a6 6 0 0 1 6-6h18v-6a6 6 0 0 1 6-6z"/></svg>';
			}
			if(card.doc.software_status === "Software has been attached"){
				html = '<svg xmlns="http://www.w3.org/2000/svg" height="1em" viewBox="0 0 512 512"><defs><style>.fa-secondary{opacity:0.4;fill:#00c700;}.fa-primary{fill:#00c700;}</style></defs><path class="fa-primary" d="M144 512a48 48 0 0 1-48-48V48a48 48 0 0 1 48-48h224a48 48 0 0 1 48 48v416a48 48 0 0 1-48 48z"/><path class="fa-secondary" d="M24 190v6H6a6 6 0 0 0-6 6v12a6 6 0 0 0 6 6h18v6a6 6 0 0 0 6 6h42v-48H30a6 6 0 0 0-6 6zm0-96v6H6a6 6 0 0 0-6 6v12a6 6 0 0 0 6 6h18v6a6 6 0 0 0 6 6h42V88H30a6 6 0 0 0-6 6zm482 6h-18v-6a6 6 0 0 0-6-6h-42v48h42a6 6 0 0 0 6-6v-6h18a6 6 0 0 0 6-6v-12a6 6 0 0 0-6-6zm0 192h-18v-6a6 6 0 0 0-6-6h-42v48h42a6 6 0 0 0 6-6v-6h18a6 6 0 0 0 6-6v-12a6 6 0 0 0-6-6zm0-96h-18v-6a6 6 0 0 0-6-6h-42v48h42a6 6 0 0 0 6-6v-6h18a6 6 0 0 0 6-6v-12a6 6 0 0 0-6-6zm0 192h-18v-6a6 6 0 0 0-6-6h-42v48h42a6 6 0 0 0 6-6v-6h18a6 6 0 0 0 6-6v-12a6 6 0 0 0-6-6zm-482-6v6H6a6 6 0 0 0-6 6v12a6 6 0 0 0 6 6h18v6a6 6 0 0 0 6 6h42v-48H30a6 6 0 0 0-6 6zm0-96v6H6a6 6 0 0 0-6 6v12a6 6 0 0 0 6 6h18v6a6 6 0 0 0 6 6h42v-48H30a6 6 0 0 0-6 6z"/></svg>';
			}
			return html
		}

		function getLoanCarIcons(){
			let html = "";
			if(!card.doc.custom_is_loan_car || card.doc.custom_is_loan_car === "No"){
				html = '<svg xmlns="http://www.w3.org/2000/svg" height="1em" viewBox="0 0 512 512"><style>svg{fill:#d1d1d1}</style><path d="M336 32c79.529 0 144 64.471 144 144s-64.471 144-144 144c-18.968 0-37.076-3.675-53.661-10.339L240 352h-48v64h-64v64H32v-80l170.339-170.339C195.675 213.076 192 194.968 192 176c0-79.529 64.471-144 144-144m0-32c-97.184 0-176 78.769-176 176 0 15.307 1.945 30.352 5.798 44.947L7.029 379.716A24.003 24.003 0 0 0 0 396.686V488c0 13.255 10.745 24 24 24h112c13.255 0 24-10.745 24-24v-40h40c13.255 0 24-10.745 24-24v-40h19.314c6.365 0 12.47-2.529 16.971-7.029l30.769-30.769C305.648 350.055 320.693 352 336 352c97.184 0 176-78.769 176-176C512 78.816 433.231 0 336 0zm48 108c11.028 0 20 8.972 20 20s-8.972 20-20 20-20-8.972-20-20 8.972-20 20-20m0-28c-26.51 0-48 21.49-48 48s21.49 48 48 48 48-21.49 48-48-21.49-48-48-48z"/></svg>';
			}
			if(card.doc.custom_is_loan_car === "Yes"){
				html = '<svg xmlns="http://www.w3.org/2000/svg" height="1em" viewBox="0 0 512 512"> <defs><style>.fa-secondary{opacity:0.4;fill:#00c700;}.fa-primary{fill:#00c700;}</style></defs><path class="fa-primary" d="M336 0a176 176 0 1 0 176 176A176 176 0 0 0 336 0zm48 176a48 48 0 1 1 48-48 48 48 0 0 1-48 48z"/><path class="fa-secondary" d="M303.06 348.91l.1.09-24 27a24 24 0 0 1-17.94 8H224v40a24 24 0 0 1-24 24h-40v40a24 24 0 0 1-24 24H24a24 24 0 0 1-24-24v-78a24 24 0 0 1 7-17l161.83-161.83-.11-.35a176.24 176.24 0 0 0 134.34 118.09z"/></svg>';
			}
			return html
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
					store.dispatch("update_card", card);
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

	function is_active_column(col) {
		return col.status !== "Archived";
	}

	function get_cards_for_column(cards, column) {
		return cards.filter(function (card) {
			return card.column === column.title;
		});
	}

	function get_card(name) {
		return store.state.cards.find(function (c) {
			return c.name === name;
		});
	}

	function update_cards_column(updated_cards) {
		var cards = store.state.cards;
		cards.forEach(function (c) {
			updated_cards.forEach(function (uc) {
				if (uc.name === c.name) {
					c.column = uc.column;
				}
			});
		});
		return cards;
	}

	function get_column_indicators(callback) {
		frappe.model.with_doctype("Kanban Board Column", function () {
			var meta = frappe.get_meta("Kanban Board Column");
			var indicators;
			meta.fields.forEach(function (df) {
				if (df.fieldname === "indicator") {
					indicators = df.options.split("\n");
				}
			});
			if (!indicators) {
				//
				indicators = ["green", "blue", "orange", "gray"];
			}
			callback(indicators);
		});
	}
})();
