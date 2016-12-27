frappe.provide("frappe.views");

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
		init: function(updater, opts) {
			get_board(opts.board_name)
				.then(function(board) {
					var card_meta = get_card_meta(opts);
					opts.card_meta = card_meta;
					opts.board = board;
					var cards = prepare_cards(opts.cards, opts);
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
		add_column: function(updater, col) {
			fluxify.doAction('update_column', col, 'add');
		},
		archive_column: function(updater, col) {
			fluxify.doAction('update_column', col, 'archive');
		},
		update_column: function(updater, col, action) {
			var doctype = this.doctype;
			var board = this.board;
			fetch_customization(doctype)
				.then(function(doc) {
					return save_customization(board, doc, col.title, action)
				}).then(function() {
					return update_kanban_board(board.name, col.title, action)
				}).then(function(r) {
					var cols = r.message;
					updater.set({
						columns: prepare_columns(cols)
					});
				}, function(err) {
					throw err;
				});
		},
		set_filter_state: function(updater) {
			updater.set({
				filters_modified: is_filters_modified(this.board, this.cur_list)
			});
		},
		save_filters: function(updater) {
			var filters = JSON.stringify(this.cur_list.filter_list.get_filters());
			frappe.call({
				method: "frappe.client.set_value",
				args: {
					doctype: 'Kanban Board',
					name: this.board.name,
					fieldname: 'filters',
					value: filters
				},
				callback: function() {
					updater.set({ filters_modified: false });
					show_alert({message:__("Filters saved"), indicator:'green'}, 1);
				}
			});
		},
		change_card_column: function(updater, card_name, column_title) {
			var state = this;
			frappe.call({
				method: "frappe.client.set_value",
				args: {
					doctype: this.doctype,
					name: card_name,
					fieldname: this.board.field_name,
					value: column_title
				}
			}).then(function(r) {
				var card = prepare_cards([r.message], state);
				var cards = state.cards.slice();
				cards = cards.concat(card);
				updater.set({ cards: cards });
				// show_alert({message:__("Saved"), indicator:'green'}, 1);
			})
		},
		add_card: function(updater, card_title, column_title) {
			var doc = frappe.model.get_new_doc(this.doctype);
			var field = this.card_meta.title_field;
			var quick_entry = this.card_meta.quick_entry;
			var board = this.board;
			var state = this;

			if(field && !quick_entry) {
				var doc_fields = {};
				doc_fields[field.fieldname] = card_title;
				doc_fields[this.board.field_name] = column_title;
				this.board.filters_array.forEach(function(f) {
					if(f[2]!=="=") return;
					doc_fields[f[1]] = f[3];
				});

				if(quick_entry) {
					frappe.route_options = {};
					$.extend(frappe.route_options, doc_fields);
					frappe.new_doc(this.doctype, doc);
				} else {
					$.extend(doc, doc_fields);
					return insert_doc(doc)
						.then(function(r) {
							var doc = r.message;
							var card = prepare_cards([doc], state);
							var cards = state.cards.slice().concat(card);
							updater.set({ cards: cards });
						});
				}
			}
		}
	}
});

