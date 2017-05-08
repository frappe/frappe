
frappe.ui.SimpleList = class SimpleList {
	constructor({
		parent = null,
		columns = [],
		values = [],
		with_checkbox = 0,
		with_remove = 0,
		on_change = {},
		empty_state = null,

		placeholder = {}	// height, icon, btn-action?

	} = {}) {

		Object.assign(this, {
			parent,
			columns,
			values,
			with_checkbox,
			with_remove,
			on_change,
			empty_state
		});

		if(this.with_checkbox && this.with_remove) {
			throw "List cannot have both checkbox and remove button";
		}

		this.prepare_columns();
		this.prepare_values();
		this.refresh();
		this.bind_events();

	}

	prepare_columns() {
		if (this.with_remove) {
			this.columns.push({
				title: '',
				is_remove_col: 1,
				order: 99,
				flex: 0
			});
		}

		this.columns = this.columns.map((col, i) => {
			if (col.is_subject === undefined && i === 0) {
				col.is_subject = 1;
			}
			if (col.order === undefined) {
				col.order = 0;
			}
			if (col.alignment === undefined) {
				col.alignment = 'left';
			}

			// alignment
			if (col.alignment === 'left') {
				col.alignment = 'flex-start';
			} else if (col.alignment === 'right') {
				col.alignment = 'flex-end';
			}

			return col;
		});

		// subject column
		const subject_col = this.columns.filter(col => col.is_subject);
		if(subject_col.length > 1) {
			throw 'Only one subject column is allowed';
		}
		this.subject_col = subject_col[0];
	}

	prepare_values() {
		this.values = this.values.map(value => {
			value.__name = value[this.subject_col.fieldname];
			return value;
		});
	}

	get_html() {
		return `<div class="list-item-table">
			${this.get_header_html()}
			<div class="empty-state">
				${__("No Items")}
			</div>
		</div>`;
	}

	get_header_html() {
		return `<div class="list-item list-item--head">
			${this.columns.map(
				col => `<div
				class="list-item__content ${col.is_subject ? "list-item__content--flex-2" : ""}"
				style="order: ${col.order}; justify-content: ${col.alignment}; flex: ${col.flex}">
					${ this.with_checkbox && col.is_subject ? this.get_checkbox_html({ style: "margin-right: 5px"}) + col.title : col.title}
					${ col.is_remove_col ? this.get_remove_button_html(1) : "" }
				</div>`
		).join("")}
		</div>`
	}

	get_row_html(value) {

		const get_cell_html = (col) => {
			let cell_value;

			if (col.fieldtype && col.fieldtype === 'Checkbox') {
				cell_value = this.get_checkbox_html({
					name: value.__name,
					fieldname: col.fieldname
				});
			} else {
				cell_value = value[col.fieldname] || '';
			}

			if (this.with_checkbox && col.is_subject) {
				cell_value = this.get_checkbox_html({
					name: value.__name,
					fieldname: 'list-row-check',
					style: 'margin-right: 5px'
				}) + cell_value;
			}

			return `<div
				class="list-item__content ${col.is_subject ? "list-item__content--flex-2" : ""}"
				style="order: ${col.order}; justify-content: ${col.alignment}; flex: ${col.flex}">
				${ cell_value }
				${ col.is_remove_col ? this.get_remove_button_html() : "" }
			</div>`
		}

		return `<div class="list-item-container" data-name="${value.__name}">
			<div class="list-item">
				${this.columns.map(get_cell_html).join("")}
			</div>
		</div>`;
	}

	get_checkbox_html({ name = '', fieldname = '', style = '' } = {}) {
		return `
			<input
				type="checkbox"
				${name ? `data-name="${name}"`: ""}
				${fieldname ? `data-fieldname="${fieldname}"`: ""}
				${style ? `style="${style}"`: ""}
				data-fieldname={}
			/>`;
	}

	get_remove_button_html(hidden = 0) {
		return `
			<button class="btn btn-default btn-xs text-muted item-remove" style="${hidden ? 'opacity: 0': ''}">
				<span class="fa fa-remove"></span>
			</button>`;
	}

	refresh() {
		if (!this.$wrapper) {
			this.$wrapper = $(this.get_html());
			this.$wrapper.appendTo(this.parent);
		} else {
			this.$wrapper
				.find('.list-item-container[data-name]')
				.remove();
		}

		if (this.values.length > 0) {
			// hide empty state
			this.$wrapper.find('.empty-state').hide();

			this.values.map(value => this.insert_row(value));
		} else {
			// show empty state
			if (this.empty_state && $.isFunction(this.empty_state)) {
				this.empty_state();
			} else {
				this.$wrapper.find('.empty-state').show();
			}
		}
	}

	add_row(value) {
		this.values.push(value);
		this.refresh();
	}

	remove_row(name) {
		this.values = this.values.filter(
			value => value.__name !== name
		);
		this.refresh();
	}

	insert_row(value) {
		this.$wrapper.append(this.get_row_html(value));
	}

	bind_events() {
		var me = this;

		// click events
		this.$wrapper.on('click', '.list-item-container', function (e) {
			const $item = $(this);
			const item_name = $item.attr('data-name');
			const $target = $(e.target);

			if ($target.is('.item-remove, .fa-remove')) {
				me.remove_row(item_name);
			}
		});

		// select / deselect all
		this.$wrapper.on('click', '.list-item--head :checkbox', (e) => {
			this.$wrapper
				.find('.list-item-container [data-fieldname="list-row-check"]')
				.prop("checked", ($(e.target).is(':checked')));
		});

		// change events on checkboxes
		this.$wrapper.on('change', '.list-item-container :checkbox', function (e) {
			const $checkbox = $(this);
			const name = $checkbox.attr('data-name');
			const fieldname = $checkbox.attr('data-fieldname');
			if(fieldname === 'list-row-check') return;

			const is_checked = $checkbox.is(':checked');

			// update values array
			me.values = me.values.map(value => {
				if(value.__name === name) {
					value[fieldname] = is_checked
				}
				return value;
			});

			const handler = me.on_change[fieldname];
			if (handler && $.isFunction(handler)) {
				handler.apply(null, [name, is_checked]);
			}
		});

	}

	get_values() {
		return this.values;
	}

	get_checked_values() {
		const checked_names = this.$wrapper
			.find('.list-item-container [data-fieldname="list-row-check"]:checked')
			.map((i, list_item) => $(list_item).attr('data-name'))
			.toArray();

		return this.values.filter(
			value => checked_names.includes(value.__name)
		);
	}

	remove_checked_rows() {
		this.get_checked_values()
			.map(value => this.remove_row(value.__name));
	}

}