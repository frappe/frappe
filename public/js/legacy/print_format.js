// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
// MIT License. See license.txt 

// default print style
_p.def_print_style_body = "html, body, div, span, td, p { \
		font-family: inherit; \
		font-size: inherit; \
	}\
	.page-settings {\
		font-family: Arial, Helvetica Neue, Sans;\
		font-size: 9pt;\
	}\
	pre { margin:0; padding:0;}";

_p.def_print_style_other = "\n.simpletable, .noborder { \
		border-collapse: collapse;\
		margin-bottom: 10px;\
	}\
	.simpletable td {\
		border: 1pt solid #777;\
		vertical-align: top;\
		padding: 4px;\
	}\
	.noborder td {\
		vertical-align: top;\
	}";

_p.go = function(html) {
	var w = _p.preview(html);
	w.print();
	w.close();
}

_p.preview = function(html) {
	var w = window.open();
	if(!w) {
		msgprint(_("Please enable pop-ups"));
		return;
	}
	w.document.write(html);
	return w
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
		var dialog = new wn.ui.Dialog({
			title: "Print Formats",
			fields: [
				{fieldtype:"Select", label:"Print Format", fieldname:"print_format", reqd:1},
				{fieldtype:"Check", label:"No Letter Head", fieldname:"no_letterhead"},
				{fieldtype:"HTML", options: '<p style="text-align: right;">\
					<button class="btn btn-primary btn-print">Print</button>\
					<button class="btn btn-default btn-preview">Preview</button>\
				</p>'},
			]
		});
		
		dialog.$wrapper.find(".btn-print").click(function() {
			var args = dialog.get_values();
			_p.build(
				args.print_format, // fmtname
				_p.go, // onload
				args.no_letterhead // no_letterhead
			);
		});

		dialog.$wrapper.find(".btn-preview").click(function() {
			var args = dialog.get_values();
			_p.build(
				args.print_format, // fmtname
				_p.preview, // onload
				args.no_letterhead // no_letterhead
			);
		});
		
		dialog.onshow = function() {
			var $print = dialog.fields_dict.print_format.$input;
			$print.empty().add_options(cur_frm.print_formats);
			
			if(cur_frm.$print_view_select && cur_frm.$print_view_select.val())
				$print.val(cur_frm.$print_view_select.val());
		}
				
		_p.dialog = dialog;
	},
	
	// Define formats dict
	formats: {},
	
	/* args dict can contain:
			+ fmtname --> print format name
			+ onload
			+ no_letterhead
			+ only_body
	*/
	build: function(fmtname, onload, no_letterhead, only_body, no_heading) {
		if(!fmtname) {
			fmtname= "Standard";
		}
		
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
			args.onload(_p.render({
				body: _p.print_std(args.no_letterhead, no_heading),
				style: _p.print_style,
				doc: doc,
				title: doc.name,
				no_letterhead: args.no_letterhead,
				no_heading: no_heading,
				only_body: args.only_body
			}));
		} else {
			var print_format_doc = locals["Print Format"][args.fmtname];
			if(!print_format_doc) {
				msgprint("Unknown Print Format: " + args.fmtname);
				return;
			}
			args.onload(_p.render({
				body: print_format_doc.html,
				style: '',
				doc: doc,
				title: doc.name,
				no_letterhead: args.no_letterhead,
				no_heading: no_heading,
				only_body: args.only_body
			}));			
		}
	},
	
	render: function(args) {
		var container = document.createElement('div');
		var stat = '';
		
		if(!args.no_heading) {
			// if draft/archived, show draft/archived banner
			stat += _p.show_draft(args);		
			stat += _p.show_archived(args);
			stat += _p.show_cancelled(args);
		}
		
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
		style_concat =  (args.only_body ? '' : _p.def_print_style_body)
				+ _p.def_print_style_other + args.style + body_style;
			
		return style_concat;
	},


	// This is used to calculate and substitude values in the HTML
	run_embedded_js: function(container, doc) {
		script_list = $(container).find("script");
		for(var i=0; i<script_list.length; i++) {
			var element = script_list[i];
			var code = element.innerHTML;
			var new_html = code ? (eval(code) || "") : "";
			if(in_list(["string", "number"], typeof new_html)) {
				$(element).replaceWith(this.add_span(new_html + ""));
			}
		}
	},
	
	add_span: function(html) {
		var tags = ["<span[^>]>", "<p[^>]>", "<div[^>]>", "<br[^>]>", "<table[^>]>"];
		var match = false;
		for(var i=0; i<tags.length; i++) {
			if(html.match(tags[i])) {
				match = true;
			}
		}
		
		if(!match) {
			html = "<span>" + html + "</span>";
		}
		
		return html;
	},
	
	
	// Attach letterhead at top of container
	show_letterhead: function(container, args) {	
		if(!(args.no_letterhead || args.only_body)) {
			container.innerHTML = '<div style="max-width: 100%">' 
				+ _p.get_letter_head() + '</div>' 
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
		if(!args.only_body) {
			var header = '<!DOCTYPE html>\
<html>\
	<head>\
		<meta charset="utf-8" />\
		<title>' + args.title + '</title>\
		<style>' + style + '</style>\
	</head>\
	<body>';
			var footer = '\
	</body>\
</html>';
		} else {
			var header = '';
			var footer = '';
		}
		var finished =  header
			+ '<div class="page-settings">'
			+ stat
			+ container.innerHTML
			+ '</div>'
			+ footer;
			
			
		// replace relative links by absolute links
		var prefix = window.location.href.split("app.html")[0]
		// find unique matches
		var matches = $.unique(finished.match(/src=['"]([^'"]*)['"]/g) || []);
		
		$.each(matches, function(i, v) {
			if(v.substr(0,4)=="src=") {
				var v = v.substr(5, v.length-6);
				if(v.substr(0,4)!="http")
					finished = finished.split(v).join(prefix + v);
			}
		});
		
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
	
	print_std: function(no_letterhead, no_heading) {
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
					h1.innerHTML = val ? val : wn._(doctype);
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
				
				if(cur_frm.state_fieldname) {
					$a(h2, 'br');
					var span = $a(h2, 'span', '', 
						{padding: "3px", color: "#fff", backgroundColor: "#777", 
							display:"inline-block"});
					span.innerHTML = cur_frm.doc[cur_frm.state_fieldname];
				}
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
		
		if(!no_heading) {
			this.build_head(data, doctype, docname);
		}

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
				row.cells[1].innerHTML = wn.format(val, f, {for_print: true});
				
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
		row.cells[0].style.width = "38%";
		row.cells[1].className = 'datainputcell';
		return row;
	}
});