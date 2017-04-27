
frappe.ui.SimpleList = class SimpleList {
	constructor({
		parent = null,
		columns = [],
		values = [],
		with_checkbox = 0,
		with_remove = 0,

		placeholder = {}	// height, icon, btn-action?

	} = {}) {

		this.columns = columns;
		this.values = values;
		this.with_checkbox = with_checkbox;
		this.with_remove = with_remove;
		this.placeholder = placeholder;

		if(this.with_checkbox && this.with_remove) {
			throw "List cannot have both checkbox and remove button"
		}

		this.prepare_columns();

		this.$wrapper = $(this.get_html());
		$(this.$wrapper).appendTo(parent);
		values.map(value => this.insert_row(value));

		this.bind_events();

	}

	refresh(values) {
		this.$wrapper = $(this.get_html());
		values.map(value => this.insert_row(value));
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
			// if (col.fieldname === undefined) {
			// 	throw 'fieldname must be defined in column ' + col.title;
			// }

			// alignment
			if (col.alignment === 'left') {
				col.alignment = 'flex-start';
			} else if (col.alignment === 'right') {
				col.alignment = 'flex-end';
			}

			return col;
		});

		
	}

	prepare_values() {

	}

	get_html() {
		return `<div class="list-item-table">
			${this.get_header_html()}
		</div>`;
	}

	get_header_html() {
		return `<div class="list-item list-item--head">
			${this.columns.map(
				col => `<div
				class="list-item__content ${col.is_subject ? "list-item__content--flex-2" : ""}"
				style="order: ${col.order}; justify-content: ${col.alignment}; flex: ${col.flex}">
					${ this.with_checkbox && col.is_subject ? this.get_checkbox_html() + col.title : col.title}
					${ col.is_remove_col ? this.get_remove_button_html(1) : "" }
				</div>`
		).join("")}
		</div>`
	}

	get_row_html(value) {
		const subject_col = this.columns.filter(col => col.is_subject)[0];

		const get_cell_html = (col) => {
			let cell_value;

			if (col.fieldtype && col.fieldtype === 'Checkbox') {
				cell_value = this.get_checkbox_html({ name: col.fieldname });
			} else {
				cell_value = value[col.fieldname] || '';
			}

			return `<div
				class="list-item__content ${col.is_subject ? "list-item__content--flex-2" : ""}"
				style="order: ${col.order}; justify-content: ${col.alignment}; flex: ${col.flex}">
				${ this.with_checkbox && col.is_subject
					? this.get_checkbox_html({ name: 'list-row-check'}) + cell_value : cell_value}
				${ col.is_remove_col ? this.get_remove_button_html() : "" }
			</div>`
		}

		return `<div class="list-item-container" data-item-name="${value[subject_col.fieldname]}">
			<div class="list-item">
				${this.columns.map(get_cell_html).join("")}
			</div>
		</div>`;
	}

	get_checkbox_html({ name = '' } = {}) {
		return `<input data-name=${name} type="checkbox"/>`;
	}

	get_remove_button_html(hidden = 0) {
		return `
			<button class="btn btn-default btn-xs text-muted item-remove" style="${hidden ? 'opacity: 0': ''}">
				<span class="fa fa-remove"></span>
			</button>`;
	}

	insert_row(value) {
		this.$wrapper.append(this.get_row_html(value));
	}

	remove_row(item_name) {
		this.$wrapper.find(`[data-item-name="${item_name}"]`).remove();
	}

	bind_events() {
		this.$wrapper.on('click', '.list-item-container', function (e) {
			var $item = $(this);
			var item_name = $item.attr('data-item-name');
			var $target = $(e.target);

			if ($target.is('.item-remove, .fa-remove')) {
				$item.remove();
			}
		});

		this.$wrapper.on('click', '.list-item--head :checkbox', (e) => {
			this.$wrapper.find('.list-item-container [data-name="list-row-check"]')
				.prop("checked", ($(e.target).is(':checked')));
		});

	}

	get_values() {
		return this.$wrapper.find('.list-item-container').map(function() {
			$(this).attr('data-item-name');
		}).get();
	}

	get_checked_values() {
		return this.$wrapper.find('.list-item-container').map(function() {
			if ($(this).find('.list-row-check:checkbox:checked').length > 0 ) {
				return $(this).attr('data-item-name');
			}
		}).get();
	}

	remove_checked_rows() {
		this.get_checked_values().map(item_name => this.remove_row(item_name));
	}

}