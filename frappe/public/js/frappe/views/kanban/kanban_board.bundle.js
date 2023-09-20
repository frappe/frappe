// TODO: Refactor for better UX

import Vuex from "vuex";

frappe.provide("frappe.views");

(function () {
	var method_prefix = "frappe.desk.doctype.kanban_board.kanban_board.";

	let columns_unwatcher = null;

	var store = new Vuex.Store({
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
								columns: prepare_columns(cols),
							});
						},
						function (err) {
							console.error(err); // eslint-disable-line
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
							let columns = prepare_columns(board.columns);
							context.commit("update_state", {
								cards: cards,
								columns: columns,
							});
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
						var columns = prepare_columns(board.columns);
						context.commit("update_state", {
							columns: columns,
						});
					});
			},
		},
	});

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
			store.dispatch("init", opts);
			columns_unwatcher && columns_unwatcher();
			store.watch((state, getters) => {
				return state.columns;
			}, make_columns);
			prepare();
			make_columns();
			store.watch((state, getters) => {
				return state.cur_list;
			}, setup_restore_columns);
			columns_unwatcher = store.watch((state, getters) => {
				return state.columns;
			}, setup_restore_columns);
			store.watch((state, getters) => {
				return state.empty_state;
			}, show_empty_state);

			store.dispatch("update_order");
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
			for (let field_name of cur_list.board.fields) {
				let field =
					frappe.meta.get_docfield(card.doctype, field_name, card.name) ||
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
			let html = get_tags_html(card);

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
