_p.show_dialog = function() {
	if(!_p.dialog) {
		_p.make_dialog();
	}
	_p.dialog.show();
}

_p.make_dialog = function() {
	var d = new Dialog(360, 140, "Print Formats");
	d.make_body(
		[['HTML','Select']
		,['Check','No Letterhead','Will ignore letterhead if it can be set. May not work for all formats']
		,['HTML', 'Buttons']
		]);
	
	d.widgets['No Letterhead'].checked = 1;
	
	// prints
	$btn(d.widgets.Buttons, 'Print', 
		function() { _p.build(sel_val(cur_frm.print_sel), _p.go, d.widgets['No Letterhead'].checked); },
		{cssFloat:'right', marginBottom:'16px', marginLeft:'7px'}, 'green');

	// preview
	$btn(d.widgets.Buttons, 'Preview', 
		function() { _p.build(sel_val(cur_frm.print_sel), _p.preview, d.widgets['No Letterhead'].checked); },
		{cssFloat:'right', marginBottom:'16px'}, '');
	
	_p.dialog = d;
	d.onshow = function() {
		var c = d.widgets['Select'];
		if(c.cur_sel && c.cur_sel.parentNode == c)
			c.removeChild(c.cur_sel);
		c.appendChild(cur_frm.print_sel);
		c.cur_sel = cur_frm.print_sel;
	}
}

_p.field_tab = function(layout_cell) {
	var t = $a(layout_cell, 'table', '', {width:'100%'});
	var r = t.insertRow(0); this.r = r;
	r.insertCell(0); r.insertCell(1);
	r.cells[0].className='datalabelcell';
	r.cells[1].className='datainputcell';
	return r
}


// standard layout
// ==========================================================================

_p.print_std_add_table = function(t, layout, pf_list, dt, no_letterhead) {
	if(t.appendChild) { 
		// one table only
		layout.cur_cell.appendChild(t);
	} else { 
		// multiple tables
		for(var ti=0;ti<t.length-1;ti++) {	
			// add to current page
			layout.cur_cell.appendChild(t[ti]);
			layout.close_borders();
			pf_list[pf_list.length] = '<div style="page-break-after: always;" class="page_break"></div>';
							
			// new page
			layout = _p.add_layout(dt, no_letterhead);
			pf_list[pf_list.length]=layout;
	
			layout.addrow(); 
			layout.addcell();
		
			var div = $a(layout.cur_cell, 'div');
			div.innerHTML = 'Continued from previous page...';
			div.style.padding = '4px';
		}
		// last table
		layout.cur_cell.appendChild(t[t.length-1]);
	}
	return layout;
}

// --------------------------------------------------------------------

_p.print_std_add_field = function(dt, dn, f, layout) {

	var v = _f.get_value(dt,dn,f.fieldname);
	if(f.fieldtype!="Button") {
		if(!v && !in_list(['Float','Int','Currency'], f.fieldtype)) {
			// no value and non-numberic - do nothing
		} else {
			r = _p.field_tab(layout.cur_cell)
			// label
			r.cells[0].innerHTML=f.label?f.label:f.fieldname;
							
			$s(r.cells[1], v, f.fieldtype);
		
			// left align currency in normal display
			if(f.fieldtype=='Currency')
				$y(r.cells[1],{textAlign: 'left'});
			}
	}
}

_p.get_letter_head = function() {
	// add letter head
	var cp = locals['Control Panel']['Control Panel'];
	if(cur_frm.doc.letter_head)
		var lh= cstr(_p.letter_heads[cur_frm.doc.letter_head]);
	else if(cp.letter_head)
		var lh= cp.letter_head;
	else 
		var lh= '';
		
	return lh;
}

// --------------------------------------------------------------------

_p.add_layout = function(dt, no_letterhead) {
	var l = new Layout();
	l.addrow();

	if(locals['DocType'][dt].print_outline=='Yes') l.with_border = 1;
	
	return l;
}

// --------------------------------------------------------------------

