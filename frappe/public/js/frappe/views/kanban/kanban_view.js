frappe.provide("frappe.views");

frappe.views.KanbanBoard = Class.extend({
	init: function(opts) {
		this.prepare(opts);
	},
	prepare: function(opts) {
		var me = this;
		this.name = opts.name;
		this.wrapper = opts.wrapper;
		this.docs = opts.values;

		this.prepare_doc(function() {
			me.board = frappe.get_doc('Kanban Board', me.name);
			me.prepare_cards();
			me.prepare_columns();
			me.render();
		});
	},
	prepare_cards: function() {
		var me = this;
		this.cards = this.docs.map(function(doc) {
			return new frappe.views.KanbanBoardCard({
				title: doc.name,
				parent: doc[me.board.field_name]
			});
		});
	},
	prepare_columns: function() {
		var me = this;
		
		me.columns = me.board.columns.map(function(column) {
			var column_title = column.value;
			return new frappe.views.KanbanBoardColumn({
				title: column_title,
				cards: me.get_cards_for_column(column_title)
			});
		});
		console.log(me)	
	},
	get_cards_for_column: function(column_title) {
		return this.cards.filter(function(card) {
			return card.parent === column_title;
		});
	},
	render: function() {
		me.bootstrap();
		// me.make_sortable();
		// me.bind();
		
	},
	bootstrap: function() {
		this.$wrapper = $(frappe.render_template('kanban-board', { columns: this.columns }))
			.appendTo(this.wrapper);
	},
	// make_sortable: function() {
	// 	var me = this;
	// 	this.$kanban_cards.each(function(i, el){
	// 		me.setup_sortable(el);
	// 	});
	// },
	// prepare_doc: function(callback) {
	// 	var me = this;
	// 	frappe.model.with_doctype('Kanban Board', function() {
	// 		frappe.model.with_doc('Kanban Board', me.name, function() {
	// 			callback();
	// 		});
	// 	});
	// },
	// setup_sortable: function(list) {
	// 	var me = this;
	// 	Sortable.create(list, {
	// 		group: "cards",
	// 		ghostClass: "ghost-card",
	// 		chosenClass: "chosen-card",
	// 		onStart: function (evt) {
	// 			me.$el.find('.kanban-card.compose-card').fadeOut(200, function() {
	// 				me.$el.find('.kanban-cards').height('200px');
	// 			});
	// 		},
	// 		onEnd: function (evt) {
	// 			me.$el.find('.kanban-card.compose-card').fadeIn(100);
	// 			me.$el.find('.kanban-cards').height('auto');
	// 		},
	// 		onAdd: function (evt) {
	// 			var column_value = $(evt.to).parent().data().columnValue;
	// 			var card_name = $(evt.item).data().name;
	// 			if (!column_value) return;
	// 			console.log(evt);
	// 			me.update_field(card_name, me.board.field_name, column_value, function (r) {
	// 				console.log(r);
	// 			});
	// 		}
	// 	});
	// },
	// bind: function() {
	// 	this.bind_click();
	// 	this.bind_add_card();
	// },
	// bind_click: function() {
	// 	var me = this;
	// 	this.$kanban_cards.on('click', '.kanban-card-wrapper', function (e) {
	// 		var name = $(this).data().name;
	// 		frappe.set_route('Form', me.doctype, name);
	// 	});
	// },
	// bind_add_card: function() {
	// 	var me = this;
	// 	this.$el.find('.compose-card').click(function () {
	// 		$(this).hide();
			
	// 		// new
	// 		var doc = frappe.model.get_new_doc(me.doctype);
	// 		var meta = frappe.get_meta(me.doctype);
	// 		var field = null;
	// 		var quick_entry = true;
			
	// 		meta.fields.every(function(df) {
	// 			if(df.reqd && !doc[df.fieldname]) {
	// 				// missing mandatory
					
	// 				if(in_list(['Data', 'Text', 'Small Text', 'Text Editor'], df.fieldtype) && !field) {
	// 					// can be mapped to textarea
	// 					field = df;
	// 					quick_entry = false;
	// 				} else {
	// 					// second mandatory missing, use quick_entry
	// 					quick_entry = true;
	// 					return false;
	// 				}
	// 			}
	// 		});
	// 		console.log(field, quick_entry);
			
	// 		$(this).next('form').removeClass('hide').find('textarea').focus();
	// 	});
	// 	this.$el.find('.octicon-x').click(function () {
	// 		$(this).closest('form').addClass('hide');
	// 		me.$el.find('.compose-card').show();
	// 	});
	// },
	// update_field: function (name, fieldname, value, callback) {
	// 	frappe.call({
	// 		method: "frappe.client.set_value",
	// 		args: {
	// 			doctype: this.doctype,
	// 			name: name,
	// 			fieldname: fieldname,
	// 			value: value
	// 		},
	// 		callback: callback
	// 	});
	// }
});

//KanbanBoardColumn
frappe.views.KanbanBoardColumn = Class.extend({
	init: function(opts) {
		this.title = opts.title;
		this.cards = opts.cards;
	},
	make: function() {
		
	},
});


//KanbanBoardCard
frappe.views.KanbanBoardCard = Class.extend({
	init: function(opts) {
		this.title = opts.title;
		this.parent = opts.parent;
	},
});