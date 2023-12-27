/**
 * @param {frappe.ui.form.Layout} layout
 * @param {import('./link_catalog_common').CatalogOptions} options
 */
export function getLayoutAdapter(layout, options) {
	if (options.table_fieldname) {
		return new LayoutAdapterTable(layout, options);
	} else {
		return new LayoutAdapterField(layout, options);
	}
}

export class BaseLayoutAdapter {
	/**
	 * @param {frappe.ui.form.Layout} layout
	 * @param {import('./link_catalog_common').CatalogOptions} options
	 */
	constructor(layout, options) {
		this.layout = layout;
		this.options = options;
	}

	get parent_doc() {
		return this.layout.doc;
	}

	get link_fieldname() {
		return this.options.link_fieldname;
	}

	get quantity_fieldname() {
		return this.options.quantity_fieldname;
	}

	// Methods to be implemented by subclasses
	upsert(selected, values) {
		throw new Error("Not implemented");
	}

	remove(selected) {
		throw new Error("Not implemented");
	}

	grab_quantity(selected) {
		throw new Error("Not implemented");
	}
}

export class LayoutAdapterField extends BaseLayoutAdapter {
	set_values(values) {
		if (this.layout.set_values) {
			this.layout.set_values(values);
		} else {
			this.layout.set_value(values);
		}
	}

	upsert(selected, values) {
		// selected is ignored because we are not in a table
		this.set_values(values); // Assuming that values is a dict
	}

	remove(selected) {
		const values = {
			[this.link_fieldname]: null,
			[this.quantity_fieldname]: null,
		};
		this.set_values(values);
	}

	grab_quantity(selected) {
		if (!this.quantity_fieldname) {
			return this._get_value(this.link_fieldname) ? 1 : 0;
		}
		return this._get_value(this.quantity_fieldname) ?? 0;
	}

	_get_value(fieldname) {
		if (this.layout.get_value) {
			return this.layout.get_value(this.quantity_fieldname);
		} else {
			return this.parent_doc?.[this.quantity_fieldname];
		}
	}
}

export class LayoutAdapterTable extends BaseLayoutAdapter {
	get child_doctype() {
		return frappe.meta.get_docfield(this.parent_doc.doctype, this.options.table_fieldname)
			.options;
	}

	get_initial_values() {
		return {};
	}

	get_grid() {
		return this.layout.get_field(this.options.table_fieldname).grid;
	}

	async upsert(selected, values) {
		const rows = Array.from(this.find_rows(selected));

		if (rows.length === 0) {
			Object.assign(values, this.get_initial_values());
			const row = this.get_grid().add_new_row();
			await frappe.model.set_value(row.doctype, row.name, values);
		} else {
			const expected_qty = this.quantity_fieldname ? values[this.quantity_fieldname] : 1;
			const qtys = this._generate_quantities(selected, expected_qty, rows);
			for (const [row, qty] of qtys) {
				if (qty === 0) {
					this._remove_row(row);
				} else {
					delete row.__removed;
					await frappe.model.set_value(
						row.doctype,
						row.name,
						this.quantity_fieldname,
						qty
					);
				}
			}
		}
	}

	_remove_row(row) {
		if (!this.quantity_fieldname) {
			row.__removed = true;
		}
		const grid = this.get_grid();
		const row_form = grid.get_row(row.name);
		if (row_form) {
			row_form.remove();
		} else {
			// Row form is not available when the row is not visible.
			const table = grid.get_data();
			const oldIndex = table.findIndex((r) => r.name == row.name);
			if (oldIndex !== -1) {
				table.splice(oldIndex, 1);
			}

			// renum idx
			for (let i = 0; i < table.length; i++) {
				table[i].idx = i + 1;
			}

			grid.refresh();
			this.layout.dirty?.();
			this.layout.script_manager?.trigger?.(
				this.options.table_fieldname + "_delete",
				this.child_doctype
			);
		}
	}

	*_generate_quantities(selected, total_quantity, _rows = null) {
		const rows = _rows || Array.from(this.find_rows(selected));
		let running_total_qty = 0;
		for (let i = 0; i < rows.length; i++) {
			const row = rows[i];
			const current_qty = this.quantity_fieldname ? row[this.quantity_fieldname] : 1;
			const next_running_total_qty = running_total_qty + current_qty;
			const too_little = next_running_total_qty < total_quantity;

			// If the last row doesn't have enough quantity, we need to increase its quantity.
			// The last row is the only row that can have its quantity increased.
			if (i === rows.length - 1 && too_little) {
				yield [row, total_quantity - running_total_qty];
				break;
			}

			// If a non-last row has not enough quantity, we can skip it.
			// We don't need to increase its quantity because we will increase the last row's quantity.
			if (too_little) {
				running_total_qty = next_running_total_qty;
				continue;
			}

			// If any row will make the total quantity too much, we need to decrease its quantity.
			// All subsequent rows will have to be zeroed out.
			// This is done by setting running_total_qty to total_quantity.
			if (!too_little) {
				const delta = total_quantity - running_total_qty;
				yield [row, delta];
				running_total_qty = total_quantity;
			}
		}
	}

	remove(selected) {
		for (const row of this.find_rows(selected)) {
			this._remove_row(row);
		}
	}

	*find_rows(selected) {
		if (!selected) {
			return [];
		}
		for (const row of this.parent_doc[this.options.table_fieldname]) {
			if (row?.[this.link_fieldname] === selected.name) {
				yield row;
			}
		}
	}

	grab_quantity(selected) {
		if (!this.quantity_fieldname) {
			return Array.from(this.find_rows(selected)).filter((x) => !x.__removed).length;
		}

		let total_qty = 0;
		for (const row of this.find_rows(selected)) {
			if (row.__removed) {
				continue;
			}
			const qty = row?.[this.quantity_fieldname] ?? 0;
			if (typeof qty === "number") {
				total_qty += qty;
			}
		}
		return total_qty;
	}
}