_p.print_std = function(no_letterhead) {
	var dn = cur_frm.docname;
	var dt = cur_frm.doctype;
	var pf_list = [];

	var layout = _p.add_layout(dt, no_letterhead);
	pf_list[pf_list.length]=layout;

	// heading
	var h1 = $a(layout.cur_row.header, 'h1', '', {fontSize:'22px', marginBottom:'8px'}); 
	h1.innerHTML = cur_frm.pformat[dn] ? cur_frm.pformat[dn] : get_doctype_label(dt);
	
	var h2 = $a(layout.cur_row.header, 'div', '', {fontSize:'16px', color:'#888', marginBottom:'8px', paddingBottom:'8px', borderBottom:(layout.with_border ? '0px' : '1px solid #000' )});
	h2.innerHTML = dn;
	
	var fl = getchildren('DocField', dt, 'fields', 'DocType');

	if(fl[0]&&fl[0].fieldtype!="Section Break") {
		layout.addrow(); // default section break
		if(fl[0].fieldtype!="Column Break") // without column too
			layout.addcell(); 
	}

	// build each field
	for(var i=0;i<fl.length;i++) {
		var fn = fl[i].fieldname?fl[i].fieldname:fl[i].label;
		if(fn)
			var f = get_field(dt, fn, dn);
		else
			var f = fl[i];
			
		if(!f.print_hide){

			// if there is a custom method to generate the HTML then use it
			if(cur_frm.pformat[f.fieldname]) {

				var tmp = $a(layout.cur_cell, 'div');
				tmp.innerHTML = cur_frm.pformat[f.fieldname](locals[dt][dn]);
				
			} else {
				// do the normal thing
			
				switch(f.fieldtype){
				 case 'Section Break':
					layout.addrow();
					// if no column break after this field then add a column
					if(fl[i+1]&&(fl[i+1].fieldtype!='Column Break')) {
						layout.addcell(); }
						
					// add label ---- no labels for section breaks!
					//if(f.label) layout.cur_row.header.innerHTML = '<div class="sectionHeading">'+f.label+'</div>';
					break;
				 case 'Column Break': 
					layout.addcell(f.width, f.label); 
					//if(f.label) layout.cur_cell.header.innerHTML = '<div class="columnHeading">'+f.label+'</div>';
					break;
				 case 'Table': 
					var t = print_table(dt, dn,f.fieldname,f.options,null,null,null,null);
					layout = _p.print_std_add_table(t, layout, pf_list, dt, no_letterhead);
				 	break;
				 case 'HTML': 
				 	var tmp = $a(layout.cur_cell, 'div');
				 	tmp.innerHTML = f.options;
				 	break;
				 case 'Code': 
				 	var tmp = $a(layout.cur_cell, 'div');
				 	var v= _f.get_value(dt,dn,f.fieldname);
				 	tmp.innerHTML = '<div>'+ f.label + ': </div>' + '<pre style="font-family: Courier, Fixed;">'+(v?v:'')+'</pre>';
				 	break;
				 case 'Text Editor': 
				 	var tmp = $a(layout.cur_cell, 'div');
				 	var v= _f.get_value(dt,dn,f.fieldname);
				 	tmp.innerHTML = v?v:'';
				 	break;
				 default:
				 	// add cell data
				 	_p.print_std_add_field(dt, dn, f, layout);

				}
			}
		}
	}

	layout.close_borders();
	
	// build html for each page
	var html = '';
	for(var i=0;i<pf_list.length;i++) {
		if(pf_list[i].wrapper) {
			html += pf_list[i].wrapper.innerHTML;
		} else if(pf_list[i].innerHTML) {
			html += pf_list[i].innerHTML;
		} else {
			html += pf_list[i];
		}
	}

	pf_list = []; // cleanup
	return html;
}

_p.print_style = ".datalabelcell {padding: 2px 0px; width: 38%;vertical-align:top; }"
	+".datainputcell { padding: 2px 0px; width: 62%; text-align:left; }"
	+".sectionHeading { font-size: 16px; font-weight: bold; margin: 8px 0px }"
	+".columnHeading { font-size: 14px; font-weight: bold; margin: 8px 0px; }"

_p.formats = {}

_p.build = function(fmtname, onload, no_letterhead, only_body) {
	if(!cur_frm) { alert('No Document Selected'); return; }
	var doc = locals[cur_frm.doctype][cur_frm.docname];
	if(fmtname=='Standard') {
		onload(_p.render(_p.print_std(no_letterhead), _p.print_style, doc, doc.name, no_letterhead, only_body));
	} else {
		if(!_p.formats[fmtname]) // not loaded, get data
			$c('webnotes.widgets.form.get_print_format', {'name':fmtname }, 
				function(r,rt) { 
					_p.formats[fmtname] = r.message;
					onload(_p.render(_p.formats[fmtname], '', doc, doc.name, no_letterhead, only_body)); 
				}
			);
		else // loaded
			onload(_p.render(_p.formats[fmtname], '', doc, doc.name, no_letterhead, only_body));	
	}
}

