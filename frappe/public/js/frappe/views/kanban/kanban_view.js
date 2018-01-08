frappe.provide('frappe.views');

frappe.views.KanbanView = class KanbanView extends frappe.views.ListView {
	static load_last_view() {
		const route = frappe.get_route();
		if (route.length === 3) {
			const doctype = route[1];
			const user_settings = frappe.get_user_settings(doctype)['Kanban'] || {};
			if (!user_settings.last_kanban_board) {
				frappe.msgprint({
					title: __('Error'),
					indicator: 'red',
					message: __('Missing parameter Kanban Board Name')
				});
				frappe.set_route('List', doctype, 'List');
				return true;
			}
			route.push(user_settings.last_kanban_board);
			frappe.set_route(route);
			return true;
		}
		return false;
	}

	setup_defaults() {
		super.setup_defaults();
		this.board_name = frappe.get_route()[3];
		this.page_title = this.board_name;
	}

	show() {
		super.show();
		this.save_view_user_settings({
			last_kanban_board: this.board_name
		});
	}

	render() {
		const board_name = this.board_name;
		if(this.kanban && board_name === this.kanban.board_name) {
			this.kanban.update(this.data);
			this.kanban.$kanban_board.trigger('after-refresh');
			return;
		}

		this.kanban = new frappe.views.KanbanBoard({
			doctype: this.doctype,
			board_name: board_name,
			cards: this.data,
			wrapper: this.$result,
			cur_list: this,
			user_settings: this.view_user_settings
		});
		this.kanban.$kanban_board.trigger('after-refresh');
	}

	get required_libs() {
		return [
			'assets/frappe/js/lib/fluxify.min.js',
			'assets/frappe/js/frappe/views/kanban/kanban_board.js'
		];
	}
};
