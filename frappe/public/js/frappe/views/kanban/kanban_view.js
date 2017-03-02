frappe.provide('frappe.views');

frappe.views.KanbanView = frappe.views.ListRenderer.extend({
	name: 'Kanban',
	render_view: function(values) {
		var board_name = this.list_view.kanban_board_name;
		this.kanban = new frappe.views.KanbanBoard({
			doctype: this.doctype,
			board_name: board_name,
			cards: values,
			wrapper: this.wrapper,
			cur_list: this.list_view,
			user_settings: this.user_settings
		});
	},
	after_refresh: function() {
		this.wrapper.find('.kanban').trigger('after-refresh');
		frappe.kanban_filters[this.list_view.kanban_board_name] =
			this.list_view.filter_list.get_filters();
	},
	should_refresh: function() {
		var to_refresh = this._super();
		if(!to_refresh) {
			to_refresh = this.list_view.last_kanban_board_name !== this.list_view.kanban_board_name;
		}
		return to_refresh;
	},
	init_settings: function() {
		this._super();
		this.filters = this.get_kanban_filters();
	},
	get_kanban_filters: function() {
		frappe.provide('frappe.kanban_filters');

		var board_name = this.list_view.kanban_board_name;
		if (!frappe.kanban_filters[board_name]) {
			var kb = this.meta.__kanban_boards.find(
				board => board.name === board_name
			);
			frappe.kanban_filters[board_name] = JSON.parse(kb.filters || "[]");
		}
		var filters = frappe.kanban_filters[board_name];
		return filters;
	},
	set_defaults: function() {
		this._super();
		this.no_realtime = true;
		this.page_title = __(this.board_name);
	},
	set_kanban_board_filters: function () {
		var me = this;
		var board_name = this.list_view.kanban_board_name;
		frappe.db.get_value('Kanban Board',
			{ name: board_name }, 'filters',
			function (res) {
				var filters = JSON.parse(res.filters || '[]');
				me.list_view.filter_list.clear_filters();
				me.list_view.set_filters(filters);
				me.list_view.run();
			});
	},
	get_header_html: function() {
		return frappe.render_template('list_item_row_head', { main: '', list: this });
	},
	required_libs: [
		'assets/frappe/js/frappe/views/kanban/fluxify.min.js',
		'assets/frappe/js/frappe/views/kanban/kanban_board.js'
	]
});