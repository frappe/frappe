frappe.provide('frappe.ui');

export default class ListFilter {
	constructor({ wrapper, doctype }) {
		Object.assign(this, arguments[0]);
		this.can_add_global = frappe.user.has_role(['System Manager', 'Administrator']);
		this.filters = [];
		this.make();
		this.bind();
		this.refresh();
	}

	make() {
		// init dom
		this.wrapper.html('<li class="input-area"></li>');
		this.$input_area = this.wrapper.find('.input-area');
		this.$list_filters = this.wrapper.find('.list-filters');

		this.filter_input = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Data',
				label: __('Save Filter').toUpperCase(),
				placeholder: __('Filter Name'),
				input_class: 'input-xs'
			},
			parent: this.$input_area,
			render_input: 1,
		});

		$(this.filter_input.label_area).css('font-size', 10);

		this.is_global_input = frappe.ui.form.make_control({
			df: {
				fieldtype: 'Check',
				label: __('Is Global')
			},
			parent: this.$input_area,
			render_input: 1
		});

	}

	bind() {
		this.bind_save_filter();
		this.bind_click_filter();
		this.bind_remove_filter();
	}

	refresh() {
		this.get_list_filters()
			.then(() => {
				const html = this.filters.map(filter => this.filter_template(filter));
				this.wrapper.find('.list-link').remove();
				this.wrapper.append(html);
			});
		this.is_global_input.toggle(false);
		this.filter_input.set_description('');
	}

	filter_template(filter) {
		return `<li class="list-link" data-name="${filter.name}">
			<a style="max-width: 90%;">${filter.filter_name}</a>
			<a class="text-muted pull-right"><span class="remove octicon octicon-x"></span></a>
		</li>`;
	}

	bind_click_filter() {
		this.wrapper.on('click', '.list-link', e => {
			const name = $(e.currentTarget).attr('data-name');
			this.list_view.filter_area.clear()
				.then(() => {
					this.list_view.filter_area.add(this.get_filters_values(name));
				});
		});
	}

	bind_remove_filter() {
		this.wrapper.on('click', '.list-link .remove', e => {
			const $li = $(e.currentTarget).closest('.list-link')
			const name = $li.attr('data-name');
			$li.remove();
			this.remove_filter(name)
				.then(() => this.refresh());
		});
	}

	bind_save_filter() {
		this.filter_input.$input.keydown(frappe.utils.debounce(e => {
			const value = this.filter_input.get_value();
			const has_value = Boolean(value);

			if (e.which === frappe.ui.keyCode['ENTER']) {
				if (!has_value || this.filter_name_exists(value)) return;

				this.filter_input.set_value('');
				this.save_filter(value)
					.then(() => this.refresh());
			} else {
				let help_text = __('Press Enter to save');

				if (this.filter_name_exists(value)) {
					help_text = __('Duplicate Filter Name');
				}

				this.filter_input.set_description(has_value ? help_text : '');

				if (this.can_add_global) {
					this.is_global_input.toggle(has_value);
				}
			}
		}, 300));
	}

	save_filter(filter_name) {
		return frappe.db.insert({
			doctype: 'List Filter',
			reference_doctype: this.list_view.doctype,
			filter_name,
			for_user: this.is_global_input.get_value() ? '' : frappe.session.user,
			filters: JSON.stringify(this.get_current_filters())
		});
	}

	remove_filter(name) {
		if (!name) return;
		return frappe.db.delete_doc('List Filter', name);
	}

	get_filters_values(name) {
		const filter = this.filters.find(filter => filter.name === name);
		return  JSON.parse(filter.filters || '[]');
	}

	get_current_filters() {
		return this.list_view.filter_area.get();
	}

	filter_name_exists(filter_name) {
		return (this.filters || []).find(f => f.filter_name === filter_name);
	}

	get_list_filters() {
		return frappe.db.get_list('List Filter', {
			fields: ['name', 'filter_name', 'for_user', 'filters'],
			filters: { reference_doctype: this.list_view.doctype },
			or_filters: [['for_user', '=', frappe.session.user], ['for_user', '=', '']]
		}).then((filters) => {
			this.filters = filters || [];
		});
	}
}
