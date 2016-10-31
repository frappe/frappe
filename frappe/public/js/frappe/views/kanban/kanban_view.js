frappe.views.KanbanView = Class.extend({
	init: function(opts) {
		this.set_defaults(opts);
		this.render();
	},
	set_defaults: function(opts) {
		this.doctype = opts.doctype;
		this.board_name = opts.board_name;
		this.values = opts.values;
		this.wrapper = opts.wrapper;
	},
	render: function() {
		var me = this;
		me.get_kanban_board_doc(function() {
			me.prepare();
			me.bootstrap();
			me.make_sortable();
			me.bind();
			console.log(me)
		});
	},
	prepare: function() {
		var me = this;
		me.board = frappe.get_doc('Kanban Board', me.board_name);
		var board_field_name = me.board.field_name;

		//map rows as cards into columns
		me.columns = me.board.columns.map(function (column) {
			var column_name = column.value;
			column.cards = me.values.filter(function (row) {
				return row[board_field_name] === column_name;
			});
			return column;
		});
	},
	bootstrap: function() {
		this.$el = $(frappe.render_template('kanban', { columns: this.columns }))
			.appendTo(this.wrapper);
		this.$kanban_cards = this.$el.find('.kanban-cards');
	},
	make_sortable: function() {
		var me = this;
		this.$kanban_cards.each(function(i, el){
			me.setup_sortable(el);
		});
	},
	get_kanban_board_doc: function(callback) {
		var me = this;
		frappe.model.with_doctype('Kanban Board', function() {
			frappe.model.with_doc('Kanban Board', me.board_name, function() {
				callback();
			});
		});
	},
	setup_sortable: function(list) {
		var me = this;
		Sortable.create(list, {
			group: "cards",
			ghostClass: "ghost-card",
			chosenClass: "chosen-card",
			onStart: function (evt) {
				me.$el.find('.kanban-card.compose-card').fadeOut(200, function() {
					me.$el.find('.kanban-cards').height('200px');
				});
			},
			onEnd: function (evt) {
				me.$el.find('.kanban-card.compose-card').fadeIn(100);
				me.$el.find('.kanban-cards').height('auto');
			},
			onAdd: function (evt) {
				var column_value = $(evt.to).parent().data().columnValue;
				var card_name = $(evt.item).data().name;
				if (!column_value) return;
				console.log(evt);
				me.update_field(card_name, me.board.field_name, column_value, function (r) {
					console.log(r);
				});
			}
		});
	},
	bind: function() {
		this.bind_click();
		this.bind_add_card();
	},
	bind_click: function() {
		var me = this;
		this.$kanban_cards.on('click', '.kanban-card-wrapper', function (e) {
			var name = $(this).data().name;
			frappe.set_route('Form', me.doctype, name);
		});
	},
	bind_add_card: function() {
		var me = this;
		this.$el.find('.compose-card').click(function () {
			$(this).hide();
			$(this).next('form').removeClass('hide').find('textarea').focus();
		});
		this.$el.find('.octicon-x').click(function () {
			$(this).closest('form').addClass('hide');
			me.$el.find('.compose-card').show();
		});
	},
	update_field: function (name, fieldname, value, callback) {
		frappe.call({
			method: "frappe.client.set_value",
			args: {
				doctype: this.doctype,
				name: name,
				fieldname: fieldname,
				value: value
			},
			callback: callback
		});
	}
});