frappe.provide('frappe.views');

frappe.views.KanbanView = frappe.views.ListRenderer.extend({
	name: 'Kanban',
	render_view: function(values) {
		var board_name = this.list_view.kanban_board_name;
		console.log(board_name)
		this.kanban = new frappe.views.KanbanBoard({
			doctype: this.doctype,
			board_name: board_name,
			cards: values,
			wrapper: this.wrapper,
			cur_list: this.list_view,
			user_settings: this.user_settings
		});
	},
	before_refresh: function() {
		if(this.list_view.last_kanban_board_name !== this.kanban_board_name) {
			this.set_kanban_board_filters();
			this.list_view.dirty = false;
		}
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