
frappe.ui.SimpleList = class SimpleList {
	constructor({
		parent = null,
		columns = [],
		values = [],
		with_checkbox = 0
	} = {}) {

		this.columns = columns;
		this.values = values;
		this.with_checkbox = with_checkbox;
		debugger;
		this.prepare_columns();

		this.$wrapper = $(this.get_html());

		$(this.$wrapper).appendTo(parent);

		this.values.map(value => this.insert_row(value));
	}

	get_html() {
		return `<div class="list-item-table">
			<div class="list-item list-item--head">
				${this.columns.map(
					col => `<div
					class="list-item__content ${col.is_subject ? "list-item__content--flex-2" : ""}"
					style="order: ${col.order}; justify-content: ${col.alignment}">
						${col.title}
					</div>`
			)}
			</div>
		</div>`;
	}

	prepare_columns() {
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
			if (col.fieldname === undefined) {
				throw 'fieldname must be defined in column ' + col.title;
			}

			// alignment
			if (col.alignment === 'left') {
				col.alignment = 'flex-start';
			} else if (col.alignment === 'right') {
				col.alignment = 'flex-end';
			}

			// checkboxes
			if (this.with_checkbox && col.is_subject) {
				col.title = this.get_checkbox_html() + col.title;
			}
			return col;
		});
	}

	prepare_values() {
		// this.values = this.values.map((value, i) => {
		// 	if ()
		// })
	}

	get_checkbox_html() {
		return '<input class="list-row-check" type="checkbox"/>';
	}

	get_row_html(value) {
		return `<div class="list-item-container">
			<div class="list-item">
				${this.columns.map(
					col => `<div
					class="list-item__content ${col.is_subject ? "list-item__content--flex-2" : ""}"
					style="order: ${col.order}; justify-content: ${col.alignment}">
						${value[col.fieldname]}
					</div>`
				)}
			</div>
		</div>`;
	}

	insert_row(value) {
		this.$wrapper.append(this.get_row_html(value));
	}
}