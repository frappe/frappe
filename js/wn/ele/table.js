// table class
// opts: table_style, cell_widths, cell_style
wn.ele.Table = function(parent, rows, cols, opts) {
	$.extend(this, opts);

	if(!table_style) table_style = {};
	table_style.borderCollapse = collapse;

	$.extend(this, {
		make: function() {
			this.table = wn.add(parent, 'table');
			wn.style(this.table, this.table_style);
			for(var i=0; i<rows; i++)
				this.make_row(i);
		},
		
		make_row: function(row) {
			var r = this.table.insertRow(row);
			for(var i=0; i<cols; i++) {
				var cell = r.insertCell(i);
				
				// set width
				if(row==0 && this.cell_widths && this.cell_widths[i]) {
					cell.style.width = widths[i];
				}
				
				if(this.cell_style) wn.style(cell, this.cell_style);
			}
		},
		
		append_row: function(at, style) {
			var t = this.table;
			var r = t.insertRow(at ? at : t.rows.length);
			if(t.rows.length>1) {
				for(var i=0;i<t.rows[0].cells.length;i++) {
					var c = r.insertCell(i);
					if(style) $y(c, style);
				}
			}
			return r;
		}
	});
	
}

// bc

function make_table(parent, nr, nc, table_width, widths, cell_style, table_style) {
	if(!table_style) table_style = {};
	table_style.width = width;
	
	return new wn.ele.Table(parent, nr, nc, {
		table_style: table_style,
		cell_widths: widths,
		cell_style: cell_style;
	}).table;
}

