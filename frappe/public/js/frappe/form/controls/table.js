import Grid from '../grid';

frappe.ui.form.ControlTable = frappe.ui.form.Control.extend({
	make: function() {
		this._super();

		// add title if prev field is not column / section heading or html
		this.grid = new Grid({
			frm: this.frm,
			df: this.df,
			perm: this.perm || (this.frm && this.frm.perm) || this.df.perm,
			parent: this.wrapper
		});
		if(this.frm) {
			this.frm.grids[this.frm.grids.length] = this;
		}

		// description
		if(this.df.description) {
			$('<p class="text-muted small">' + __(this.df.description) + '</p>')
				.appendTo(this.wrapper);
		}
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
			clipboardData = event.clipboardData || window.clipboardData || event.originalEvent.clipboardData;
			pastedData = clipboardData.getData('Text');
			if (!pastedData) return;
			var data = frappe.utils.csv_to_array(pastedData,'\t');
			if (data.length === 1 & data[0].length === 1) return;
			if (data.length > 100){
				data = data.slice(0, 100);
				frappe.msgprint('for performance, only the first 100 rows processed!');
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
				});
				return fieldname;
			}
			if (get_field(data[0][0])){ // for raw data with column header
				$.each(data[0], (ci, column)=>{fieldnames.push(get_field(column));});
				data.shift();
			}
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
			});
			frappe.hide_progress();
			return false; // Prevent the default handler from running.
		})		
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
		return true
	}
});
