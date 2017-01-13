frappe.provide("frappe.views");

(function () {

	var store = fluxify.createStore({
		id: 'store',
		initialState: {
			doctype: '',
			board: {},
			card_meta: {},
			cards: [],
			columns: [],
			filters_modified: false,
			cur_list: {}
		},
		actionCallbacks: {
			init: function (updater, opts) {
				get_board(opts.board_name)
					.then(function (board) {
						var card_meta = get_card_meta(opts);
						opts.card_meta = card_meta;
						opts.board = board;
						var cards = opts.cards.map(function (card) {
							return prepare_card(card, opts);
						});
						var columns = prepare_columns(board.columns);

						updater.set({
							doctype: opts.doctype,
							board: board,
							card_meta: card_meta,
							cards: cards,
							columns: columns,
							cur_list: opts.cur_list
						});
					});
			},
			add_column: function (updater, col) {
				fluxify.doAction('update_column', col, 'add');
			},
			archive_column: function (updater, col) {
				fluxify.doAction('update_column', col, 'archive');
			},
			restore_column: function (updater, col) {
				fluxify.doAction('update_column', col, 'restore');
			},
			update_column: function (updater, col, action) {
				var doctype = this.doctype;
				var board = this.board;
				fetch_customization(doctype)
					.then(function (doc) {
						return modify_column_field_in_c11n(doc, board, col.title, action)
					})
					.then(save_customization)
					.then(function (r) {
						return update_kanban_board(board.name, col.title, action)
					}).then(function (r) {
						var cols = r.message;
						updater.set({
							columns: prepare_columns(cols)
						});
					}, function (err) {
						console.error(err);
					});
			},
			set_filter_state: function (updater) {
				updater.set({
					filters_modified: is_filters_modified(this.board, this.cur_list)
				});
			},
			save_filters: function (updater) {
				var filters = JSON.stringify(this.cur_list.filter_list.get_filters());
				frappe.call({
					method: "frappe.client.set_value",
					args: {
						doctype: 'Kanban Board',
						name: this.board.name,
						fieldname: 'filters',
						value: filters
					},
					callback: function () {
						updater.set({ filters_modified: false });
						show_alert({ message: __("Filters saved"), indicator: 'green' }, 1);
					}
				});
			},
			change_card_column: function (updater, card, column_title) {
				var state = this;
				frappe.call({
					method: "frappe.client.set_value",
					args: {
						doctype: this.doctype,
						name: card.name,
						fieldname: this.board.field_name,
						value: column_title
					}
				}).then(function (r) {
					// var doc = r.message;
					// var new_card = prepare_card(card, state, doc);
					// fluxify.doAction('update_card', new_card);
				});
			},
			add_card: function (updater, card_title, column_title) {
				var doc = frappe.model.get_new_doc(this.doctype);
				var field = this.card_meta.title_field;
				var quick_entry = this.card_meta.quick_entry;
				var board = this.board;
				var state = this;

				if (field && !quick_entry) {
					var doc_fields = {};
					doc_fields[field.fieldname] = card_title;
					doc_fields[this.board.field_name] = column_title;
					this.board.filters_array.forEach(function (f) {
						if (f[2] !== "=") return;
						doc_fields[f[1]] = f[3];
					});

					if (quick_entry) {
						frappe.route_options = {};
						$.extend(frappe.route_options, doc_fields);
						frappe.new_doc(this.doctype, doc);
					} else {
						$.extend(doc, doc_fields);
						return insert_doc(doc)
							.then(function (r) {
								var doc = r.message;
								var card = prepare_card(doc, state, doc);
								var cards = state.cards.slice();
								cards.push(card);
								updater.set({ cards: cards });
							});
					}
				}
			},
			update_card: function (updater, card) {
				var index = -1;
				this.cards.forEach(function (c, i) {
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
			update_doc: function (updater, doc, card) {
				var state = this;
				return frappe.call({
					method: "frappe.desk.doctype.kanban_board.kanban_board.update_doc",
					args: { doc: doc },
					freeze: true
				}).then(function (r) {
					var updated_doc = r.message;
					var updated_card = prepare_card(card, state, updated_doc);
					fluxify.doAction('update_card', updated_card);
				});
			},
			assign_to: function (updater, user, desc, card) {
				var opts = {
					method: "frappe.desk.form.assign_to.add",
					doctype: this.doctype,
					docname: card.name,
				}
				var args = {
					description: desc
				}
				return frappe.ui.add_assignment(user, args, opts)
					.then(function () {
						card.assigned_list.push(user);
						fluxify.doAction('update_card', card);
					});
			},
			update_order: function(updater, column_title, order) {
				var board = store.getState().board.name;
				return frappe.call({
					method: "frappe.desk.doctype.kanban_board.kanban_board.update_order",
					args: {
						board_name: board,
						column_title: column_title,
						order: order
					}
				});
			}
		}
	});

	frappe.views.KanbanBoard = function (opts) {

		var self = {};
		self.wrapper = opts.wrapper;
		self.cur_list = opts.cur_list;

		function init() {
			fluxify.doAction('init', opts)
			store.on('change:columns', make_columns);
			prepare();
			store.on('change:cur_list', setup_restore_columns);
			store.on('change:columns', setup_restore_columns);
		}

		function prepare() {
			self.$kanban_board = $(frappe.render_template("kanban_board"));
			self.$kanban_board.appendTo(self.wrapper);
			self.$filter_area = self.cur_list.$page.find('.set-filters');
			bind_events();
		}

		function make_columns() {
			self.$kanban_board.find(".kanban-column").not(".add-new-column").remove();
			var columns = store.getState().columns;

			columns.filter(is_active_column).map(function (col) {
				frappe.views.KanbanBoardColumn(col, self.$kanban_board);
			});
		}

		function bind_events() {
			bind_add_column();
			bind_save_filter_button();
		}

		function bind_add_column() {

			var wrapper = self.$kanban_board;
			var $add_new_column = self.$kanban_board.find(".add-new-column"),
				$compose_column = $add_new_column.find(".compose-column"),
				$compose_column_form = $add_new_column.find(".compose-column-form").hide();

			$compose_column.on('click', function () {
				$(this).hide();
				$compose_column_form.show();
				$compose_column_form.find('input').focus();
			});

			//save on enter
			$compose_column_form.keydown(function (e) {
				if (e.which == 13) {
					e.preventDefault();
					if (!frappe.request.ajax_count) {
						// not already working -- double entry
						var title = $compose_column_form.serializeArray()[0].value;
						var col = {
							title: title.trim()
						}
						fluxify.doAction('add_column', col);
						$compose_column_form.find('input').val('');
						$compose_column.show();
						$compose_column_form.hide();
					}
				}
			});

			// on form blur
			$compose_column_form.find('input').on("blur", function (e) {
				$(this).val('');
				$compose_column.show();
				$compose_column_form.hide();
			});
		}

		function bind_save_filter_button() {
			self.$save_filter_btn = self.$filter_area.find('.save-filters');
			if (self.$save_filter_btn.length) return;

			//make save filter button
			self.$save_filter_btn = $('<button>', {
				class: 'btn btn-xs btn-default text-muted save-filters',
				text: __('Save filters')
			}).on('click', function () {
				fluxify.doAction('save_filters')
			}).appendTo(self.$filter_area).hide();

			store.on('change:filters_modified', function (val) {
				val ? self.$save_filter_btn.show() :
					self.$save_filter_btn.hide();
			});

			self.cur_list.wrapper.on('render-complete', function () {
				fluxify.doAction('set_filter_state');
			});
		}

		function setup_restore_columns() {
			var cur_list = store.getState().cur_list;
			var columns = store.getState().columns;
			cur_list.$page.find(".list-row-right").empty();

			var archived_columns = columns.filter(function (col) {
				return col.status === 'Archived';
			});

			if (!archived_columns.length) return;

			var options = archived_columns.reduce(function (a, b) {
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
				"</div>")

			cur_list.$page.find(".list-row-right").css("margin-top", 0).html($dropdown);

			$dropdown.find(".dropdown-menu").on("click", "button.restore-column", function (e) {
				var column_title = $(this).data().column;
				var col = {
					title: column_title,
					status: 'Archived'
				}
				fluxify.doAction('restore_column', col);
			});
		}

		init();
	}

	frappe.views.KanbanBoardColumn = function (column, wrapper) {
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
			self.$kanban_column = $(frappe.render_template('kanban_column',
				{ title: column.title })).appendTo(wrapper);
			self.$kanban_cards = self.$kanban_column.find('.kanban-cards');
		}

		function make_cards() {
			self.$kanban_cards.empty();
			var cards = store.getState().cards;
			var board = store.getState().board;
			filtered_cards = get_cards_for_column(cards, column);

			var order = column.order;
			if(order) {
				order = order.split('|');
				order.forEach(function(name) {
					frappe.views.KanbanBoardCard(get_card(name), self.$kanban_cards);
				});
				// new cards
				filtered_cards.forEach(function(card) {
					if(order.indexOf(card.name) === -1) {
						frappe.views.KanbanBoardCard(card, self.$kanban_cards);
					}
				});
			} else {
				filtered_cards.map(function (card) {
					frappe.views.KanbanBoardCard(card, self.$kanban_cards);
				});
			}
		}

		function setup_sortable() {
			var sortable = Sortable.create(self.$kanban_cards.get(0), {
				group: "cards",
				animation: 150,
				dataIdAttr: 'data-name',
				onStart: function (evt) {
					wrapper.find('.kanban-card.add-card').fadeOut(200, function () {
						wrapper.find('.kanban-cards').height('100vh');
					});
				},
				onEnd: function (evt) {
					wrapper.find('.kanban-card.add-card').fadeIn(100);
					wrapper.find('.kanban-cards').height('auto');
					var card_name = $(evt.item).data().name;
					var card = get_card(card_name);
					var board = store.getState().board.name;
					// update order
					var order = sortable.toArray();
					fluxify.doAction('update_order', column.title, order.join('|'));
				},
				onAdd: function (evt) {
					var card_name = $(evt.item).data().name;
					var card = get_card(card_name);
					fluxify.doAction('change_card_column', card, column.title);
					// update order
					var order = sortable.toArray();
					fluxify.doAction('update_order', column.title, order.join('|'));
				},
			});
		}

		function get_card_by_order(order) {
			var board = store.getState().board.name;
			filtered_cards.find(function(c) {
				return c.kanban_column_order[board] === order;
			});
		}

		function get_card(name) {
			return store.getState().cards.find(function (c) {
				return c.name === name;
			});
		}

		function bind_add_card() {
			var $wrapper = self.$kanban_column;
			var $btn_add = $wrapper.find('.add-card');
			var $new_card_area = $wrapper.find('.new-card-area');
			var $textarea = $new_card_area.find('textarea');

			//Add card button
			$new_card_area.hide();
			$btn_add.on('click', function () {
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
						fluxify.doAction('add_card', card_title, column.title);
						$btn_add.show();
						$new_card_area.hide();
						$textarea.val('');
					}
				}
			});

			// on textarea blur
			$textarea.on("blur", function (e) {
				$(this).val('');
				$btn_add.show();
				$new_card_area.hide();
			});
		}

		function bind_options() {
			self.$kanban_column.find(".column-options .dropdown-menu")
				.on("click", "a", function (e) {
					var $btn = $(this);
					var action = $btn.data().action;

					if (action === "archive") {
						fluxify.doAction('archive_column', column);
					}
				});
		}

		init();
	}

	frappe.views.KanbanBoardCard = function (card, wrapper) {
		var self = {};

		function init() {
			if(!card) return;
			make_dom();
			render_card_meta();
			bind_edit_card();
			edit_card_title();
		}

		function make_dom() {
			var opts = {
				name: card.name,
				title: card.title
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
			self.$card.find(".kanban-card-meta").empty().append(html);
		}

		function bind_edit_card() {
			self.$card.find('.kanban-card.content').on('click', function () {
				setup_edit_card();
			});
		}

		function setup_edit_card() {
			if (self.dialog) {
				refresh_dialog();
				self.dialog.show();
				return;
			}

			var card_meta = store.getState().card_meta;
			get_doc().then(function () {
				// prepare dialog fields
				var fields = [];
				if (card_meta.description_field) {
					fields.push({
						fieldtype: "Small Text", label: __("Description"),
						fieldname: card_meta.description_field.fieldname
					});
				}

				fields.push({ fieldtype: "Section Break" });
				fields.push({
					fieldtype: "Read Only", label: "Assigned to",
					fieldname: "assignees"
				});
				fields.push({ fieldtype: "Column Break" });

				if (card_meta.due_date_field) {
					fields.push(card_meta.due_date_field);
				}

				var d = make_edit_dialog(card.title, fields);

				refresh_dialog();
				make_timeline();

				d.set_primary_action(__('Save'), function () {
					if (d.working) return;
					var doc = d.get_values(true);
					$.extend(doc, { name: card.name, doctype: card.doctype });
					d.working = true;
					fluxify.doAction('update_doc', doc, card)
						.then(function (r) {
							d.working = false;
							// fluxify.doAction('update_card', card)
						});
				});
				d.show();
			});
		}

		function refresh_dialog() {
			set_dialog_fields();
			make_assignees();
		}

		function set_dialog_fields() {
			self.dialog.fields.forEach(function (df) {
				var value = card.doc[df.fieldname];
				if (value) {
					self.dialog.set_value(df.fieldname, value);
				}
			});
		}

		function get_doc() {
			return new Promise(function (resolve, reject) {
				frappe.model.with_doc(card.doctype, card.name, function () {
					frappe.call({
						method: 'frappe.client.get',
						args: {
							doctype: card.doctype,
							name: card.name
						},
						callback: function (r) {
							var doc = r.message;
							if (!doc) {
								reject(__("{0} {1} does not exist", [card.doctype, card.name]));
							}
							card.doc = doc;
							resolve();
						}
					});
				});
			});
		}

		function make_edit_dialog(title, fields) {
			self.dialog = new frappe.ui.Dialog({
				title: title,
				fields: fields
			});
			return self.dialog;
		}

		function make_assignees() {
			var d = self.dialog;
			var html = get_assignees_html() + '<a class="strong add-assignment">\
		Assign <i class="octicon octicon-plus" style="margin-left: 2px;"></i></a>';

			d.$wrapper.find("[data-fieldname='assignees'] .control-input-wrapper").empty().append(html);
			d.$wrapper.find(".add-assignment").on("click", function () {
				if (self.assign_to_dialog) {
					self.assign_to_dialog.show();
					return;
				}
				show_assign_to_dialog();
			});
		}

		function get_assignees_html() {
			return card.assigned_list.reduce(function (a, b) {
				return a + frappe.avatar(b);
			}, "");
		}

		function show_assign_to_dialog() {
			var ad = new frappe.ui.Dialog({
				title: __("Assign to"),
				fields: [
					{ fieldtype: "Link", fieldname: "user", label: __("User"), options: "User" },
					{ fieldtype: "Small Text", fieldname: "description", label: __("Description") }
				]
			})
			ad.set_primary_action(__("Save"), function () {
				var values = ad.get_values();
				fluxify.doAction('assign_to', values.user, values.description, card)
					.then(function () {
						refresh_dialog();
						ad.hide();
					});
			});
			ad.show();
			self.assign_to_dialog = ad;
		}

		function make_timeline() {
			var d = self.dialog;
			// timeline wrapper
			d.$wrapper.find('.modal-body').append('<div class="form-comments" style="padding:7px">');

			// edit in full page button
			$('<div class="text-muted small" style="padding-left: 10px; padding-top: 15px;">\
		<a class="edit-full">'+ __('Edit in full page') + '</a></div>')
				.appendTo(d.$wrapper.find('.modal-body'))
				.on('click', function () {
					frappe.set_route("Form", card.doctype, card.name);
				});
			var tl = new frappe.ui.form.Timeline({
				parent: d.$wrapper.find(".form-comments"),
				frm: {
					doctype: card.doctype,
					docname: card.name,
					get_docinfo: function () {
						return frappe.model.get_docinfo(card.doctype, card.name)
					},
					doc: card.doc,
					sidebar: {
						refresh_comments: function () { }
					},
					trigger: function () { }
				}
			});
			tl.wrapper.addClass('in-dialog');
			tl.wrapper.find('.timeline-new-email').remove();
			// update comment count
			var tl_refresh = tl.refresh.bind(tl);
			tl.refresh = function () {
				tl_refresh();
				var communications = tl.get_communications();
				var comment_count = communications.filter(function (c) {
					return c.comment_type === 'Comment';
				}).length;
				if (comment_count !== card.comment_count) {
					card.comment_count = comment_count;
					fluxify.doAction('update_card', card);
				}
			}
			tl.refresh();
		}

		function edit_card_title() {
			var $edit_card_area = self.$card.find('.edit-card-area').hide();
			var $kanban_card_area = self.$card.find('.kanban-card.content');
			var $textarea = $edit_card_area.find('textarea').val(card.title);

			self.$card.find('.kanban-card-edit').on('click', function (e) {
				e.stopPropagation();
				$edit_card_area.show();
				$kanban_card_area.hide();
				$textarea.focus();
			});

			$textarea.on('blur', function () {
				$edit_card_area.hide();
				$kanban_card_area.show();
			});

			$textarea.keydown(function (e) {
				if (e.which === 13) {
					e.preventDefault();
					var new_title = $textarea.val();
					if (card.title === new_title) {
						return;
					}
					get_doc().then(function () {
						var tf = store.getState().card_meta.title_field.fieldname;
						var doc = card.doc;
						doc[tf] = new_title;
						fluxify.doAction('update_doc', doc, card);
					})
				}
			})
		}

		init();
	}

	// Helpers
	function get_board(board_name) {
		return frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: 'Kanban Board',
				name: board_name
			}
		}).then(function(r) {
			var board = r.message;
			if (!board) {
				frappe.msgprint(__('Kanban Board {0} does not exist.',
					['<b>' + self.board_name + '</b>']));
			}
			return prepare_board(board);
		});
	}

	function prepare_board(board) {
		board.filters_array = board.filters ?
			JSON.parse(board.filters) : [];
		return board;
	}

	function get_card_meta(opts) {
		var meta = frappe.get_meta(opts.doctype);
		var doc = frappe.model.get_new_doc(opts.doctype);
		var field = null;
		var quick_entry = true;
		var description_field = null;
		var due_date_field = null;

		meta.fields.forEach(function (df) {
			if (df.reqd && !doc[df.fieldname]) {
				// missing mandatory
				if (in_list(['Data', 'Text', 'Small Text', 'Text Editor'], df.fieldtype) && !field) {
					// can be mapped to textarea
					field = df;
					quick_entry = false;
				} else {
					// second mandatory missing, use quick_entry
					quick_entry = true;
				}
			}
			if (df.fieldtype === "Text Editor" && !description_field) {
				description_field = df;
			}
			if (df.fieldtype === "Date" && df.fieldname.indexOf("end") !== -1 && !due_date_field) {
				due_date_field = df;
			}
		});
		return {
			quick_entry: quick_entry,
			title_field: field,
			description_field: description_field,
			due_date_field: due_date_field,
		}
	}

	function prepare_card(card, state, doc) {
		var assigned_list = card._assign ?
			JSON.parse(card._assign) : [];
		var comment_count = card._comment_count || 0;

		if (card.kanban_column_order === null || card.kanban_column_order === '') {
			var kanban_column_order = {};
		} else if (typeof card.kanban_column_order === 'string') {
			kanban_column_order = JSON.parse(card.kanban_column_order);
		} else if (typeof card.kanban_column_order === 'object') {
			kanban_column_order = card.kanban_column_order;
		}

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
			kanban_column_order: kanban_column_order,
			doc: doc
		};
	}

	function prepare_columns(columns) {
		return columns.map(function (col) {
			return {
				title: col.column_name,
				status: col.status,
				order: col.order
			};
		})
	}

	function modify_column_field_in_c11n(doc, board, title, action) {
		doc.fields.forEach(function (df) {
			if (df.fieldname === board.field_name && df.fieldtype === "Select") {
				if (action === "add") {
					//add column_name to Select field's option field
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
		return new Promise(function (resolve, reject) {
			frappe.model.with_doc("Customize Form", "Customize Form", function () {
				var doc = frappe.get_doc("Customize Form");
				doc.doc_type = doctype;
				frappe.call({
					doc: doc,
					method: "fetch_to_customize",
					callback: function (r) {
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
			callback: function (r) {
				frappe.model.clear_doc(doc.doctype, doc.name);
				show_alert({ message: __("Saved"), indicator: 'green' }, 1);
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
			method: 'frappe.desk.doctype.kanban_board.kanban_board.' + method,
			args: args
		});
	}

	function is_filters_modified(board, cur_list) {
		var list_filters = JSON.stringify(cur_list.filter_list.get_filters());
		return list_filters !== board.filters;
	}

	function is_active_column(col) {
		return col.status !== 'Archived'
	}

	function get_cards_for_column(cards, column) {
		return cards.filter(function (card) {
			return card.column === column.title
		});
	}

})();
