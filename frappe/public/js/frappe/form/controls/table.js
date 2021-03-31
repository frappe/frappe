import Grid from '../grid';

frappe.ui.form.ControlTable = frappe.ui.form.Control.extend({
	make: function() {
		this._super();

		// add title if prev field is not column / section heading or html
		this.grid = new Grid({
			frm: this.frm,
			df: this.df,
			perm: this.perm || (this.frm && this.frm.perm) || this.df.perm,
			parent: this.wrapper,
			control: this
		});
		if(this.frm) {
			this.frm.grids[this.frm.grids.length] = this;
		}
<<<<<<< HEAD
		this.$wrapper.on('paste',':text', function(e) {
			var cur_table_field =$(e.target).closest('div [data-fieldtype="Table"]').data('fieldname');
			var cur_field = $(e.target).data('fieldname');
			var cur_grid= cur_frm.get_field(cur_table_field).grid;
			var cur_grid_rows = cur_grid.grid_rows;
			var cur_doctype = cur_grid.doctype;
			var cur_row_docname =$(e.target).closest('div .grid-row').data('name');
			var row_idx = locals[cur_doctype][cur_row_docname].idx;
			var clipboardData, pastedData;
			// Get pasted data via clipboard API
			clipboardData = e.clipboardData || window.clipboardData || e.originalEvent.clipboardData;
			pastedData = clipboardData.getData('Text');
			if (!pastedData) return;
			var data = frappe.utils.csv_to_array(pastedData,'\t');
			if (data.length === 1 & data[0].length === 1) return;
			if (data.length > 100){
				data = data.slice(0, 100);
				frappe.msgprint(__('For performance, only the first 100 rows were processed.'));
			}
			var fieldnames = [];
			var get_field = function(name_or_label){
				var fieldname;
				$.each(cur_grid.meta.fields,(ci,field)=>{
					name_or_label = name_or_label.toLowerCase()
					if (field.fieldname.toLowerCase() === name_or_label ||
						(field.label && field.label.toLowerCase() === name_or_label)){
						  fieldname = field.fieldname;
						  return false;
						}
=======

		this.$wrapper.on('paste', ':text', e => {
			const table_field = this.df.fieldname;
			const grid = this.grid;
			const grid_pagination = grid.grid_pagination;
			const grid_rows = grid.grid_rows;
			const doctype = grid.doctype;
			const row_docname = $(e.target).closest('.grid-row').data('name');
			const in_grid_form = $(e.target).closest('.form-in-grid').length;

			let clipboard_data = e.clipboardData || window.clipboardData || e.originalEvent.clipboardData;
			let pasted_data = clipboard_data.getData('Text');

			if (!pasted_data || in_grid_form) return;

			let data = frappe.utils.csv_to_array(pasted_data, '\t');

			if (data.length === 1 && data[0].length === 1) return;

			let fieldnames = [];
			// for raw data with column header
			if (this.get_field(data[0][0])) {
				data[0].forEach(column => {
					fieldnames.push(this.get_field(column));
>>>>>>> 5688b3e7d9... fix: Miscellaneous changes (#12730)
				});
				return fieldname;
			}
			if (get_field(data[0][0])){ // for raw data with column header
				$.each(data[0], (ci, column)=>{fieldnames.push(get_field(column));});
				data.shift();
			}
<<<<<<< HEAD
			else{ // no column header, map to the existing visible columns
				var visible_columns = cur_grid_rows[0].get_visible_columns();
				var find;
				$.each(visible_columns, (ci, column)=>{
					if (column.fieldname === cur_field) find = true;
					find && fieldnames.push(column.fieldname);
				})
			}
			$.each(data, function(i, row) {
				var blank_row = true;
				$.each(row, function(ci, value) {
					if(value) {
						blank_row = false;
						return false;
					}
				});
				if(!blank_row) {
					if (row_idx > cur_frm.doc[cur_table_field].length){
						cur_grid.add_new_row();
					}
					var cur_row = cur_grid_rows[row_idx - 1];
					row_idx ++;
					var row_name = cur_row.doc.name;
					$.each(row, function(ci, value) {
						if (fieldnames[ci]) frappe.model.set_value(cur_doctype, row_name, fieldnames[ci], value);
					});
					frappe.show_progress(__('Processing'), i, data.length);
				}
=======

			let row_idx = locals[doctype][row_docname].idx;
			let data_length = data.length;
			data.forEach((row, i) => {
				setTimeout(() => {
					let blank_row = !row.filter(Boolean).length;
					if (!blank_row) {
						if (row_idx > this.frm.doc[table_field].length) {
							this.grid.add_new_row();
						}

						if (row_idx > 1 && (row_idx - 1) % grid_pagination.page_length === 0) {
							grid_pagination.go_to_page(grid_pagination.page_index + 1);
						}

						const row_name = grid_rows[row_idx - 1].doc.name;
						row.forEach((value, data_index) => {
							if (fieldnames[data_index]) {
								frappe.model.set_value(doctype, row_name, fieldnames[data_index], value);
							}
						});
						row_idx++;
						if (data_length >= 10) {
							let progress = i + 1;
							frappe.show_progress(__('Processing'), progress, data_length, null, true);
						}
					}
				}, 0);
>>>>>>> 5688b3e7d9... fix: Miscellaneous changes (#12730)
			});
			frappe.hide_progress();
			return false; // Prevent the default handler from running.
		});
	},
	refresh_input: function() {
		this.grid.refresh();
	},
	get_value: function() {
		if(this.grid) {
			return this.grid.get_data();
		}
	},
	set_input: function( ) {
		//
	},
	validate: function() {
		return this.get_value();
	},
	check_all_rows() {
		this.$wrapper.find('.grid-row-check')[0].click();
	}
});
