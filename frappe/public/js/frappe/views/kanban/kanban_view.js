frappe.provide("frappe.views");

/**
 * frappe.views.KanbanBoard
 * 
 * opts: 
 * 		name - Kanban Board name
 * 		docs - Values in list view to be rendered as cards
 * 		wrapper - wrapper for kanban
 */

frappe.views.KanbanBoard = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.prepare(opts);
	},
	prepare: function(opts) {
		var me = this;
		this.$kanban_board = $('<div class="kanban">').appendTo(this.wrapper);
		this.$filter_area = this.cur_list.$page.find('.set-filters');

		me.get_board(function(board) {
			me.board = board;
			me.prepare_cards();
			me.prepare_meta();
			me.make_columns();
			me.bind_events();
		})
	},
	prepare_cards: function() {
		var me = this;
		this._cards = this.cards.map(function(card) {
			var assigned_list = []
			if(card._assign) {
				assigned_list = JSON.parse(card._assign);
			}
			return {
				name: card.name,
				title: card.subject,
				column: card[me.board.field_name],
				assigned_list: assigned_list
			};
		});
	},
	make_columns: function() {
		var me = this;
		
		me.columns = me.board.columns.map(function(column) {
			var column_name = column.column_name;
			return new frappe.views.KanbanBoardColumn({
				kb: me,
				title: column_name,
				cards: me.get_cards_for_column(column_name),
				wrapper: me.$kanban_board
			});
		});
		me.make_add_new_column();
	},
	bind_events: function() {
		this.bind_add_new_column();
		this.bind_save_filter_button();
	},
	bind_save_filter_button: function() {
		var me = this;
		me.$save_filter_btn = this.$filter_area.find('.save-filters'); 
		if(me.$save_filter_btn.length) return;

		me.$save_filter_btn = $('<button>', {
			class: 'btn btn-xs btn-default text-muted save-filters',
			text: 'Save filters'
		}).on('click', function(){
			$(this).hide();
			me.save_filters();
		}).appendTo(this.$filter_area).hide();

		me.cur_list.wrapper.on('render-complete', function() {
			if(me.is_filters_modified())
				me.$save_filter_btn.show();
			else
				me.$save_filter_btn.hide();
		});
	},
	save_filters: function() {
		var filters = JSON.stringify(this.cur_list.filter_list.get_filters());
		frappe.call({
			method: "frappe.client.set_value",
			args: {
				doctype: 'Kanban Board',
				name: this.board_name,
				fieldname: 'filters',
				value: filters
			},
			callback: function() {
				show_alert({message:__("Filters saved"), indicator:'green'}, 1);
			}
		});
	},
	is_filters_modified: function() {
		var list_filters = JSON.stringify(this.cur_list.filter_list.get_filters());
		if(list_filters !== this.board.filters)
			return true;
		return false;
	},
	get_cards_for_column: function(column_name) {
		return this._cards.filter(function(card) {
			return card.column === column_name;
		});
	},
	get_board: function(callback) {
		var me = this;
		var doctype = 'Kanban Board';
		frappe.model.with_doctype(doctype, function() {
			frappe.model.with_doc(doctype, me.board_name, function() {
				var board = frappe.get_doc(doctype, me.board_name);
				if(!board) {
					frappe.msgprint(__('Kanban Board {0} does not exist.',
						['<b>'+me.board_name+'</b>']));
					frappe.set_route('List', me.doctype);
					return;
				}
				board.filters_array = board.filters ?
					JSON.parse(board.filters) : [];
				callback(board);
			});
		});
	},
	make_add_new_column: function() {
		this.$add_new_column = $('<div class="kanban-column">' +
			'<div class="kanban-column-title h4 add-new-column">' +
				__("Add a column") + '</div></div>')
			.appendTo(this.$kanban_board);
	},
	bind_add_new_column: function() {
		this.$add_new_column.on('click', function() {
			//add column_name to Select field's option field
		})
	},
	insert_option_to_customization: function() {
		frappe.call({
			method: "frappe.custom.doctype.customize_form.customize_form",
			args: {
				
			}
		})
	},
	prepare_meta: function() {
		var meta = frappe.get_meta(this.doctype);
		var doc = frappe.model.get_new_doc(this.doctype);
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
		this.card_title_field = field;
		this.card_description_field = description_field;
		this.card_quick_entry = quick_entry;
		this.due_date_field = due_date_field;
	}
});

//KanbanBoardColumn
frappe.views.KanbanBoardColumn = Class.extend({
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
			var doc_name = $(this).data().name;
			var card = me.get_card(doc_name);

			frappe.model.with_doc(me.kb.doctype, doc_name, function() {
				var doc = frappe.get_doc(me.kb.doctype, doc_name);
				// console.log(doc)
				var fields = [];
				// fields.push({ fieldtype: "Read Only", label: "In Column", default: me.title});
				// fields.push({ fieldtype: "Section Break" });
				if(me.kb.card_description_field) {
					fields.push(me.kb.card_description_field);
				}
				fields.push({ fieldtype: "Section Break" });
				fields.push({ fieldtype: "Read Only", label: "Assigned to",
					fieldname: "assignees" });
				fields.push({ fieldtype: "Column Break" });

				if(me.kb.due_date_field) {
					fields.push(me.kb.due_date_field);
				}

				var d = new frappe.ui.Dialog({
					title: card.title,
					fields: fields
				});

				if(me.kb.due_date_field) {
					d.set_value(me.kb.due_date_field.fieldname, doc[me.kb.due_date_field.fieldname]);
				}
				if(me.kb.card_description_field) {
					d.set_value(me.kb.card_description_field.fieldname, doc[me.kb.card_description_field.fieldname]);
				}

				// var indicator = frappe.get_indicator(doc, me.kb.doctype);
				// var indicator_html = $("<span class='indicator'>"+indicator[0]+"</span>")
				// 	.addClass(indicator[1]).css("float", "left");
				// d.$wrapper.find('.modal-title').css({
				// 	float: "left", marginRight: "7px"
				// }).after(indicator_html);

				d.$wrapper.find(".text-editor").css("height", "60px");
				d.$wrapper.find(".frappe-list-toolbar").hide();
				
				var assignees = "", html = "";
				if(card.assigned_list.length) {
					card.assigned_list.forEach(function(a) {
						assignees += a + ",";
						html += frappe.avatar(a);
					});
					d.set_value("assignees", assignees);
				}

				d.$wrapper.find("[data-fieldname='assignees'] .control-value").hide().after(html);

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
				console.log(tl)
				tl.wrapper.addClass('in-dialog');
				tl.refresh();
				d.show();

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
				window.dialog = d

			})
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
frappe.views.KanbanBoardCard = Class.extend({
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