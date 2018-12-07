frappe.provide("frappe.views");

(function() {

	var method_prefix = 'frappe.desk.doctype.kanban_board.kanban_board.';

	var store = fluxify.createStore({
		id: 'store',
		initialState: {
			doctype: '',
			board: {},
			card_meta: {},
			cards: [],
			columns: [],
			filters_modified: false,
			cur_list: {},
			empty_state: true
		},
		actionCallbacks: {
			init: function(updater, opts) {
				updater.set({
					empty_state: true
				});

				var board = opts.board;
				var card_meta = opts.card_meta;
				opts.card_meta = card_meta;
				opts.board = board;
				var cards = opts.cards.map(function(card) {
					return prepare_card(card, opts);
				});
				var columns = prepare_columns(board.columns);

				updater.set({
					doctype: opts.doctype,
					board: board,
					card_meta: card_meta,
					cards: cards,
					columns: columns,
					cur_list: opts.cur_list,
					empty_state: false
				});
			},
			update_cards: function(updater, cards) {
				var state = this;
				var _cards = cards
					.map(card => prepare_card(card, state))
					.concat(this.cards)
					.uniqBy(card => card.name);

				updater.set({
					cards: _cards
				});
			},
			add_column: function(updater, col) {
				if(frappe.model.can_create('Custom Field')) {
					fluxify.doAction('update_column', col, 'add');
				} else {
					frappe.msgprint({
						title: __('Not permitted'),
						message: __('You are not allowed to create columns'),
						indicator: 'red'
					});
				}
			},
			archive_column: function(updater, col) {
				fluxify.doAction('update_column', col, 'archive');
			},
			restore_column: function(updater, col) {
				fluxify.doAction('update_column', col, 'restore');
			},
			update_column: function(updater, col, action) {
				var doctype = this.doctype;
				var board = this.board;
				fetch_customization(doctype)
					.then(function(doc) {
						return modify_column_field_in_c11n(doc, board, col.title, action);
					})
					.then(save_customization)
					.then(function() {
						return update_kanban_board(board.name, col.title, action);
					}).then(function(r) {
						var cols = r.message;
						updater.set({
							columns: prepare_columns(cols)
						});
					}, function(err) {
						console.error(err); // eslint-disable-line
					});
			},
			add_card: function(updater, card_title, column_title) {
				var doc = frappe.model.get_new_doc(this.doctype);
				var field = this.card_meta.title_field;
				var quick_entry = this.card_meta.quick_entry;
				var state = this;

				var doc_fields = {};
				doc_fields[field.fieldname] = card_title;
				doc_fields[this.board.field_name] = column_title;
				this.board.filters_array.forEach(function(f) {
					if (f[2] !== "=") return;
					doc_fields[f[1]] = f[3];
				});

				$.extend(doc, doc_fields);

				if (field && !quick_entry) {
					return insert_doc(doc)
						.then(function(r) {
							var updated_doc = r.message;
							var card = prepare_card(doc, state, updated_doc);
							var cards = state.cards.slice();
							cards.push(card);
							updater.set({ cards: cards });
						});
				} else {
					frappe.new_doc(this.doctype, doc);
				}
			},
			update_card: function(updater, card) {
				var index = -1;
				this.cards.forEach(function(c, i) {
					if (c.name === card.name) {
						index = i;
					}
				});
				var cards = this.cards.slice();
				if (index !== -1) {
					cards.splice(index, 1, card);
				}
				updater.set({ cards: cards });
			},
			update_doc: function(updater, doc, card) {
				var state = this;
				return frappe.call({
					method: method_prefix + "update_doc",
					args: { doc: doc },
					freeze: true
				}).then(function(r) {
					var updated_doc = r.message;
					var updated_card = prepare_card(card, state, updated_doc);
					fluxify.doAction('update_card', updated_card);
				});
			},
			update_order: function(updater, order) {
				// cache original order
				const _cards = this.cards.slice();
				const _columns = this.columns.slice();

				frappe.call({
					method: method_prefix + "update_order",
					args: {
						board_name: this.board.name,
						order: order
					},
					callback: (r) => {
						var board = r.message[0];
						var updated_cards = r.message[1];
						var cards = update_cards_column(updated_cards);
						var columns = prepare_columns(board.columns);
						updater.set({
							cards: cards,
							columns: columns
						});
					}
				}).fail(function() {
					// revert original order
					updater.set({
						cards: _cards,
						columns: _columns
					});
				});
			},
			update_column_order: function(updater, order) {
				return frappe.call({
					method: method_prefix + "update_column_order",
					args: {
						board_name: this.board.name,
						order: order
					}
				}).then(function(r) {
					var board = r.message;
					var columns = prepare_columns(board.columns);
					updater.set({
						columns: columns
					});
				});
			},
			set_indicator: function(updater, column, color) {
				return frappe.call({
					method: method_prefix + "set_indicator",
					args: {
						board_name: this.board.name,
						column_name: column.title,
						indicator: color
					}
				}).then(function(r) {
					var board = r.message;
					var columns = prepare_columns(board.columns);
					updater.set({
						columns: columns
					});
				});
			}
		}
	});

	frappe.views.KanbanBoard = function(opts) {

		var self = {};
		self.wrapper = opts.wrapper;
		self.cur_list = opts.cur_list;
		self.board_name = opts.board_name;

		self.update = function(cards) {
			// update cards internally
			opts.cards = cards;

			if(self.wrapper.find('.kanban').length > 0 && self.cur_list.start !== 0) {
				fluxify.doAction('update_cards', cards);
			} else {
				init();
			}
		};

		function init() {
			fluxify.doAction('init', opts);
			store.on('change:columns', make_columns);
			prepare();
			store.on('change:cur_list', setup_restore_columns);
			store.on('change:columns', setup_restore_columns);
			store.on('change:empty_state', show_empty_state);
		}

		function prepare() {
			self.$kanban_board = self.wrapper.find('.kanban');

			if(self.$kanban_board.length === 0) {
				self.$kanban_board = $(frappe.render_template("kanban_board"));
				self.$kanban_board.appendTo(self.wrapper);
			}

			self.$filter_area = self.cur_list.$page.find('.active-tag-filters');
			bind_events();
			setup_sortable();
		}

		function make_columns() {
			self.$kanban_board.find(".kanban-column").not(".add-new-column").remove();
			var columns = store.getState().columns;

			columns.filter(is_active_column).map(function(col) {
				frappe.views.KanbanBoardColumn(col, self.$kanban_board);
			});
		}

		function bind_events() {
			bind_add_column();
		}

		function setup_sortable() {
			var sortable = new Sortable(self.$kanban_board.get(0), {
				group: 'columns',
				animation: 150,
				dataIdAttr: 'data-column-value',
				filter: '.add-new-column',
				handle: '.kanban-column-title',
				onEnd: function() {
					var order = sortable.toArray();
					order = order.slice(1);
					fluxify.doAction('update_column_order', order);
				}
			});
		}

		function bind_add_column() {

			var $add_new_column = self.$kanban_board.find(".add-new-column"),
				$compose_column = $add_new_column.find(".compose-column"),
				$compose_column_form = $add_new_column.find(".compose-column-form").hide();

			$compose_column.on('click', function() {
				$(this).hide();
				$compose_column_form.show();
				$compose_column_form.find('input').focus();
			});

			//save on enter
			$compose_column_form.keydown(function(e) {
				if (e.which == 13) {
					e.preventDefault();
					if (!frappe.request.ajax_count) {
						// not already working -- double entry
						var title = $compose_column_form.serializeArray()[0].value;
						var col = {
							title: title.trim()
						};
						fluxify.doAction('add_column', col);
						$compose_column_form.find('input').val('');
						$compose_column.show();
						$compose_column_form.hide();
					}
				}
			});

			// on form blur
			$compose_column_form.find('input').on("blur", function() {
				$(this).val('');
				$compose_column.show();
				$compose_column_form.hide();
			});
		}

		function setup_restore_columns() {
			var cur_list = store.getState().cur_list;
			var columns = store.getState().columns;
			var list_row_right = cur_list.$page
				.find(`[data-list-renderer='Kanban'] .list-row-right`)
				.css('margin-right', '15px');
			list_row_right.empty();

			var archived_columns = columns.filter(function(col) {
				return col.status === 'Archived';
			});

			if (!archived_columns.length) return;

			var options = archived_columns.reduce(function(a, b) {
				return a + "<li><a class='option'>" +
					"<span class='ellipsis' style='max-width: 100px; display: inline-block'>" +
					__(b.title) + "</span>" +
					"<button style='float:right;' data-column='" + b.title +
					"' class='btn btn-default btn-xs restore-column text-muted'>"
					+ __('Restore') + "</button></a></li>";
			}, "");
			var $dropdown = $("<div class='dropdown pull-right'>" +
				"<a class='text-muted dropdown-toggle' data-toggle='dropdown'>" +
				"<span class='dropdown-text'>" + __('Archived Columns') + "</span><i class='caret'></i></a>" +
				"<ul class='dropdown-menu'>" + options + "</ul>" +
				"</div>");

			list_row_right.html($dropdown);

			$dropdown.find(".dropdown-menu").on("click", "button.restore-column", function() {
				var column_title = $(this).data().column;
				var col = {
					title: column_title,
					status: 'Archived'
				};
				fluxify.doAction('restore_column', col);
			});
		}

		function show_empty_state() {
			var empty_state = store.getState().empty_state;

			if(empty_state) {
				self.$kanban_board.find('.kanban-column').hide();
				self.$kanban_board.find('.kanban-empty-state').show();
			} else {
				self.$kanban_board.find('.kanban-column').show();
				self.$kanban_board.find('.kanban-empty-state').hide();
			}
		}

		init();

		return self;
	};

	frappe.views.KanbanBoardColumn = function(column, wrapper) {
		var self = {};
		var filtered_cards = [];

		function init() {
			make_dom();
			setup_sortable();
			make_cards();
			store.on('change:cards', make_cards);
			bind_add_card();
			bind_options();
		}

		function make_dom() {
			self.$kanban_column = $(frappe.render_template(
				'kanban_column', {
					title: column.title,
					doctype: store.getState().doctype,
					indicator: column.indicator
				})).appendTo(wrapper);
			self.$kanban_cards = self.$kanban_column.find('.kanban-cards');
		}

		function make_cards() {
			self.$kanban_cards.empty();
			var cards = store.getState().cards;
			filtered_cards = get_cards_for_column(cards, column);
			var filtered_cards_names = filtered_cards.map(card => card.name);

			var order = column.order;
			if(order) {
				order = JSON.parse(order);
				order.forEach(function(name) {
					if (!filtered_cards_names.includes(name)) return;
					frappe.views.KanbanBoardCard(get_card(name), self.$kanban_cards);
				});
				// new cards
				filtered_cards.forEach(function(card) {
					if(order.indexOf(card.name) === -1) {
						frappe.views.KanbanBoardCard(card, self.$kanban_cards);
					}
				});
			} else {
				filtered_cards.map(function(card) {
					frappe.views.KanbanBoardCard(card, self.$kanban_cards);
				});
			}
		}

		function setup_sortable() {
			Sortable.create(self.$kanban_cards.get(0), {
				group: "cards",
				animation: 150,
				dataIdAttr: 'data-name',
				onStart: function() {
					wrapper.find('.kanban-card.add-card').fadeOut(200, function() {
						wrapper.find('.kanban-cards').height('100vh');
					});
				},
				onEnd: function() {
					wrapper.find('.kanban-card.add-card').fadeIn(100);
					wrapper.find('.kanban-cards').height('auto');
					// update order
					var order = {};
					wrapper.find('.kanban-column[data-column-value]')
						.each(function() {
							var col_name = $(this).data().columnValue;
							order[col_name] = [];
							$(this).find('.kanban-card-wrapper').each(function() {
								var card_name = $(this).data().name;
								order[col_name].push(card_name);
							});
						});
					fluxify.doAction('update_order', order);
				},
				onAdd: function() {
				},
			});
		}

		function bind_add_card() {
			var $wrapper = self.$kanban_column;
			var $btn_add = $wrapper.find('.add-card');
			var $new_card_area = $wrapper.find('.new-card-area');
			var $textarea = $new_card_area.find('textarea');

			//Add card button
			$new_card_area.hide();
			$btn_add.on('click', function() {
				$btn_add.hide();
				$new_card_area.show();
				$textarea.focus();
			});

			//save on enter
			$new_card_area.keydown(function(e) {
				if (e.which == 13) {
					e.preventDefault();
					if (!frappe.request.ajax_count) {
						// not already working -- double entry
						e.preventDefault();
						var card_title = $textarea.val();
						fluxify.doAction('add_card', card_title, column.title)
							.then(() => {
								$btn_add.show();
								$new_card_area.hide();
								$textarea.val('');
							});
					}
				}
			});

			// on textarea blur
			$textarea.on("blur", function() {
				$(this).val('');
				$btn_add.show();
				$new_card_area.hide();
			});
		}

		function bind_options() {
			self.$kanban_column.find(".column-options .dropdown-menu")
				.on("click", "[data-action]", function() {
					var $btn = $(this);
					var action = $btn.data().action;

					if (action === "archive") {
						fluxify.doAction('archive_column', column);
					} else if (action === "indicator") {
						var color = $btn.data().indicator;
						fluxify.doAction('set_indicator', column, color);
					}
				});
			get_column_indicators(function(indicators) {
				var html = '<li class="button-group">';
				html += indicators.reduce(function(prev, curr) {
					return prev + '<div \
						data-action="indicator" data-indicator="'+curr+'"\
						class="btn btn-default btn-xs indicator ' + curr + '"></div>';
				}, "");
				html += '</li>';
				self.$kanban_column.find(".column-options .dropdown-menu")
					.append(html);
			});
		}

		init();
	};

	frappe.views.KanbanBoardCard = function(card, wrapper) {
		var self = {};

		function init() {
			if(!card) return;
			make_dom();
			render_card_meta();
			bind_edit_card();
			// edit_card_title();
		}

		function make_dom() {
			var opts = {
				name: card.name,
				title: remove_img_tags(card.title)
			};
			self.$card = $(frappe.render_template('kanban_card', opts))
				.appendTo(wrapper);
		}

		function render_card_meta() {
			var html = "";
			if (card.comment_count > 0)
				html += '<span class="list-comment-count small text-muted ">' +
					'<i class="octicon octicon-comment"></i> ' + card.comment_count +
					'</span>';
			html += get_assignees_html();

			if (card.color && frappe.ui.color.validate_hex(card.color)) {
				const $div = $('<div>');
				$('<div></div>').css({
					width: '20px',
					height: '5px',
					borderRadius: '2px',
					marginBottom: '4px',
					backgroundColor: card.color
				}).appendTo($div);

				self.$card.find('.kanban-card.content').prepend($div);
			}

			self.$card.find(".kanban-card-meta").empty().append(html);
		}

		function bind_edit_card() {
			self.$card.find('.kanban-card.content').on('click', function() {
				frappe.set_route('Form', card.doctype, card.name);
				// setup_edit_card();
			});
		}

		function refresh_dialog() {
			set_dialog_fields();
			make_assignees();
		}

		function set_dialog_fields() {
			self.edit_dialog.fields.forEach(function(df) {
				var value = card.doc[df.fieldname];
				if (value) {
					self.edit_dialog.set_value(df.fieldname, value);
				}
			});
		}

		function make_assignees() {
			var d = self.edit_dialog;
			var html = get_assignees_html() + '<a class="add-assignment avatar avatar-small avatar-empty">\
				<i class="octicon octicon-plus text-muted" style="margin: 3px 0 0 5px;"></i></a>';

			d.$wrapper.find("[data-fieldname='assignees'] .control-input-wrapper").empty().append(html);
			d.$wrapper.find(".add-assignment").on("click", function() {
				if (self.assign_to_dialog) {
					self.assign_to_dialog.show();
					return;
				}
				show_assign_to_dialog();
			});
		}

		function get_assignees_html() {
			return card.assigned_list.reduce(function(a, b) {
				return a + frappe.avatar(b);
			}, "");
		}

		function show_assign_to_dialog() {
			self.assign_to = new frappe.ui.form.AssignToDialog({
				obj: self,
				method: 'frappe.desk.form.assign_to.add',
				doctype: card.doctype,
				docname: card.name,
				callback: function() {
					var user = self.assign_to_dialog.get_values().assign_to;
					card.assigned_list.push(user);
					fluxify.doAction('update_card', card);
					refresh_dialog();
				}
			});
			self.assign_to_dialog = self.assign_to.dialog;
			self.assign_to_dialog.show();
		}

		init();
	};

	function prepare_card(card, state, doc) {
		var assigned_list = card._assign ?
			JSON.parse(card._assign) : [];
		var comment_count = card._comment_count || 0;

		if (doc) {
			card = Object.assign({}, card, doc);
		}

		return {
			doctype: state.doctype,
			name: card.name,
			title: card[state.card_meta.title_field.fieldname],
			column: card[state.board.field_name],
			assigned_list: card.assigned_list || assigned_list,
			comment_count: card.comment_count || comment_count,
			color: card.color || null,
			doc: doc
		};
	}

	function prepare_columns(columns) {
		return columns.map(function(col) {
			return {
				title: col.column_name,
				status: col.status,
				order: col.order,
				indicator: col.indicator || 'darkgrey'
			};
		});
	}

	function modify_column_field_in_c11n(doc, board, title, action) {
		doc.fields.forEach(function(df) {
			if (df.fieldname === board.field_name && df.fieldtype === "Select") {
				if(!df.options) df.options = "";

				if (action === "add") {
					//add column_name to Select field's option field
					if(!df.options.includes(title))
						df.options += "\n" + title;
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
		return new Promise(function(resolve) {
			frappe.model.with_doc("Customize Form", "Customize Form", function() {
				var doc = frappe.get_doc("Customize Form");
				doc.doc_type = doctype;
				frappe.call({
					doc: doc,
					method: "fetch_to_customize",
					callback: function(r) {
						resolve(r.docs[0]);
					}
				});
			});
		});
	}

	function save_customization(doc) {
		if (!doc) return;
		doc.hide_success = true;
		return frappe.call({
			doc: doc,
			method: "save_customization"
		});
	}

	function insert_doc(doc) {
		return frappe.call({
			method: "frappe.client.insert",
			args: {
				doc: doc
			},
			callback: function() {
				frappe.model.clear_doc(doc.doctype, doc.name);
				frappe.show_alert({ message: __("Saved"), indicator: 'green' }, 1);
			}
		});
	}

	function update_kanban_board(board_name, column_title, action) {
		var method;
		var args = {
			board_name: board_name,
			column_title: column_title
		};
		if (action === 'add') {
			method = 'add_column';
		} else if (action === 'archive' || action === 'restore') {
			method = 'archive_restore_column';
			args.status = action === 'archive' ? 'Archived' : 'Active';
		}
		return frappe.call({
			method: method_prefix + method,
			args: args
		});
	}

	function is_filters_modified(board, cur_list) {
		return new Promise(function(resolve) {
			setTimeout(function() {
				try {
					var list_filters = JSON.stringify(cur_list.filter_area.get());
					resolve(list_filters !== board.filters);
				} catch(e) {
					// sometimes the filter_list is not initiated
					resolve(false);
				}

			}, 2000);
		});
	}

	function is_active_column(col) {
		return col.status !== 'Archived';
	}

	function get_cards_for_column(cards, column) {
		return cards.filter(function(card) {
			return card.column === column.title;
		});
	}

	function get_card(name) {
		return store.getState().cards.find(function(c) {
			return c.name === name;
		});
	}

	function update_cards_column(updated_cards) {
		var cards = store.getState().cards;
		cards.forEach(function(c) {
			updated_cards.forEach(function(uc) {
				if(uc.name === c.name) {
					c.column = uc.column;
				}
			});
		});
		return cards;
	}

	function get_column_indicators(callback) {
		frappe.model.with_doctype('Kanban Board Column', function() {
			var meta = frappe.get_meta('Kanban Board Column');
			var indicators;
			meta.fields.forEach(function(df) {
				if(df.fieldname==='indicator') {
					indicators = df.options.split("\n");
				}
			});
			if(!indicators) {
				//
				indicators = ['green', 'blue', 'orange', 'grey'];
			}
			callback(indicators);
		});
	}

	function isBound(el, event, fn) {
		var events = $._data(el[0], 'events');
		if(!events) return false;
		var handlers = events[event];
		var flag = false;
		handlers.forEach(function(h) {
			if(h.handler.name === fn.name)
				flag = true;
		});
		return flag;
	}

	function remove_img_tags(html) {
		const $temp = $(`<div>${html}</div>`);
		$temp.find('img').remove();
		return $temp.html();
	}
})();
