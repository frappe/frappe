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

// default print style
_p.def_print_style_body = "html, body, div, span, td { font-family: Arial, Helvetica; font-size: 12px; }" + "\npre { margin:0; padding:0;}"	

_p.def_print_style_other = "\n.simpletable, .noborder { border-collapse: collapse; margin-bottom: 10px;}"
	+"\n.simpletable td {border: 1pt solid #000; vertical-align: top; padding: 2px; }"
	+"\n.noborder td { vertical-align: top; }"

_p.go = function(html) {
	var d = document.createElement('div')
	d.innerHTML = html
	$(d).printElement();
}

_p.preview = function(html) {
	var w = window.open('');
	if(!w) return;
	w.document.write(html)
	w.document.close();
}


// _p can be referenced as this inside $.extend
$.extend(_p, {
	show_dialog: function() {
		if(!_p.dialog) {
			_p.make_dialog();	
		}
		_p.dialog.show();
	},
	
	make_dialog: function() {
		// Prepare Dialog Box Layout		
		var d = new Dialog(
			360, // w
			140, // h
			'Print Formats', // title
			[ // content
				['HTML', 'Select'],
				['Check', 'No Letterhead'],
				['HTML', 'Buttons']				
			]);
		//d.widgets['No Letterhead'].checked = 1;
		
		// Print Button
		$btn(d.widgets.Buttons, 'Print', function() {
				_p.build(
					sel_val(cur_frm.print_sel), // fmtname
					_p.go, // onload
					d.widgets['No Letterhead'].checked // no_letterhead
				);
			},
			{
					cssFloat: 'right',
					marginBottom: '16px',
					marginLeft: '7px'
			}, 'green');
		
		// Print Preview
		$btn(d.widgets.Buttons, 'Preview', function() {
				_p.build(
					sel_val(cur_frm.print_sel), // fmtname
					_p.preview, // onload
					d.widgets['No Letterhead'].checked // no_letterhead
				);
			},
			{
				cssFloat: 'right',
				marginBottom: '16px'			
			}, '');
		
		// Delete previous print format select list and Reload print format list from current form
		d.onshow = function() {
			var c = _p.dialog.widgets['Select'];
			if(c.cur_sel && c.cur_sel.parentNode == c) {
				c.removeChild(c.cur_sel);
			}
			c.appendChild(cur_frm.print_sel);
			c.cur_sel = cur_frm.print_sel;	
		}
		
		_p.dialog = d;
	},
	
	// Define formats dict
	formats: {},
	
	/* args dict can contain:
			+ fmtname --> print format name
			+ onload
			+ no_letterhead
			+ only_body
	*/
	build: function(fmtname, onload, no_letterhead, only_body) {
		args = {
			fmtname: fmtname,
			onload: onload,
			no_letterhead: no_letterhead,
			only_body: only_body
		};
	
		if(!cur_frm) {
			alert('No Document Selected');
			return;
		}
				
		// Get current doc (record)
		var doc = locals[cur_frm.doctype][cur_frm.docname];
		if(args.fmtname == 'Standard') {
			/*
				Render standard print layout
				The function passed as args onload is then called using these parameters
			*/
			args.onload(_p.render({
				body: _p.print_std(args.no_letterhead),
				style: _p.print_style,
				doc: doc,
				title: doc.name,
				no_letterhead: args.no_letterhead,
				only_body: args.only_body
			}));
		} else {			
			if (!_p.formats[args.fmtname]) {
				/*
					If print formats are not loaded, then load them and call the args onload function on callback.
					I think, this case happens when preview is invoked directly
				*/
				var build_args = args;
				$c(
					command = 'webnotes.widgets.form.print_format.get',
					args = { 'name': build_args.fmtname	},
					fn = function(r, rt) {
						_p.formats[build_args.fmtname] = r.message;
						build_args.onload(_p.render({
							body: _p.formats[build_args.fmtname],
							style: '',
							doc: doc,
							title: doc.name,
							no_letterhead: build_args.no_letterhead,
							only_body: build_args.only_body
						}));						
					}
				);			
			} else {
				// If print format is already loaded, go ahead with args onload function call
				args.onload(_p.render({
					body: _p.formats[args.fmtname],
					style: '',
					doc: doc,
					title: doc.name,
					no_letterhead: args.no_letterhead,
					only_body: args.only_body
				}));			
			}		
		}
	},
	
	
	/*
		args dict can contain:
			+ body
			+ style
			+ doc
			+ title
			+ no_letterhead
			+ only_body
	
	*/
	render: function(args) {
		var container = document.createElement('div');
		var stat = '';
		
		// if draft/archived, show draft/archived banner
		stat += _p.show_draft(args);		
		stat += _p.show_archived(args);
		stat += _p.show_cancelled(args);
		
		// Append args.body's content as a child of container
		container.innerHTML = args.body;
		
		// Show letterhead?
		_p.show_letterhead(container, args);
		
		_p.run_embedded_js(container, args.doc);
		var style = _p.consolidate_css(container, args);
		
		_p.render_header_on_break(container, args);
		
		return _p.render_final(style, stat, container, args);
	},
	

	head_banner_format: function() {
		return "\
			<div style = '\
					text-align: center; \
					padding: 8px; \
					background-color: #CCC;'> \
				<div style = '\
						font-size: 20px; \
						font-weight: bold;'>\
					{{HEAD}}\
				</div>\
				{{DESCRIPTION}}\
			</div>"
	},

	/*
		Check if doc's status is not submitted (docstatus == 0) 
		and submission is pending
		
		Display draft in header if true
	*/	
	show_draft: function(args) {
		var is_doctype_submittable = 0;
		var plist = locals['DocPerm'];
		for(var perm in plist) {
			var p = plist[perm];
			if((p.parent==args.doc.doctype) && (p.submit==1)){
				is_doctype_submittable = 1;
				break;
			}
		}

		if(args.doc && cint(args.doc.docstatus)==0 && is_doctype_submittable) {
			draft = _p.head_banner_format();
			draft = draft.replace("{{HEAD}}", "DRAFT");
			draft = draft.replace("{{DESCRIPTION}}", "This box will go away after the document is submitted.");
			return draft;
		} else {
			return "";
		}
	},
	
	
	/*
		Check if doc is archived	
		Display archived in header if true
	*/
	show_archived: function(args) {
		if(args.doc && args.doc.__archived) {
			archived = _p.head_banner_format();
			archived = archived.replace("{{HEAD}}", "ARCHIVED");
			archived = archived.replace("{{DESCRIPTION}}", "You must restore this document to make it editable.");
			return archived;
		} else {
			return "";
		}	
	},


	/*
		Check if doc is cancelled
		Display cancelled in header if true
	*/
	show_cancelled: function(args) {
		if(args.doc && args.doc.docstatus==2) {
			cancelled = _p.head_banner_format();
			cancelled = cancelled.replace("{{HEAD}}", "CANCELLED");
			cancelled = cancelled.replace("{{DESCRIPTION}}", "You must amend this document to make it editable.");
			return cancelled;
		} else {
			return "";
		}	
	},


	consolidate_css: function(container, args) {
		// Extract <style> content from container
		var body_style = '';
		var style_list = container.getElementsByTagName('style');
		while(style_list && style_list.length>0) {
			for(i in style_list) {
				if(style_list[i] && style_list[i].innerHTML) {
					body_style += style_list[i].innerHTML;
					var parent = style_list[i].parentNode;
					if(parent) {
						parent.removeChild(style_list[i]);
					} else {
						container.removeChild(style_list[i]);
					}
				}
			}
			style_list = container.getElementsByTagName('style');
		}
		
		// Concatenate all styles
		//style_concat =  _p.def_print_style_other + args.style + body_style;
		style_concat =  (args.only_body ? '' : _p.def_print_style_body)
				+ _p.def_print_style_other + args.style + body_style;
			
		return style_concat;
	},


	// This is used to calculate and substitude values in the HTML
	run_embedded_js: function(container, doc) {
		var jslist = container.getElementsByTagName('script');
		while(jslist && jslist.length > 0) {
			for(i in jslist) {
				if(jslist[i] && jslist[i].innerHTML) {
					var code = jslist[i].innerHTML;
					var parent = jslist[i].parentNode;
					var span = $a(parent, 'span');
					parent.replaceChild(span, jslist[i]);
					var val = code ? eval(code) : '';
					if(!val || typeof(val)=='object') { val = ''; }
					span.innerHTML = val;
				}
			}
			jslist = container.getElementsByTagName('script');
		}
	},
	
	
	// Attach letterhead at top of container
	show_letterhead: function(container, args) {	
		if(!(args.no_letterhead || args.only_body)) {
			container.innerHTML = '<div>' + _p.get_letter_head() + '</div>' 
				+ container.innerHTML;
		}
	},
	
	
	render_header_on_break: function(container, args) {
		var page_set = container.getElementsByClassName('page-settings');
		if(page_set.length) {
			for(var i = 0; i < page_set.length; i++) {
				var tmp = '';
				// if draft/archived, show draft/archived banner
				tmp += _p.show_draft(args);
				tmp += _p.show_archived(args);
				_p.show_letterhead(page_set[i], args);
				page_set[i].innerHTML = tmp + page_set[i].innerHTML;
			}
		}
	},
	
	
	// called by _p.render for final render of print
	render_final: function(style, stat, container, args) {
		var header = '<div class="page-settings">\n';
		var footer = '\n</div>';
		if(!args.only_body) {
			header = '<!DOCTYPE html>\n\
					<html>\
						<head>\
							<title>' + args.title + '</title>\
							<style>' + style + '</style>\
						</head>\
						<body>\n' + header;
			
			footer = footer + '\n</body>\n\
					</html>';
		}
		var finished =  header
			+ stat
			+ container.innerHTML.replace(/<div/g, '\n<div').replace(/<td/g, '\n<td')
			+ footer;
		return finished;
	},
	
	
	// fetches letter head from current doc or control panel
	get_letter_head: function() {
		var cp = wn.control_panel;
		var lh = '';
		if(cur_frm.doc.letter_head) {
			lh = cstr(wn.boot.letter_heads[cur_frm.doc.letter_head]);
		} else if (cp.letter_head) {
			lh = cp.letter_head;
		}		
		return lh;
	},
	
	// common print style setting
	print_style: "\
		.datalabelcell { \
			padding: 2px 0px; \
			width: 38%; \
			vertical-align: top; \
			} \
		.datainputcell { \
			padding: 2px 0px; \
			width: 62%; \
			text-align: left; \
			}\
		.sectionHeading { \
			font-size: 16px; \
			font-weight: bold; \
			margin: 8px 0px; \
			} \
		.columnHeading { \
			font-size: 14px; \
			font-weight: bold; \
			margin: 8px 0px; \
			}",
	
	print_std: function(no_letterhead) {
		// Get doctype, docname, layout for a doctype
		var docname = cur_frm.docname;
		var doctype = cur_frm.doctype;
		var data = getchildren('DocField', doctype, 'fields', 'DocType');
		var layout = _p.add_layout(doctype);
		this.pf_list = [layout];
		var me = this;
		me.layout = layout;

		$.extend(this, {
			build_head: function(data, doctype, docname) {
				// Heading
				var h1_style = {
					fontSize: '22px',
					marginBottom: '8px'			
				}
				var h1 = $a(me.layout.cur_row.header, 'h1', '', h1_style);
				
				// Get print heading
				if (cur_frm.pformat[docname]) {
					// first check in cur_frm.pformat
					h1.innerHTML = cur_frm.pformat[docname];
				} else {
					// then check if select print heading exists and has a value
					var val = null;
					for (var i = 0; i < data.length; i++) {
						if (data[i].fieldname === 'select_print_heading') {
							val = _f.get_value(doctype, docname, data[i].fieldname);
							break;
						}
					}
					// if not, just have doctype has heading
					h1.innerHTML = val ? val : get_doctype_label(doctype);
				}
					
				var h2_style = {
					fontSize: '16px',
					color: '#888',
					marginBottom: '8px',
					paddingBottom: '8px',
					borderBottom: (me.layout.with_border ? '0px' :
						'1px solid #000')
				}
				var h2 = $a(me.layout.cur_row.header, 'div', '', h2_style);
				h2.innerHTML = docname;
			},
			
			build_data: function(data, doctype, docname) {
				// Start with a row and a cell in that row
				if(data[0] && data[0].fieldtype != "Section Break") {
					me.layout.addrow();
					if(data[0].fieldtype != "Column Break") {
						me.layout.addcell();
					}
				}
				
				$.extend(this, {
					generate_custom_html: function(field, doctype, docname) {
						var container = $a(me.layout.cur_cell, 'div');
						container.innerHTML = cur_frm.pformat[field.fieldname](locals[doctype][docname]);					
					},
					
					render_normal: function(field, data, i) {
						switch(field.fieldtype) {
							case 'Section Break':
								me.layout.addrow();
								
								// Add column if no column break after this field
								if(data[i+1] && data[i+1].fieldtype !=
										'Column Break') {
									me.layout.addcell();
								}
								break;
							
							case 'Column Break':
								me.layout.addcell(field.width, field.label);							
								break;
								
							case 'Table':
								var table = print_table(
										doctype, // dt
										docname, // dn
										field.fieldname,
										field.options, // tabletype 
										null, // cols
										null, // head_labels
										null, // widths
										null); // condition
								me.layout = _p.print_std_add_table(table, me.layout, me.pf_list, doctype, no_letterhead);
								break;
							
							case 'HTML':
								var div = $a(me.layout.cur_cell, 'div');
								div.innerHTML = field.options;
								break;
							
							case 'Code':
								var div = $a(me.layout.cur_cell, 'div');
								var val = _f.get_value(doctype, docname,
									field.fieldname);
								div.innerHTML = '<div>' + field.label +
									': </div><pre style="font-family: Courier, Fixed;">' + (val ? val : '') +
									'</pre>';
								break;
								
							case 'Text Editor':
								var div = $a(me.layout.cur_cell, 'div');
								var val = _f.get_value(doctype, docname,
									field.fieldname);
								div.innerHTML = val ? val : '';
								break;
								
							default:
								// Add Cell Data
								_p.print_std_add_field(doctype, docname, field, me.layout);
								break;
						}
					}				
				});
				
				// Then build each field
				for(var i = 0; i < data.length; i++) {
					var fieldname = data[i].fieldname ? data[i].fieldname :
						data[i].label;
					var field = fieldname ?
						wn.meta.get_docfield(doctype, fieldname, docname) : data[i];
					if(!field.print_hide) {
						if(cur_frm.pformat[field.fieldname]) {
							// If there is a custom method to generate the HTML, then use it
							this.generate_custom_html(field, doctype, docname);
						} else {
							// Do the normal rendering
							this.render_normal(field, data, i);
						}
					}					
				}
				me.layout.close_borders();
			},
			
			build_html: function() {
				var html = '';
				for(var i = 0; i < me.pf_list.length; i++) {
					if(me.pf_list[i].wrapper) {
						html += me.pf_list[i].wrapper.innerHTML;
					} else if(me.pf_list[i].innerHTML) {
						html += me.pf_list[i].innerHTML;
					} else {
						html += me.pf_list[i];
					}
				}
				this.pf_list = [];
				return html;
			}
		});
		
		this.build_head(data, doctype, docname);

		this.build_data(data, doctype, docname);

		var html = this.build_html();
		return html;
	},
	
	add_layout: function(doctype) {
		var layout = new Layout();
		layout.addrow();
		
		if(locals['DocType'][doctype].print_outline == 'Yes') {
			layout.with_border = 1
		}
		
		return layout;	
	},
	
	print_std_add_table: function(t, layout, pf_list, dt, no_letterhead) {
		if(t.appendChild) {
			// If only one table is passed
			layout.cur_cell.appendChild(t);
		} else {
			page_break = '\n\
				<div style = "page-break-after: always;" \
				class = "page_break"></div><div class="page-settings"></div>';
				
			// If a list of tables is passed
			for(var i = 0; i < t.length-1; i++) {
				// add to current page
				layout.cur_cell.appendChild(t[i]);
				layout.close_borders();
				
				pf_list.push(page_break);
				
				// Create new page
				layout = _p.add_layout(dt, no_letterhead);
				pf_list.push(layout);
				
				layout.addrow();
				layout.addcell();
				
				var div = $a(layout.cur_cell, 'div');
				div.innerHTML = 'Continued from previous page...';
				div.style.padding = '4px';
			}
			
			// Append last table
			layout.cur_cell.appendChild(t[t.length-1]);
		}
		return layout;
	},
	
	print_std_add_field: function(dt, dn, f, layout) {
		var val = _f.get_value(dt, dn, f.fieldname);
		if(f.fieldtype!='Button') {
			if(val || in_list(['Float', 'Int', 'Currency'], f.fieldtype)) {
				// If value or a numeric type then proceed
				
				// Add field table
				row = _p.field_tab(layout.cur_cell);
				
				// Add label
				row.cells[0].innerHTML = f.label ? f.label : f.fieldname;
				$s(row.cells[1], val, f.fieldtype);
				
				// left align currency in normal display
				if(f.fieldtype == 'Currency') {
					$y(row.cells[1], { textAlign: 'left' });
				}
				
			}
		}
	},
	
	field_tab: function(layout_cell) {
		var tab = $a(layout_cell, 'table', '', {width:'100%'}); 
		var row = tab.insertRow(0);
		_p.row = row; // Don't know this line's purpose
		row.insertCell(0);
		row.insertCell(1);
		row.cells[0].className = 'datalabelcell';
		row.cells[1].className = 'datainputcell';
		return row;
	}
});


