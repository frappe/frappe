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
		this.view_name = 'Kanban';
		this.board_name = frappe.get_route()[3];
		this.page_title = this.board_name;
		this.card_meta = this.get_card_meta();

		return this.get_board()
			.then(() => {
				this.filters = this.board.filters_array;
			});
	}

	get_board() {
		return frappe.db.get_doc('Kanban Board', this.board_name)
			.then(board => {
				this.board = board;
				this.board.filters_array = JSON.parse(this.board.filters || '[]');
			});
	}

	setup_view() {

	}

	set_fields() {
		super.set_fields();
		this._add_field(this.card_meta.title_field);
	}

	before_render() {
		this.save_view_user_settings({
			last_kanban_board: this.board_name
		});

		frappe.call({
			method: 'frappe.desk.doctype.kanban_board.kanban_board.save_filters',
			args: {
				board_name: this.board_name,
				filters: this.filter_area.get()
			}
		}).then(function() {
			frappe.show_alert({
				message: __('Filters saved'),
				indicator: 'green'
			}, 0.5);
		});
	}

	render() {
		const board_name = this.board_name;
		if(this.kanban && board_name === this.kanban.board_name) {
			this.kanban.update(this.data);
			return;
		}

		this.kanban = new frappe.views.KanbanBoard({
			doctype: this.doctype,
			board: this.board,
			board_name: board_name,
			cards: this.data,
			card_meta: this.card_meta,
			wrapper: this.$result,
			cur_list: this,
			user_settings: this.view_user_settings
		});
	}

	get_card_meta() {
		var meta = frappe.get_meta(this.doctype);
		var doc = frappe.model.get_new_doc(this.doctype);
		var title_field = null;
		var quick_entry = false;

		if(this.meta.title_field) {
			title_field = frappe.meta.get_field(this.doctype, this.meta.title_field);
		}

		this.meta.fields.forEach(function(df) {
			const is_valid_field =
				in_list(['Data', 'Text', 'Small Text', 'Text Editor'], df.fieldtype)
					&& !df.hidden;

			if (is_valid_field && !title_field) {
				// can be mapped to textarea
				title_field = df;
			}
		});

		// quick entry
		var mandatory = meta.fields.filter(function(df) {
			return df.reqd && !doc[df.fieldname];
		});

		if(mandatory.some(df => df.fieldtype === 'Table') || mandatory.length > 1) {
			quick_entry = true;
		}

		if(!title_field) {
			title_field = frappe.meta.get_field(this.doctype, 'name');
		}

		return {
			quick_entry: quick_entry,
			title_field: title_field
		};
	}

	get required_libs() {
		return [
			'assets/frappe/js/lib/fluxify.min.js',
			'assets/frappe/js/frappe/views/kanban/kanban_board.js'
		];
	}
};
