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
			w = 360,
			h = 140,
			title = 'Print Formats',
			content = [
				['HTML', 'Select'],
				['Check', 'No Letterhead'],
				['HTML', 'Buttons']				
			]);		
		d.widgets['No Letterhead'].checked = 1;
		
		// Print Button
		$btn(
			parent = d.widgets.Buttons,
			label = 'Print',
			onclick = function() {
				_p.build({
					fmtname: sel_val(cur_frm.print_sel),
					onload: _p.go,
					no_letterhead: d.widgets['No Letterhead'].checked,
					only_body: undefined
				});			
			},
			style = {
				cssFloat: 'right',
				marginBottom: '16px',
				marginLeft: '7px'
			},
			css_class = 'green'
		);
		
		// Print Preview
		$btn(
			parent = d.widgets.Buttons,
			label = 'Preview',
			onclick = function() {
				_p.build({
					fmtname: sel_val(cur_frm.print_sel),
					onload: _p.preview,
					no_letterhead: d.widgets['No Letterhead'].checked,
					only_body: undefined
				});
			},
			style = {
				cssFloat: 'right',
				marginBottom: '16px'			
			},
			css_class = ''
		);
		
		_p.dialog = d;
		
		// Delete previous print format select list and Reload print format list from current form
		d.onshow = function() {
			var c = _p.dialog.widgets['Select'];
			if(c.cur_sel && c.cur_sel.parentNode == c) {
				c.removeChild(c.cur_sel);
			}
			c.appendChild(cur_frm.print_sel);
			c.cur_sel = cur_frm.print_sel;		
		}
	},
	
	// Define formats dict
	formats: {},
	
	/* args dict can contain:
			+ fmtname --> print format name
			+ onload
			+ no_letterhead
			+ only_body
	*/
	build: function(args) {
		if(!cur_frm) {
			alert('No Document Selected');
			return;
		}
		
		// Get current doc (record)
		var doc = locals[cur_frm.doctype][cur_frm.docname];
		if(args.fmtname == 'Standard') {
			/*
				Render standard print layout
				The function passed as args.onload is then called using these parameters
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
					If print formats are not loaded, then load them and call the args.onload function on callback.
					I think, this case happens when preview is invoked directly
				*/
				$c(
					command = 'webnotes.widgets.form.get_print_format',
					args = { 'name': args.fmtname	},
					fn = function(r, rt) {
						_p.formats[args.fmtname] = r.message;
						args.onload(_p.render({
							body: _p.formats[args.fmtname],
							style: '',
							doc: doc,
							title: doc.name,
							no_letterhead: args.no_letterhead,
							only_body: args.only_body
						}));						
					}
				);			
			} else {
				// If print format is already loaded, go ahead with args.onload function call
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
		
		// Append args.body's content as a child of container
		container.innerHTML = args.body;
		
		_p.run_embedded_js(container, args.doc);
		var style = _p.consolidate_css(container, args);
		
		// Show letterhead?
		_p.show_letterhead(container, args);
		
		_p.render_final(style, stat, container, args);
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
					{{TITLE}}\
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
		if(args.doc && cint(args.doc.docstatus)==0 && cur_frm.perm[0][SUBMIT]) {
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
		return (args.only_body ? '' : _p.def_print_style_body)
			+ _p.def_print_style_other
			+ args.style;
			+ body_style;
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
					var val = eval(code);
					if(!val) { val = ''; }
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
	
	
	// called by _p.render for final render of print
	render_final: function(style, stat, container, args) {
		var header = '';
		var footer = '';
		if(!args.only_body) {
			header = '<!DOCTYPE html>\n\
					<html>\
						<head>\
							<title>' + args.title + '</title>\
							<style>' + style + '</style>\
						</head>\
						<body>\n';
			
			footer = '\n</body>\n\
					</html>';
		}
		return header
			+ stat
			+ container.innerHTML.replace(/<div/g, '\n<div').replace(/<td/g, '\n<td')
			+ footer;
	
	},
	
	
	// fetches letter head from current doc or control panel
	get_letter_head: function() {
		var cp = locals['Control Panel']['Control Panel'];
		var lh = '';
		if(cur_frm.doc.letter_head) {
			lh = cstr(_p.letter_heads[cur_frm.doc.letter_head]);
		} else if (cp.letter_head) {
			lh = cp.letter_head
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
			}"
	
	
	/*print_std_add_table: function() {
	
	
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
	}*/
});

print_table = function(args) {


}