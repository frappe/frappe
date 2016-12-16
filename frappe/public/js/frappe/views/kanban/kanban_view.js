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
	var self = Object.assign(this, opts);
	var state = {};
	var actions = {};

	function init() {
		get_board(function(board) {
			self.board = board;
			prepare_meta();
			prepare_state();
			callback({
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
				insert_doc(doc);
			}
		}
	}
	actions.add_card = add_card;

	function insert_doc(doc) {
		frappe.call({
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

	init();
}

frappe.views.KanbanBoard = function(opts) {
	
	var self = this;

	function init() {
		frappe.stores.kanban(opts, function(store) {
			self.store = store;
			self.wrapper = opts.wrapper;
			console.log(self.store);
			prepare();
		});
	}

	function prepare() {
		self.$kanban_board =
			$(frappe.render_template("kanban_board"))
				.appendTo(self.wrapper);
		// this.$filter_area = this.cur_list.$page.find('.set-filters');
		make_columns();
		// bind_events();
	}

	function make_columns() {
		var actions = self.store.actions;
		for(var column of self.store.state.columns) {
			var wrapper = self.$kanban_board;
			var cards = get_cards_for_column(column.title);
			frappe.views.KanbanBoardColumn(column, cards, wrapper, actions);
		}
	}

	function bind_events() {
		bind_add_new_column();
		bind_save_filter_button();
	}

	// bind_save_filter_button: function() {
	// 	var me = this;
	// 	me.$save_filter_btn = this.$filter_area.find('.save-filters');
	// 	if(me.$save_filter_btn.length) return;

	// 	me.$save_filter_btn = $('<button>', {
	// 		class: 'btn btn-xs btn-default text-muted save-filters',
	// 		text: 'Save filters'
	// 	}).on('click', function(){
	// 		$(this).hide();
	// 		me.save_filters();
	// 	}).appendTo(this.$filter_area).hide();

	// 	me.cur_list.wrapper.on('render-complete', function() {
	// 		if(me.is_filters_modified())
	// 			me.$save_filter_btn.show();
	// 		else
	// 			me.$save_filter_btn.hide();
	// 	});
	// },
	// save_filters: function() {
	// 	var filters = JSON.stringify(this.cur_list.filter_list.get_filters());
	// 	frappe.call({
	// 		method: "frappe.client.set_value",
	// 		args: {
	// 			doctype: 'Kanban Board',
	// 			name: this.board_name,
	// 			fieldname: 'filters',
	// 			value: filters
	// 		},
	// 		callback: function() {
	// 			show_alert({message:__("Filters saved"), indicator:'green'}, 1);
	// 		}
	// 	});
	// },
	// is_filters_modified: function() {
	// 	var list_filters = JSON.stringify(this.cur_list.filter_list.get_filters());
	// 	if(list_filters !== this.board.filters)
	// 		return true;
	// 	return false;
	// },
	function get_cards_for_column(column_name) {
		return self.store.state.cards.filter(function(card) {
			return card.column === column_name;
		});
	}
	
	// make_add_new_column: function() {
	// 	this.$add_new_column = $('<div class="kanban-column">' +
	// 		'<div class="kanban-column-title h4 add-new-column"><a class="text-muted">' +
	// 			__("Add a column") + '</a></div></div>')
	// 		.appendTo(this.$kanban_board);
	// },
	function bind_add_new_column() {
		var me = this,
		$add_new_column = this.$kanban_board.find(".add-new-column"),
		$compose_column = $add_new_column.find(".compose-column"),
		$compose_column_form = $add_new_column.find(".compose-column-form").hide();

		$compose_column.on('click', function() {
			$(this).hide();
			$compose_column_form.show();
			$compose_column_form.find('textarea').focus();
		});

		//Add button
		$compose_column_form.find('.add-new').on('click', function(e) {
			e.preventDefault();
			var title = $compose_column_form.serializeArray()[0].value;
			me.new_column(title);
		});

		//Close form button
		$compose_column_form.find('.close-form').on('click', function() {
			$compose_column.show();
			$compose_column_form.hide();
		});
	}
	// new_column: function(title) {
	// 	console.log(title)
	// 	var me = this;

	// 	frappe.model.with_doc("Customize Form", "Customize Form", function() {
	// 		var doc = frappe.get_doc("Customize Form");
	// 		doc.doc_type = me.doctype;

	// 		fetch_customization().then(save_customization);

	// 		function fetch_customization() {
	// 			return frappe.call({
	// 				doc: doc,
	// 				method: "fetch_to_customize"
	// 			});
	// 		}

	// 		function save_customization(r) {
	// 			//add column_name to Select field's option field
	// 			var d = r.docs[0];
	// 			d.fields.forEach(function(df) {
	// 				if(df.fieldname === me.board.field_name && df.fieldtype === "Select") {
	// 					df.options += "\n" + title;
	// 				}
	// 			});
	// 			return frappe.call({
	// 				doc: d,
	// 				method: "save_customization"
	// 			});
	// 		}

	// 		function update_kanban_board() {
	// 			// frappe.model.set_value("Kanban Board", me.board_name, "columns")
	// 		}
	// 	});
	// },
	init();
}

frappe.views.KanbanBoardColumn = function(column, cards, wrapper, actions) {
	var self = this;
	
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
			frappe.views.KanbanBoardCard(card, wrapper);
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
			actions.add_card(card_title, column.title);
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

frappe.views.KanbanBoardCard = function(card, wrapper) {
	var self = this;

	function init() {
		var opts = { name: card.name, title: card.title };
		self.$kanban_card = $(frappe.render_template('kanban_card', opts))
				.appendTo(wrapper);
	}

	init();
}

//KanbanBoardColumn
frappe.views.KanbanBoardColumn_old = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.prepare();
		this.make_cards();
		this.setup_sortable();
		this.bind_add_card();
		this.bind_edit_card();
	},
	prepare: function() {
		this.$kanban_column = $(frappe.render_template('kanban_column',
			{ title: this.title })).appendTo(this.wrapper);
		this.$kanban_cards = this.$kanban_column.find('.kanban-cards');
	},
	make_cards: function() {
		var me = this;
		this.cards = this.cards.map(function(card) {
			var opts = $.extend({}, card, {
				kb: me.kb,
				wrapper: me.$kanban_cards
			});
			return new frappe.views.KanbanBoardCard(opts);
		});
	},
	setup_sortable: function() {
		var me = this;
		Sortable.create(me.$kanban_cards.get(0), {
			group: "cards",
			ghostClass: "ghost-card",
			onStart: function (evt) {
				me.wrapper.find('.kanban-card.compose-card').fadeOut(200, function() {
					me.wrapper.find('.kanban-cards').height('200px');
				});
				//get the card being moved
				var card_name = $(evt.item).data().name;
				me.kb.moved_card = me.get_card(card_name);
			},
			onEnd: function (evt) {
				me.wrapper.find('.kanban-card.compose-card').fadeIn(100);
				me.wrapper.find('.kanban-cards').height('auto');
				//remove after use
				delete me.kb.moved_card;
			},
			onAdd: function (evt) {
				me.kb.moved_card.set_column(me.title); //one line update, sweet
			}
		});
	},
	get_card: function(name) {
		var card = this.cards.filter(function(card) {
			return card.name === name;
		});
		return card[0];
	},
	bind_add_card: function() {
		var me = this;
		var selector = '.kanban-column[data-column-value="'+me.title+'"]';
		var $wrapper = this.wrapper.find(selector);
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
			var title = $compose_card_form.serializeArray()[0].value;
			me.new_card(title);
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
					$compose_card_form.find('.add-new').trigger('click')
				}
			}
		});
	},
	bind_edit_card: function() {
		var me = this;
		var selector = '.kanban-column[data-column-value="'+me.title+'"]';
		var $wrapper = this.wrapper.find(selector);
		var $card = $wrapper.find('.kanban-card-wrapper');

		$card.on('click', function() {
			if(me.edit_dialog) {
				me.edit_dialog.show();
				return;
			}

			var doc_name = $(this).data().name;
			var card = me.get_card(doc_name);

			frappe.model.with_doc(me.kb.doctype, doc_name, function() {
				var doc = frappe.get_doc(me.kb.doctype, doc_name);
				var fields = [];
				if(me.kb.card_meta.description_field) {
					fields.push(me.kb.card_meta.description_field);
				}
				fields.push({ fieldtype: "Section Break" });
				fields.push({ fieldtype: "Read Only", label: "Assigned to",
					fieldname: "assignees" });
				fields.push({ fieldtype: "Column Break" });

				if(me.kb.card_meta.due_date_field) {
					fields.push(me.kb.card_meta.due_date_field);
				}


				var d = new frappe.ui.Dialog({
					title: card.title,
					fields: fields
				});

				if(me.kb.card_meta.due_date_field) {
					d.set_value(me.kb.card_meta.due_date_field.fieldname,
						doc[me.kb.card_meta.due_date_field.fieldname]);
				}
				if(me.kb.card_meta.description_field) {
					d.set_value(me.kb.card_meta.description_field.fieldname,
						doc[me.kb.card_meta.description_field.fieldname]);
				}

				// simplify editor appearance
				d.$wrapper.find(".text-editor").css("height", "60px");
				d.$wrapper.find(".frappe-list-toolbar").hide();

				// assignees
				var assignees = "", html = "";
				if(card.assigned_list.length) {
					card.assigned_list.forEach(function(a) {
						assignees += a + ",";
						html += frappe.avatar(a);
					});
					d.set_value("assignees", assignees);
				}
				html += '<a class="strong add-assignment">\
					Assign <i class="octicon octicon-plus" style="margin-left: 2px;"></i></a>';
				d.$wrapper.find("[data-fieldname='assignees'] .control-value").hide().after(html);
				d.$wrapper.find(".add-assignment").on("click", function() {

					var ad = new frappe.ui.Dialog({
						title: __("Assign to"),
						fields: [
							{ fieldtype: "Link", fieldname: "user", label: __("User"), options: "User"}
						]
					})
					ad.set_primary_action(__("Save"), function() {
						var assign_to = ad.fields_dict.user.get_value();
						var args = {
							description: d.fields_dict.description.get_value() || ""
						}
						var opts = {
							method: "frappe.desk.form.assign_to.add",
							doctype: me.kb.doctype,
							docname: doc_name
						}
						frappe.ui.add_assignment(assign_to, args, opts);
					})
					ad.show()
				})

				// activity timeline
				d.$wrapper.find('.modal-body').append("<div class='form-comments' style='padding:7px'>");
				var $link = $('<div class="text-muted small" style="padding-left: 10px; padding-top: 15px;">\
			 		<a class="edit-full">Edit in full page</a></div>').appendTo(d.$wrapper.find('.modal-body'));
				$link.on('click', function() {
					frappe.set_route("Form", me.kb.doctype, doc_name);
				});
				var tl = new frappe.ui.form.Timeline({
					parent: d.$wrapper.find(".form-comments"),
					frm: {
						doctype: me.kb.doctype,
						get_docinfo: function() {
							return frappe.model.get_docinfo(me.kb.doctype, doc_name)
						},
						doc: doc,
						sidebar: {
							refresh_comments: function() {}
						}
					}
				});
				tl.wrapper.addClass('in-dialog');
				tl.refresh();

				d.set_primary_action(__('Save'), function() {
					if(d.working) return;
					var data = d.get_values(true);
					$.extend(data, { docname: doc_name, doctype: me.kb.doctype });
					d.working = true;
					frappe.call({
						method: "frappe.client.bulk_update",
						args: { docs: [data] },
						callback: function(r) {
							d.hide();
							console.log(r);
						},
						always: function() {
							d.working = false;
						},
						freeze: true
					});
				});
				d.show();
				me.edit_dialog = d;
			});
		});
	},
	new_card: function(card_title) {
		var me = this;
		var doc = frappe.model.get_new_doc(me.kb.doctype);

		var field = me.kb.card_title_field, quick_entry = me.kb.card_quick_entry;

		if(field && !quick_entry) {
			var doc_fields = {};
			doc_fields[field.fieldname] = card_title;
			doc_fields[me.kb.board.field_name] = me.title;
			me.kb.board.filters_array.forEach(function(f) {
				if(f[2]!=="=") return;
				doc_fields[f[1]] = f[3];
			});

			if(quick_entry) {
				frappe.route_options = {};
				$.extend(frappe.route_options, doc_fields);
				frappe.new_doc(me.kb.doctype, doc);
			} else {
				$.extend(doc, doc_fields);
				me.insert_doc(doc);
			}
		}
	},
	insert_doc: function(doc) {
		var me = this;
		frappe.call({
			method: "frappe.client.insert",
			args: {
				doc: doc
			},
			callback: function(r) {
				frappe.model.clear_doc(doc.doctype, doc.name);
				show_alert({message:__("Saved"), indicator:'green'}, 1);
			}
		});
	},
});

//KanbanBoardCard
frappe.views.KanbanBoardCard_old = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.prepare();
	},
	prepare: function() {
		this.$kanban_card = $(frappe.render_template('kanban_card',
			{
				name: this.name,
				title: this.title
			}))
			.appendTo(this.wrapper);
	},
	set_column: function(column) {
		this.column = column;
		this.update_column();
	},
	update_column: function(value) {
		frappe.call({
			method: "frappe.client.set_value",
			args: {
				doctype: this.kb.doctype,
				name: this.name,
				fieldname: this.kb.board.field_name,
				value: value || this.column
			},
			callback: function() {
				show_alert({message:__("Saved"), indicator:'green'}, 1);
			}
		});
	},
});