_p.render = function(body, style, doc, title, no_letterhead, only_body) {
	var block = document.createElement('div');
	var tmp_html = '';
	
	if(doc && cint(doc.docstatus)==0 && cur_frm.perm[0][SUBMIT])  {
		var tmp_html = '<div style="text-align: center; padding: 8px; background-color: #CCC; "><div style="font-size: 20px; font-weight: bold; ">DRAFT</div>This box will go away after the document is submitted.</div>';
	}
	if(doc && doc.__archived)  {
		var tmp_html = '<div style="text-align: center; padding: 8px; background-color: #CCC; "><div style="font-size: 20px; font-weight: bold; ">ARCHIVED</div>You must restore this document to make it editable.</div>';
	}

	style = (only_body ? '' : _p.def_print_style_body) + _p.def_print_style_other + style;
	
	block.innerHTML = body;

	// run embedded javascript
	var jslist = block.getElementsByTagName('script');
	while(jslist.length>0) {
		for(var i=0; i<jslist.length; i++) {
			var code = jslist[i].innerHTML;
			var p = jslist[i].parentNode;
			var sp = $a(p, 'span');
			p.replaceChild(sp, jslist[i]);
			var h = eval(code); if(!h)h='';
			sp.innerHTML = h;
		}
		jslist = block.getElementsByTagName('script');
	}
	
	// show letterhead?
	if(only_body) 
		show_lh = false;
	else {
		if(!no_letterhead) show_lh = true;
		else show_lh = false;
	}
	
	// add letter head
	if(show_lh) {
		block.innerHTML = '<div>' + _p.get_letter_head() + '</div>' + block.innerHTML;
	}

	if(only_body) {
		return tmp_html + block.innerHTML.replace(/<td/g, '\n<td').replace(/<div/g, '\n<div');
	} else {
		// print block
		return '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">\n'
			+ '<html><head>'
			+ '<title>'+title+'</title>'
			+ '<style>'+style+'</style>'
			+ '</head><body>'
			+ tmp_html
			+ block.innerHTML.replace(/<td/g, '\n<td')
			+ '</body></html>';
	}
}

print_table = function(dt, dn, fieldname, tabletype, cols, head_labels, widths, condition, cssClass) {
	var fl = fields_list[tabletype];
	var ds = getchildren(tabletype, dn, fieldname, dt);
	var tl = [];
	var cell_style = {border:'1px solid #000', padding:'2px', verticalAlign:'top'};
	var head_cell_style = {border:'1px solid #000', padding:'2px', verticalAlign:'top', backgroundColor:'#ddd'};
	
	var make_table = function(fl) {
		var w = document.createElement('div');
		var t = $a(w, 'table', '', {width:'100%', borderCollapse:'collapse', marginBottom:'10px'});
		t.wrapper = w;
		
		// head row
		t.insertRow(0);
		var c_start = 0;
	 	if(fl[0]=='SR') {
			var cell = t.rows[0].insertCell(0)
			cell.innerHTML = head_labels?head_labels[0]:'<b>Sr</b>';
	 		$y(cell, {width:'30px'});
	 		$y(cell, head_cell_style)

			c_start = 1;
		}

		for(var c=c_start;c<fl.length;c++) {
			var cell = t.rows[0].insertCell(c);
			$y(cell, head_cell_style)
			if(head_labels)
				cell.innerHTML = head_labels[c];
			else
				cell.innerHTML = fl[c].label;
			if(fl[c].width)
				$y(cell, {width:fl[c].width});
			if(widths)
				$y(cell, {width: widths[c]});
			if(fl[c].fieldtype=='Currency')
				$y(cell,{textAlign: 'right'});
			cell.style.fontWeight = 'bold';
		}
		return t;
	}
	
	// no headings if not entries
	
	if(!ds.length) return document.createElement('div');
		
	// make column list
	var newfl = [];
	if(cols&&cols.length) { // custom
		if(cols[0]=='SR')newfl[0]='SR';
		for(var i=0;i<cols.length;i++) {
			for(var j=0;j<fl.length;j++) {
				if(fl[j].fieldname==cols[i]) {
					newfl[newfl.length] = fl[j];
					break;
				}
			}
		}
	} else { // remove hidden cols
		newfl = ['SR']
		for(var j=0;j<fl.length;j++) {
			if(!fl[j].print_hide) {
				newfl[newfl.length] = fl[j];
			}
		}
	}
	fl = newfl;
	
	var t = make_table(fl);
	tl.push(t.wrapper);

	// setup for auto "Sr No" -> SR
	var c_start = 0;
	if(fl[0]=='SR') { c_start = 1; }
		
	// data
	var sr = 0;
	for(var r=0;r<ds.length;r++) {
		if((!condition)||(condition(ds[r]))) {

			// check for page break
			if(ds[r].page_break) { var t = make_table(fl); tl.push(t.wrapper); }

			var rowidx = t.rows.length; 
			sr++
			var row = t.insertRow(rowidx);
			if(c_start) { 
				var cell = row.insertCell(0);
				cell.innerHTML = sr;
				$y(cell, cell_style);
			}
			
			// add values
			for(var c=c_start;c<fl.length;c++) {
				var cell = row.insertCell(c);
				$y(cell, cell_style);

				$s(cell, ds[r][fl[c].fieldname], fl[c].fieldtype);
				if(fl[c].fieldtype=='Currency')
					cell.style.textAlign = 'right';
			}
		}
	}	
	if(tl.length>1) return tl; // multiple tables with page breakes
	else return tl[0];
}