function get_board(board_name) {
	return new Promise(function(resolve, reject) {
		var doctype = 'Kanban Board';
		frappe.model.with_doc(doctype, board_name, function() {
			var board = frappe.get_doc(doctype, board_name);
			if(!board) {
				reject(__('Kanban Board {0} does not exist.',
					['<b>'+self.board_name+'</b>']));
				// frappe.set_route('List', self.doctype);
			}
			board.filters_array = board.filters ?
				JSON.parse(board.filters) : [];
			resolve(board);
		});
	})
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

function prepare_cards(cards, state) {
	return cards.map(function(card) {
		var assigned_list = card._assign ?
			JSON.parse(card._assign) : [];
		return {
			doctype: state.doctype,
			name: card.name,
			title: card[state.card_meta.title_field.fieldname],
			column: card[state.board.field_name],
			assigned_list: assigned_list,
			comment_count: card._comment_count || 0
		};
	});
}

function prepare_columns(columns) {
	return columns.map(function(col) {
		return {
			title: col.column_name,
			status: col.status
		};
	})
}

function fetch_customization(doctype) {
	return new Promise(function(resolve, reject) {
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

function save_customization(board, doc, title, action) {
	doc.fields.forEach(function(df) {
		if(df.fieldname === board.field_name && df.fieldtype === "Select") {
			if(action==="add") {
				//add column_name to Select field's option field
				df.options += "\n" + title;
			} else if(action==="delete") {
				var options = df.options.split("\n");
				var index = options.indexOf(title);
				if(index !== -1) options.splice(index, 1);
				df.options = options.join("\n");
			}
		}
	});
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
		callback: function(r) {
			frappe.model.clear_doc(doc.doctype, doc.name);
			show_alert({message:__("Saved"), indicator:'green'}, 1);
		}
	});
}

function update_kanban_board(board_name, column_title, action) {
	return frappe.call({
		method: "frappe.desk.doctype.kanban_board.kanban_board."+action+"_column",
		args: {
			board_name: board_name,
			column_title: column_title
		}
	});
}

function is_filters_modified(board, cur_list) {
	var list_filters = JSON.stringify(cur_list.filter_list.get_filters());
	return list_filters !== board.filters;
}


frappe.stores = {}
frappe.stores = function(opts, callback) {

	var self = Object.assign({}, opts);
	var state = {};
	var actions = {};

	function init() {
		get_board(function(board) {
			self.board = board;
			prepare_meta();
			prepare_state();
			callback({
				card_meta: self.card_meta,
				state: state,
				actions: actions
			});
		});
	}

	function prepare_state() {
		prepare_cards();
		prepare_columns();
	}

	function prepare_cards() {
		var cards = self.cards.map(function(card) {
			var assigned_list = []
			if(card._assign) {
				assigned_list = JSON.parse(card._assign);
			}
			return {
				doctype: self.doctype,
				name: card.name,
				title: card.subject,
				column: card[self.board.field_name],
				assigned_list: assigned_list,
				comment_count: card._comment_count
			};
		});
		state.cards = cards;
	}

	function prepare_columns() {
		var columns = self.board.columns.map(function(column) {
			var column_name = column.column_name;
			return {
				title: column_name
			};
		});
		state.columns = columns;
	}

	function add_card(card_title, column_title) {
		var doc = frappe.model.get_new_doc(self.doctype);
		var field = self.card_meta.title_field, quick_entry = self.card_meta.quick_entry;

		if(field && !quick_entry) {
			var doc_fields = {};
			doc_fields[field.fieldname] = card_title;
			doc_fields[self.board.field_name] = column_title;
			self.board.filters_array.forEach(function(f) {
				if(f[2]!=="=") return;
				doc_fields[f[1]] = f[3];
			});

			if(quick_entry) {
				frappe.route_options = {};
				$.extend(frappe.route_options, doc_fields);
				frappe.new_doc(self.doctype, doc);
			} else {
				$.extend(doc, doc_fields);
				return insert_doc(doc)
					.then(function(r) {
						var doc = r.message;
						return {
							doctype: doc.doctype,
							name: doc.name,
							title: doc.subject,
							column: doc[self.board.field_name],
							assigned_list: []
						}
					});
			}
		}
	}
	actions.add_card = add_card;

	function insert_doc(doc) {
		return frappe.call({
			method: "frappe.client.insert",
			args: {
				doc: doc
			},
			quiet: true,
			callback: function(r) {
				frappe.model.clear_doc(doc.doctype, doc.name);
				show_alert({message:__("Saved"), indicator:'green'}, 1);
			}
		});
	}

	function add_column(column) {
		return update_column(column, "add");
	}
	actions.add_column = add_column;

	function delete_column(column) {
		return update_column(column, "delete");
	}
	actions.delete_column = delete_column;

	function update_column(column, action) {
		var defer = $.Deferred();
		fetch_customization()
			.then(function(doc) {
				return save_customization(doc, column.title, action)
			})
			.then(function() {
				return update_kanban_board(column.title, action)
			})
			.then(function() {
				if(action==="delete") {
					return delete_cards(column.cards);
				}
				return;
			})
			.then(function() {
				defer.resolve({
					title: column.title
				});
			});
		return defer;
	}

	function fetch_customization() {
		var defer = $.Deferred();
		frappe.model.with_doc("Customize Form", "Customize Form", function() {
			var doc = frappe.get_doc("Customize Form");
			doc.doc_type = self.doctype;
			frappe.call({
				doc: doc,
				method: "fetch_to_customize",
				callback: function(r) {
					defer.resolve(r.docs[0]);
				}
			});
		});
		return defer;
	}

	function save_customization(d, title, action) {
		d.fields.forEach(function(df) {
			if(df.fieldname === self.board.field_name && df.fieldtype === "Select") {
					if(action==="add") {
						//add column_name to Select field's option field
						df.options += "\n" + title;
					} else if(action==="delete") {
						var options = df.options.split("\n");
						var index = options.indexOf(title);
						if(index !== -1) options.splice(index, 1);
						df.options = options.join("\n");
					}
				}
			});
		d.hide_success = true;
		return frappe.call({
			doc: d,
			method: "save_customization"
		});
	}

	function update_kanban_board(title, action) {
		console.log(title, action)
		return frappe.call({
			method: "frappe.desk.doctype.kanban_board.kanban_board."+action+"_column",
			args: {
				board_name: self.board_name,
				column_title: title
			}
		});
	}

	function delete_cards(cards) {
		console.log(cards)
		return frappe.call({
			method: "frappe.desk.doctype.kanban_board.kanban_board.delete_cards",
			args: {
				cards: cards
			}
		});
	}

	function update_column_for_card(card_name, column_title) {
		frappe.call({
			method: "frappe.client.set_value",
			args: {
				doctype: self.doctype,
				name: card_name,
				fieldname: self.board.field_name,
				value: column_title
			},
			callback: function() {
				show_alert({message:__("Saved"), indicator:'green'}, 1);
			}
		});
	}
	actions.update_column_for_card = update_column_for_card;

	function add_assignee(assign_to, description, card, dialog, callback) {
		var args = {
			description: description
		}
		var opts = {
			method: "frappe.desk.form.assign_to.add",
			doctype: card.doctype,
			docname: card.name,
			callback: callback
		}
		frappe.ui.add_assignment(assign_to, args, opts, dialog);
	}
	actions.add_assignee = add_assignee;

	function update_doc(doc, callback) {
		console.log(doc)
		frappe.call({
			method: "frappe.client.bulk_update",
			args: { docs: [doc] },
			callback: function (r) {
				callback();
			},
			freeze: true
		});
	}
	actions.update_doc = update_doc;

	function get_board(callback) {
		var doctype = 'Kanban Board';
		frappe.model.with_doc(doctype, self.board_name, function() {
			var board = frappe.get_doc(doctype, self.board_name);

			if(!board) {
				frappe.msgprint(__('Kanban Board {0} does not exist.',
					['<b>'+self.board_name+'</b>']));
				frappe.set_route('List', self.doctype);
				return;
			}
			board.filters_array = board.filters ?
				JSON.parse(board.filters) : [];
			callback(board);
		});
	}

	function prepare_meta() {
		var meta = frappe.get_meta(self.doctype);
		var doc = frappe.model.get_new_doc(self.doctype);
		var field = null;
		var quick_entry = true;
		var description_field = null;
		var due_date_field = null;

		meta.fields.forEach(function(df) {
			if(df.reqd && !doc[df.fieldname]) {
				// missing mandatory
				if(in_list(['Data', 'Text', 'Small Text', 'Text Editor'], df.fieldtype) && !field) {
					// can be mapped to textarea
					field = df;
					quick_entry = false;
				} else {
					// second mandatory missing, use quick_entry
					quick_entry = true;
				}
			}
			if(df.fieldtype==="Text Editor" && !description_field) {
				description_field = df;
			}
			if(df.fieldtype==="Date" && df.fieldname.indexOf("end")!==-1 && !due_date_field) {
				due_date_field = df;
			}
		});
		self.card_meta = {
			title_field: field,
			description_field: description_field,
			quick_entry: quick_entry,
			due_date_field: due_date_field,
		}
	}

	function save_filters() {
		var filters = JSON.stringify(self.cur_list.filter_list.get_filters());
		return frappe.call({
			method: "frappe.client.set_value",
			args: {
				doctype: 'Kanban Board',
				name: self.board_name,
				fieldname: 'filters',
				value: filters
			},
			callback: function() {
				show_alert({message:__("Filters saved"), indicator:'green'}, 1);
			}
		});
	}
	actions.save_filters = save_filters;

	function is_filters_modified() {
		var list_filters = JSON.stringify(self.cur_list.filter_list.get_filters());
		return list_filters !== self.board.filters;
	}
	actions.is_filters_modified = is_filters_modified;

	init();
}

frappe.views.KanbanBoard = function(opts) {

	var self = {};
	self.wrapper = opts.wrapper;
	self.cur_list = opts.cur_list;

	function init() {
		fluxify.doAction('init', opts)
		store.on('change:columns', make_columns);
		prepare();
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

		columns.filter(function(col) {
			return col.status !== 'Archived'
		}).map(function(col) {
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

		$compose_column.on('click', function() {
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
		$compose_column_form.find('input').on("blur", function(e) {
			$(this).val('');
			$compose_column.show();
			$compose_column_form.hide();
		});
	}

	function bind_save_filter_button() {
		self.$save_filter_btn = self.$filter_area.find('.save-filters');
		if(self.$save_filter_btn.length) return;

		//make save filter button
		self.$save_filter_btn = $('<button>', {
			class: 'btn btn-xs btn-default text-muted save-filters',
			text: __('Save filters')
		}).on('click', function() {
			fluxify.doAction('save_filters')
		}).appendTo(self.$filter_area).hide();

		store.on('change:filters_modified', function(val) {
			val ? self.$save_filter_btn.show() :
				self.$save_filter_btn.hide();
		});

		self.cur_list.wrapper.on('render-complete', function() {
			fluxify.doAction('set_filter_state');
		});
	}

	init();
}

frappe.views.KanbanBoardColumn = function(column, wrapper) {
	var self = {};

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
		cards.filter(function(card) {
			return card.column === column.title
		}).map(function(card) {
			frappe.views.KanbanBoardCard(card, self.$kanban_cards);
		});
	}

	function setup_sortable() {
		Sortable.create(self.$kanban_cards.get(0), {
			group: "cards",
			onStart: function (evt) {
				wrapper.find('.kanban-card.add-card').fadeOut(200, function() {
					wrapper.find('.kanban-cards').height('2000px');
				});
			},
			onEnd: function (evt) {
				wrapper.find('.kanban-card.add-card').fadeIn(100);
				wrapper.find('.kanban-cards').height('auto');
			},
			onAdd: function (evt) {
				var card_name = $(evt.item).data().name;
				fluxify.doAction('change_card_column', card_name, column.title);
			}
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
			if(e.which==13) {
				e.preventDefault();
				if(!frappe.request.ajax_count) {
					// not already working -- double entry
					e.preventDefault();
					var card_title = $textarea.val();
					fluxify.doAction('add_card', card_title, column.title);
					// actions.add_card(card_title, column.title)
					// 	.then(function(card) {
					// 		cards.push(card);
					// 		frappe.views.KanbanBoardCard(card, card_meta, actions, self.$kanban_cards);
					// 	});
					//TODO
					$btn_add.show();
					$new_card_area.hide();
					$textarea.val('');
				}
			}
		});

		// on textarea blur
		$textarea.on("blur", function(e) {
			$(this).val('');
			$btn_add.show();
			$new_card_area.hide();
		});
	}

	function bind_options() {
		self.$kanban_column.find(".column-options .dropdown-menu")
			.on("click", "a", function(e) {
				var $btn = $(this);
				var action = $btn.data().action;

				if(action === "archive") {
					fluxify.doAction('archive_column', column);
				}
			});
	}

	init();
}

frappe.views.KanbanBoardCard = function(card, wrapper) {
	var self = {};

	function init() {
		make_dom();
		bind_edit_card();
	}

	function make_dom() {
		var opts = {
			name: card.name,
			title: card.title
		};
		self.$card = $(frappe.render_template('kanban_card', opts))
				.appendTo(wrapper);
		render_card_meta();
	}

	function render_card_meta() {
		var html = "";
		if(card.comment_count > 0)
			html += '<span class="list-comment-count small text-muted ">' +
					'<i class="octicon octicon-comment"></i> '+ card.comment_count +
				'</span>';
		html += get_assignees_html();
		self.$card.find(".kanban-card-meta").empty().append(html);
	}

	function bind_edit_card() {
		var card_meta = store.getState().card_meta;
		self.$card.on('click', function() {
			if(self.dialog) {
				self.dialog.show();
				return;
			}

			get_doc().then(function(doc) {
				// prepare dialog fields
				var fields = [];
				if(card_meta.description_field) {
					fields.push({ fieldtype: "Small Text", label: __("Description"),
						fieldname: card_meta.description_field.fieldname});
				}

				fields.push({ fieldtype: "Section Break" });
				fields.push({ fieldtype: "Read Only", label: "Assigned to",
					fieldname: "assignees" });
				fields.push({ fieldtype: "Column Break" });

				if(card_meta.due_date_field) {
					fields.push(card_meta.due_date_field);
				}

				var d = make_edit_dialog(card.title, fields);

				// set fields into dialog from doc
				fields.forEach(function(df) {
					var value = doc[df.fieldname];
					if(value) {
						d.set_value(df.fieldname, value);
					}
				});

				// assignees
				make_assignees();

				// activity timeline
				make_timeline();

				d.set_primary_action(__('Save'), function() {
					if(d.working) return;
					var data = d.get_values(true);
					$.extend(data, { docname: card.name, doctype: card.doctype });
					d.working = true;
					// actions.update_doc(data, function() {
					// 	d.working = false;
					// });
					//TODO
				});
				d.show();
			});
		});
	}

	function get_doc() {
		return new Promise(function(resolve, reject) {
			frappe.model.with_doc(card.doctype, card.name, function() {
				var doc = frappe.get_doc(card.doctype, card.name);
				if(!doc) {
					reject(__("{0} {1} does not exist", [card.doctype, card.name]));
				}
				self.doc = doc;
				resolve(doc);
			});
		});
	}

	function make_edit_dialog(title, fields) {
		self.dialog = new frappe.ui.Dialog({
			title: title,
			fields: fields
		});

		self.dialog.$wrapper.on("input", function() {
			console.log('changed')
		})
		return self.dialog;
	}

	function make_assignees() {
		var d = self.dialog;

		var html = get_assignees_html() + '<a class="strong add-assignment">\
			Assign <i class="octicon octicon-plus" style="margin-left: 2px;"></i></a>';

		d.$wrapper.find("[data-fieldname='assignees'] .control-input-wrapper").empty().append(html);
		d.$wrapper.find(".add-assignment").on("click", function() {
			if(self.assign_to_dialog) {
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
		var ad = new frappe.ui.Dialog({
			title: __("Assign to"),
			fields: [
				{ fieldtype: "Link", fieldname: "user", label: __("User"), options: "User"},
				{ fieldtype: "Small Text", fieldname: "description", label: __("Description")}
			]
		})
		ad.set_primary_action(__("Save"), function() {
			var assign_to = ad.fields_dict.user.get_value();
			var description = ad.fields_dict.description.get_value();
			// actions.add_assignee(assign_to, description, card, ad, function() {
			// 	card.assigned_list.push(assign_to);
			// 	make_assignees();
			// 	render_card_meta();
			// 	self.timeline.refresh(); // does not work
			// });
			//TODO
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
			<a class="edit-full">'+__('Edit in full page')+'</a></div>')
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
				doc: self.doc,
				sidebar: {
					refresh_comments: function () { }
				}
			}
		});
		tl.wrapper.addClass('in-dialog');
		tl.wrapper.find('.timeline-new-email').remove();
		tl.refresh();
		self.timeline = tl;

		// update comment count
		tl.comment_button.on("click", function(e) {
			if(tl.input.val()) {
				card.comment_count += 1;
				render_card_meta();
			}
		});
	}

	init();
}