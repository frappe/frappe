frappe.provide("frappe.views");
frappe.provide("frappe.stores")

/**
 * frappe.views.KanbanBoard
 *
 * opts:
 * 		board_name - Kanban Board name
 * 		cards - Values in list view to be rendered as cards
 * 		wrapper - wrapper for kanban
 */
frappe.stores.kanban = function(opts, callback) {
	// doctype: me.doctype,
	// board_name: me.kanban_board,
	// cards: values,
	// wrapper: me.wrapper.find('.result-list'),
	// cur_list: me
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
				assigned_list: assigned_list
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

	function add_column(title) {
		title = title.trim();

		var defer = $.Deferred();

		frappe.model.with_doc("Customize Form", "Customize Form", function() {
			var doc = frappe.get_doc("Customize Form");
			doc.doc_type = self.doctype;
			

			return fetch_customization()
				.then(save_customization)
				.then(update_kanban_board)
				.then(function(r) {
					console.log(r);
					defer.resolve({
						title: title
					});
				});

			function fetch_customization() {
				return frappe.call({
					doc: doc,
					method: "fetch_to_customize"
				});
			}

			function save_customization(r) {
				//add column_name to Select field's option field
				var d = r.docs[0];
				d.fields.forEach(function(df) {
					if(df.fieldname === self.board.field_name && df.fieldtype === "Select") {
						df.options += "\n" + title;
					}
				});
				d.hide_success = true;
				return frappe.call({
					doc: d,
					method: "save_customization"
				});
			}

			function update_kanban_board() {
				return frappe.call({
					method: "frappe.desk.doctype.kanban_board.kanban_board.update_column",
					args: {
						board_name: self.board_name,
						column_title: title
					}
				});
			}
		});
		return defer;
	}
	actions.add_column = add_column;

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
	var actions, card_meta;

	function init() {
		frappe.stores.kanban(opts, function(store) {
			self.store = store;
			self.wrapper = opts.wrapper;
			self.cur_list = opts.cur_list;
			actions = self.store.actions;
			card_meta = self.store.card_meta;
			
			prepare();
		});
	}

	function prepare() {
		self.$kanban_board = $(frappe.render_template("kanban_board"));
		self.$kanban_board.appendTo(self.wrapper);
		self.$filter_area = self.cur_list.$page.find('.set-filters');
		make_columns();
		bind_events();
	}

	function make_columns() {
		for(var column of self.store.state.columns) {
			var wrapper = self.$kanban_board;
			var cards = get_cards_for_column(column.title);
			frappe.views.KanbanBoardColumn(column, cards, card_meta, wrapper, actions);
		}
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
					actions.add_column(title)
						.then(function (column) {
							frappe.views.KanbanBoardColumn(column, [], card_meta, wrapper, actions);
						});
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
			$(this).hide();
			actions.save_filters();
		}).appendTo(self.$filter_area).hide();

		self.cur_list.wrapper.on('render-complete', function() {
			actions.is_filters_modified() ?
				self.$save_filter_btn.show() :
				self.$save_filter_btn.hide()
		});
	}

	function get_cards_for_column(column_name) {
		return self.store.state.cards.filter(function(card) {
			return card.column === column_name;
		});
	}

	init();
}

frappe.views.KanbanBoardColumn = function(column, cards, card_meta, wrapper, actions) {
	var self = {};

	function init() {
		make_dom();
		make_cards();
		setup_sortable();
		bind_add_card();
	}

	function make_dom() {
		self.$kanban_column = $(frappe.render_template('kanban_column',
			{ title: column.title })).appendTo(wrapper);
		self.$kanban_cards = self.$kanban_column.find('.kanban-cards');
	}

	function make_cards() {
		for(var card of cards) {
			var wrapper = self.$kanban_cards;
			frappe.views.KanbanBoardCard(card, card_meta, actions, wrapper);
		}
	}

	function setup_sortable() {
		Sortable.create(self.$kanban_cards.get(0), {
			group: "cards",
			ghostClass: "ghost-card",
			onStart: function (evt) {
				wrapper.find('.kanban-card.compose-card').fadeOut(200, function() {
					wrapper.find('.kanban-cards').height('200px');
				});
			},
			onEnd: function (evt) {
				wrapper.find('.kanban-card.compose-card').fadeIn(100);
				wrapper.find('.kanban-cards').height('auto');
			},
			onAdd: function (evt) {
				var card_name = $(evt.item).data().name;
				actions.update_column_for_card(card_name, column.title);
			}
		});
	}

	function bind_add_card() {
		var selector = '.kanban-column[data-column-value="'+column.title+'"]';
		var $wrapper = wrapper.find(selector);
		var $compose_card = $wrapper.find('.compose-card');
		var $compose_card_form = $wrapper.find('.compose-card-form');

		//Add card button
		$compose_card_form.hide();
		$compose_card.on('click', function() {
			$compose_card.hide();
			$compose_card_form.show().find('textarea').focus();
		});

		//Add button
		$compose_card_form.find('.add-new').on('click', function(e) {
			e.preventDefault();
			var card_title = $compose_card_form.serializeArray()[0].value;
			actions.add_card(card_title, column.title)
				.then(function(card) {
					frappe.views.KanbanBoardCard(card, card_meta, actions, self.$kanban_cards);
				});
			$compose_card.show();
			$compose_card_form.hide().find('textarea').val('');
		});

		//Close form button
		$compose_card_form.find('.close-form').on('click', function() {
			$compose_card.show();
			$compose_card_form.hide();
		});

		//save on enter
		$compose_card_form.keydown(function(e) {
			if(e.which==13) {
				e.preventDefault();
				if(!frappe.request.ajax_count) {
					// not already working -- double entry
					$compose_card_form.find('.add-new').trigger('click');
				}
			}
		});
	}

	init();
}

frappe.views.KanbanBoardCard = function(card, card_meta, actions, wrapper) {
	var self = {};

	function init() {
		make_dom();
		bind_edit_card();
	}

	function make_dom() {
		var opts = { name: card.name, title: card.title };
		self.$card = $(frappe.render_template('kanban_card', opts))
				.appendTo(wrapper);
	}

	function bind_edit_card() {

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
					actions.update_doc(data, function() {
						d.working = false;
					});
				});
				d.show();
			});
		});
	}

	function get_doc() {
		var defer = new $.Deferred();
		frappe.model.with_doc(card.doctype, card.name, function() {
			var doc = frappe.get_doc(card.doctype, card.name);
			self.doc = doc;
			defer.resolve(doc);
		});
		return defer.promise();
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

		var assignees = "", html = "";
		if(card.assigned_list.length) {
			card.assigned_list.forEach(function(a) {
				html += frappe.avatar(a);
			});
		}
		html += '<a class="strong add-assignment">\
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
			actions.add_assignee(assign_to, description, card, ad, function() {
				card.assigned_list.push(assign_to);
				make_assignees();
				self.timeline.refresh(); // does not work
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
			<a class="edit-full">'+__('Edit in full page')+'</a></div>')
			.appendTo(d.$wrapper.find('.modal-body'))
			.on('click', function () {
				frappe.set_route("Form", card.doctype, card.name);
			});

		var tl = new frappe.ui.form.Timeline({
			parent: d.$wrapper.find(".form-comments"),
			frm: {
				doctype: card.doctype,
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
	}

	init();
}