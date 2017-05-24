frappe.printTable = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		if(!this.columns)
			this.columns = this.get_columns();
		this.data = this.get_data();
		this.remove_empty_cols();
		this.set_widths();
		this.make();
	},
	get_columns: function() {
		var perms = frappe.perm.get_perm(this.doctype);
		return ['Sr'].concat($.map(frappe.meta.docfield_list[this.tabletype], function(df) {
			return (cint(df.print_hide) || !(perms[df.permlevel] &&
				perms[df.permlevel].read)) ? null : df.fieldname;
		}));
	},
	get_data: function() {
		var children = frappe.get_doc(this.doctype, this.docname)[this.fieldname] || [];

		var data = []
		for(var i=0; i<children.length; i++) {
			data.push(copy_dict(children[i]));
		}
		return data;
	},

	remove_empty_cols: function() {
		var me = this;

		var cols_with_value = [];

		$.each(this.data, function(i, row) {
			$.each(me.columns, function(ci, fieldname) {
				var value = row[fieldname];
				if(value || ci==0) {
					if(cols_with_value.indexOf(ci)===-1) {
						cols_with_value.push(ci);
					}
				}
			});
		});

		var columns = [],
			widths = [],
			head_labels = [];


		// sort by col index, asc
		cols_with_value.sort(function(a, b) { return a - b; });

		// make new arrays to remove empty cols, widths and head labels
		$.each(cols_with_value, function(i, col_idx) {
			columns.push(me.columns[col_idx]);
			me.widths && widths.push(me.widths[col_idx]);
			me.head_labels && head_labels.push(me.head_labels[col_idx]);
		});

		this.columns = columns;
		if(this.widths) this.widths = widths;
		if(this.head_labels) this.head_labels = head_labels;

	},

	make: function() {
		var me = this;
		this.tables = [];
		var table_data = [];
		$.each(this.data, function(i, d) {
			table_data.push(d);
			if(d.page_break) {
				me.add_table(table_data);
				table_data = [];
			}
		});
		if(table_data)
			me.add_table(table_data);
	},

	add_table: function(data) {
		var me = this;
		var wrapper = $("<div>")
		var table = $("<table>").css(this.table_style).appendTo(wrapper);

		var headrow = $("<tr>").appendTo(table);
		$.each(me.columns, function(ci, fieldname) {
			var df = frappe.meta.docfield_map[me.tabletype][fieldname];
			if(me.head_labels) {
				var label = me.head_labels[ci];
			} else {
				var label = df ? df.label : fieldname;
			}
			var td = $("<td>").html(__(label))
				.css(me.head_cell_style)
				.css({"width": me.widths[ci]})
				.appendTo(headrow)

			if(df && in_list(['Float', 'Currency'], df.fieldtype)) {
				td.css({"text-align": "right"});
			}
		});

		$.each(data, function(ri, row) {
			var allow = true;
			if(me.condition) {
				allow = me.condition(row);
			}
			if(allow) {
				var tr = $("<tr>").appendTo(table);

				$.each(me.columns, function(ci, fieldname) {
					if(fieldname.toLowerCase()==="sr")
						var value = row.idx;
					else
						var value = row[fieldname];

					var df = frappe.meta.docfield_map[me.tabletype][fieldname];
					value = frappe.format(value, df, {for_print:true});

					// set formatted value back into data so that modifer can use it
					row[fieldname] = value;

					// modifier is called after formatting so that
					// modifier's changes do not get lost in formatting (eg. 3.45%)
					if(me.modifier && me.modifier[fieldname])
						value = me.modifier[fieldname](row);

					var td = $("<td>").html(value)
						.css(me.cell_style)
						.css({width: me.widths[ci]})
						.appendTo(tr);
				});
			}
		});
		this.tables.push(wrapper)
	},

	set_widths: function() {
		var me = this;
		// if widths not passed (like in standard),
		// get from doctype and redistribute to fit 100%
		if(!this.widths) {
			this.widths = $.map(this.columns, function(fieldname, ci) {
				var df = frappe.meta.docfield_map[me.tabletype][fieldname];
				return df && df.print_width || (fieldname=="Sr" ? 30 : 80);
			});

			var sum = 0;
			$.each(this.widths, function(i, w) {
				sum += cint(w);
			});

			this.widths = $.map(this.widths, function(w) {
				w = (flt(w) / sum * 100).toFixed(0);
				return (w < 5 ? 5 : w) + "%";
			});
		}
	},

	get_tables: function() {
		if(this.tables.length > 1) {
			return $.map(this.tables, function(t) {
				return t.get(0);
			});
		} else {
			return this.tables[0].get(0);
		}
	},

	cell_style: {
		border: '1px solid #999',
		padding: '3px',
		'vertical-align': 'top',
		'word-wrap': 'break-word',
	},

	head_cell_style: {
		border: '1px solid #999',
		padding: '3px',
		'vertical-align': 'top',
		'background-color': '#ddd',
		'font-weight': 'bold',
		'word-wrap': 'break-word',
	},

	table_style: {
		width: '100%',
		'border-collapse': 'collapse',
		'margin-bottom': '10px',
		'margin-top': '10px',
		'table-layout': 'fixed'
	},
})

window.print_table = function print_table(dt, dn, fieldname, tabletype, cols, head_labels, widths, condition, cssClass, modifier) {
	return new frappe.printTable({
		doctype: dt,
		docname: dn,
		fieldname: fieldname,
		tabletype: tabletype,
		columns: cols,
		head_labels: head_labels,
		widths: widths,
		condition: condition,
		cssClass: cssClass,
		modifier: modifier
	}).get_tables();
}
