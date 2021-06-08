// Simpler table implementation where values are edited in a dialog
// Used in web form

frappe.ui.form.ControlTableDialog = class ControlTableDialog extends frappe.ui.form.Control {
	make() {
		this._super();
		frappe.utils.bind_actions_with_object(this.$wrapper, this);

		// used to store values
		this.rows = [];

		let header_fields = this.get_header_fields();
		this.$wrapper.html(`
			<div class="form-group">
				<div class="clearfix">
					<label class="control-label ${this.df.reqd ? 'reqd': ''}">${this.df.label}</label>
				</div>
				<div class="table-responsive table-dialog">
					<table class="table">
						<thead>
							<tr>
								<th>#</th>
								${header_fields.map(df => `<th scope="col">${df.label}</th>`).join("")}
								<th></th>
							</tr>
						</thead>
						<tbody></tbody>
					</table>
				</div>
				<div><button class="btn btn-xs btn-default" data-action="add_row">Add Row</button></div>
			</div>
		`);
		this.update_table();
	}

	add_row() {
		this.edit_in_dialog().then(values => {
			this.rows.push(values);
			this.update_table();
		});
	}

	edit_row(e, $btn) {
		let index = parseInt($btn.data("index"));
		let row = this.rows[index];
		this.edit_in_dialog(row).then(values => {
			this.rows[index] = values;
			this.update_table();
		});
	}

	delete_row(e, $btn) {
		let index = parseInt($btn.data("index"));
		this.rows = this.rows.filter((row, i) => i != index);
		this.update_table();
	}

	edit_in_dialog(initial_values = {}) {
		let fields = this.get_table_fields().filter(
			df => df.fieldname != "name"
		);
		return new Promise(resolve => {
			let d = new frappe.ui.Dialog({
				title: __("Add Row"),
				fields,
				primary_action: values => {
					resolve(values);
					d.hide();
				}
			});
			d.set_values(initial_values);
			d.show();
		});
	}

	update_table() {
		let html = "";
		if (this.rows.length) {
			html = this.rows
				.map((row, i) => this.get_row_html(row, i))
				.join("");
		} else {
			let header_fields = this.get_header_fields();
			html = `<tr>
				<td class="text-center" colspan="${header_fields.length + 2}">
					${__("No data")}
				</td>
			</tr>`;
		}
		this.$wrapper.find("tbody").html(html);
	}

	get_row_html(row, i) {
		let header_fields = this.get_header_fields();
		let format_value = df => frappe.format(row[df.fieldname], df, {}, row);
		return `
			<tr>
				<th>${i + 1}</th>
				${header_fields.map(df => `<td>${format_value(df)}</td>`).join("")}
				<td class="text-right">
					<button data-action="edit_row" data-index="${i}" class="btn btn-xs btn-default">Edit</button>
					<button data-action="delete_row" data-index="${i}" class="btn btn-xs btn-default">Delete</button>
				</td>
			</tr>
		`;
	}

	get_table_fields() {
		if (this.df.options) {
			let meta = frappe.get_meta(this.df.options);
			if (meta) {
				return meta.fields;
			}
		}
		return this.df.table_fields || [];
	}

	get_header_fields() {
		let fields = this.get_table_fields();
		let header_fields = fields.filter(df => df.header);
		if (!header_fields.length) {
			header_fields = fields.filter(df => df.in_list_view);
		}
		return header_fields.slice(0, 4);
	}

	validate(value) {
		return value;
	}

	set_input(value) {
		this.rows = value;
		this.update_table();
	}

	get_value() {
		return this.rows;
	}
};