print_table = function(dt, dn, fieldname, tabletype, cols, head_labels, widths, condition, cssClass, modifier, hide_empty) {
	var me = this;
	$.extend(this, {
		flist: (function() {
			var f_list = [];
			var fl = wn.meta.docfield_list[tabletype];
			if(fl) {
				for(var i=0; i<fl.length; i++) {
					f_list.push(copy_dict(fl[i]));
				}
			}
			return f_list;
		})(),

		data: function() {
			var children = getchildren(
				tabletype, // child_dt
				dn, // parent
				fieldname, // parentfield
				dt // parenttype
			);
			var data = []
			for(var i=0; i<children.length; i++) {
				data.push(copy_dict(children[i]));
			}
			return data;
		}(),
		
		cell_style: {
			border: '1px solid #000',
			padding: '2px',
			verticalAlign: 'top'	
		},
		
		head_cell_style: {
			border: '1px solid #000',
			padding: '2px',
			verticalAlign: 'top',
			backgroundColor: '#ddd',
			fontWeight: 'bold'
		},
		
		table_style: {
			width: '100%',
			borderCollapse: 'collapse',
			marginBottom: '10px'		
		},

		remove_empty_cols: function(flist) {
			var non_empty_cols = []
			for(var i=0; i<me.data.length; i++) {
				for(var c=0; c<flist.length; c++) {
					if(flist[c].print_hide || !inList(['', null], me.data[i][flist[c].fieldname])) {
						if(!inList(non_empty_cols, flist[c])) {
							non_empty_cols.push(flist[c]);
						}
					}
				}
			}
			for(var c=0; c<flist.length; c++) {
				if(!inList(non_empty_cols, flist[c])) {
					flist.splice(c, 1);
					c = c - 1;
				}
			}
		},
		
		/*
			This function prepares a list of columns to be displayed and calls make_print_table to create a table with these columns
		*/
		prepare_col_heads: function(flist) {
			var new_flist = [];

			if(!cols || (cols && cols.length && hide_empty)) {
				me.remove_empty_cols(flist);
			}
			
			// Make a list of column headings
			if(cols && cols.length) {
				// If cols to be displayed are passed in print_table
				if(cols[0] == 'SR') { new_flist.push('SR') }
				for(var i = 0; i < cols.length; i++) {
					for(var j = 0; j < flist.length; j++) {
						if(flist[j].fieldname == cols[i]) {
							new_flist.push(flist[j]);
							break;
						}
					}
				}			
			} else {
				// Default action: remove hidden cols
				new_flist.push('SR');
				for(var i = 0; i < flist.length; i++) {
					if(!flist[i].print_hide) {
						new_flist.push(flist[i]);
					}
				}			
			}
			
			// Changing me.flist so that it could be used to hide data
			me.flist = new_flist;
		},
		
		// This function makes a new table with its heading rows
		make_print_table: function(flist) {
			// Make a table
			var wrapper = document.createElement('div');
			var table = $a(wrapper, 'table', '', me.table_style);
			table.wrapper = wrapper;
			
			// Make Head Row
			table.insertRow(0);
			var col_start = 0;
			
			// If 'SR' exists in flist, then create its heading column cell
			if(flist[0]=='SR') {
				var cell = table.rows[0].insertCell(0);
				cell.innerHTML = head_labels?head_labels[0]:'<b>SR</b>';
				$y(cell, { width: '30px' });
				$y(cell, me.head_cell_style);
				col_start++;
			}
			
			for(var c = col_start; c < flist.length; c++) {
				var cell = table.rows[0].insertCell(c);
				$y(cell, me.head_cell_style);
				cell.innerHTML = head_labels?head_labels[c]:flist[c].label;
				if(flist[c].width) { $y(cell, {width: flist[c].width}); }
				if(widths) { $y(cell, {width: widths[c]}); }
				if(in_list(['Currency', 'Float'], flist[c].fieldtype)) {
					$y(cell, { textAlign: 'right' });
				}
			}
			return table;
		},
		
		// Populate table with data
		populate_table: function(table, data) {
			for(var r = 0; r < data.length; r++) {
				if((!condition) || (condition(data[r]))) {
					// Check for page break
					if(data[r].page_break) {
						table = me.make_print_table(me.flist);
						me.table_list.push(table.wrapper);
					}
					
					var row = table.insertRow(table.rows.length);
					
					// Add serial number if required
					if(me.flist[0] == 'SR') {
						var cell = row.insertCell(0);
						cell.innerHTML = r + 1;
						$y(cell, me.cell_style);
					}
					
					for(var c=me.flist.indexOf('SR')+1; c<me.flist.length; c++){
						var cell = row.insertCell(c);
						$y(cell, me.cell_style);
						if(modifier && me.flist[c].fieldname in modifier) {
							data[r][me.flist[c].fieldname] = modifier[me.flist[c].fieldname](data[r]);
						}
						$s(cell, data[r][me.flist[c].fieldname],
							me.flist[c].fieldtype);
						if(in_list(['Currency', 'Float'], me.flist[c].fieldtype)) {
							cell.style.textAlign = 'right';
						}
					}
				}			
			}
		}
	});	
	
	// If no data, do not create table
	if(!this.data.length) { return document.createElement('div'); }
	
	this.prepare_col_heads(this.flist);

	var table = me.make_print_table(this.flist);

	this.table_list = [table.wrapper];

	this.populate_table(table, this.data);

	// If multiple tables exists, send whole list, else send only one table
	return (me.table_list.length > 1) ? me.table_list : me.table_list[0];
}
