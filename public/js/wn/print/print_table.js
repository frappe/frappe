// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//

wn.provide("wn.print");

// opts: 
// doctype (parent)
// docname
// tabletype
// fieldname
// show_all = false;

wn.print.Table = Class.extend({
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
		return ['Sr'].concat($.map(wn.meta.docfield_list[this.tabletype], function(df) {
			return cint(df.print_hide) ? null : df.fieldname;
		}));
	},
	get_data: function() {
		var children = wn.model.get(this.tabletype, {
			parent:this.docname, parenttype:this.doctype, parentfield: this.fieldname})
				
		var data = []
		for(var i=0; i<children.length; i++) {
			data.push(copy_dict(children[i]));
		}
		return data;
	},
	
	remove_empty_cols: function() {
		var cols_with_value = [];
		var widths = [];
		var head_labels = [];
		var me = this;
		
		$.each(this.data, function(i, row) {
			$.each(me.columns, function(ci, fieldname) {
				var value = row[fieldname];
				if((value!==null && value!=="") || ci==0) {
					if(!in_list(cols_with_value, fieldname)) {
						cols_with_value.push(fieldname);

						// also prepare a new list of widths and head labels
						me.widths && widths.push(me.widths[ci]);
						me.head_labels && head_labels.push(me.head_labels[ci]);
					}
				}
			});
		});
		
		this.columns = cols_with_value;
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
			if(me.head_labels) {
				var label = me.head_labels[ci];
			} else {
				var df = wn.meta.docfield_map[me.tabletype][fieldname];
				var label = df ? df.label : fieldname;
			}
			var td = $("<td>").html(label)
				.appendTo(headrow)
				.css(me.head_cell_style)
				.css({"width": me.widths[ci] + "%"});

			if(ci==0) {
				td.css({"min-width": "30px"});
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
					if(ci==0) 
						var value = row.idx;
					else
						var value = row[fieldname];

					if(me.modifier && me.modifier[fieldname])
						value = me.modifier[fieldname](row);
					
					var df = wn.meta.docfield_map[me.tabletype][fieldname];
					value = wn.form.get_formatter(
						df && df.fieldtype || "Data")(value);

					$("<td>").html(value)
						.css(me.cell_style)
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
				df = wn.meta.docfield_map[me.tabletype][fieldname];
				return df && df.width || (fieldname=="Sr" ? 30 : 80);
			});
			
			var sum = 0;
			$.each(this.widths, function(i, w) {
				sum += cint(w);
			});

			this.widths = $.map(this.widths, function(w) {
				return (flt(w) / sum * 100).toFixed(0);
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

function print_table(dt, dn, fieldname, tabletype, cols, head_labels, widths, condition, cssClass, modifier, hide_empty) {
	return new wn.print.Table({
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
