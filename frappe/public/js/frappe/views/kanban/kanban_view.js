frappe.provide('frappe.views');

frappe.views.KanbanView = frappe.views.ListRenderer.extend({
	name: 'Kanban',
	render_view: function(values) {
		this.kanban = new frappe.views.KanbanBoard({
			doctype: this.doctype,
			board_name: this.board_name,
			cards: values,
			wrapper: this.wrapper,
			cur_list: this.list_view,
			user_settings: this.user_settings
		});
	},
	set_defaults: function() {
		this._super();
		this.no_realtime = true;
		this.page_title = __(this.board_name);
	},
	before_refresh: function() {
		// if(this.list_view.current_view === 'Kanban') {
		// 	// this.
		// }
	},
	get_header_html: function() {
		return frappe.render_template('list_item_row_head', { main: '', list: this });
	},
	required_libs: [
		'assets/frappe/js/frappe/views/kanban/fluxify.min.js',
		'assets/frappe/js/frappe/views/kanban/kanban_board.js'
	]
});