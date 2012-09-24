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

search_fields = {};

// Search Selector 2.0
// -------------------

function setlinkvalue(name) {
	//selector.input.set(name);// in local - this will be set onchange
	selector.input.set_input_value(name); // on screen
	selector.hide();
}

// Link Selector
// -------------

function makeselector() {
	var d = new Dialog(540,440, 'Search');

	d.make_body([
		['HTML', 'Help'],
		['Data', 'Beginning With', 'Tip: You can use wildcard "%"'],
		['Select', 'Search By'],
		['Button', 'Search'],
		['HTML', 'Result']
	]);

	// search with
	var inp = d.widgets['Beginning With'];
	var field_sel = d.widgets['Search By'];
	var btn = d.widgets['Search'];

	// result
	d.sel_type = '';
	d.values_len = 0;
	d.set = function(input, type, label) {
		d.sel_type = type; 
		d.input = input;
		if(d.style!='Link') {
			d.rows['Result'].innerHTML ='';
			d.values_len = 0;
		}
		d.style = 'Link';
		d.set_query_description()

		if(!d.sel_type)d.sel_type = 'Value';
		d.set_title("Select");
		d.set_query_description('Select a "'+ d.sel_type +'" for field "'+label+'"');
	}
	d.set_search = function(dt) {
		if(d.style!='Search') {
			d.rows['Result'].innerHTML ='';
			d.values_len = 0;
		}
		d.style = 'Search';
		if(d.input) { d.input = null; sel_type = null; }
		d.sel_type = get_label_doctype(dt);
		d.set_title('Quick Search for ' + dt);
	}

	$(inp).keydown(function(e) {
		if(e.which==13) {
			if(!btn.disabled)btn.onclick();
		}
	})

	d.set_query_description = function(txt) {
		txt = d.input && d.input.query_description || txt;
		if(txt) {
			d.rows['Help'].innerHTML ='<div class="help-box" style="margin-top:0px">' + txt + '</div>';
		} else {
			d.rows['Help'].innerHTML =''
		}
	}
	d.onshow = function() {
		if(d.set_doctype!=d.sel_type) {
			d.rows['Result'].innerHTML ='';
			d.values_len = 0;
		}

		inp.value = '';
		if(d.input && d.input.txt.value) {
			inp.value = d.input.txt.value;
		}
		try{inp.focus();} catch(e){}

		if(d.input) d.input.set_get_query();

		// temp function to strip labels from search fields
		var get_sf_list = function(dt) {
			var l = []; var lf = search_fields[dt];
			for(var i=0; i<lf.length; i++) l.push(lf[i][1]);
			return l;
		}

		// set fields
		$ds(d.rows['Search By']);

		if(search_fields[d.sel_type]) {
			empty_select(field_sel);
			add_sel_options(field_sel, get_sf_list(d.sel_type), 'ID');
		} else {
			// set default select by
			empty_select(field_sel);
			add_sel_options(field_sel, ['ID'], 'ID');

			$c('webnotes.widgets.search.getsearchfields', {'doctype':d.sel_type}, function(r,rt) {
				search_fields[d.sel_type] = r.searchfields;
				empty_select(field_sel);
				add_sel_options(field_sel, get_sf_list(d.sel_type));
				field_sel.selectedIndex = 0;
			} );
		}
	}
	d.onhide = function() {
		//if(d.input && d.input.txt) // link, call onchange
		//	d.input.txt.set_input_value()
	}

	btn.onclick = function() {
		if(this.disabled) return;

		this.args.is_ajax = true;
		this.set_working();
		d.set_doctype = d.sel_type;
		var q = '';
		args = {};

		if(d.input && d.input.get_query) {
			var doc = {};
			args.is_simple = 1;
			if(cur_frm) doc = locals[cur_frm.doctype][cur_frm.docname];
			var q = d.input.get_query(doc, d.input.doctype, d.input.docname);
			if(!q) { return ''; }
		}

		// for field type, return field name
		var get_sf_fieldname = function(v) {
			var lf = search_fields[d.sel_type];

			// still loading options
			if(!lf)
				return 'name'

			for(var i=0; i<lf.length; i++) if(lf[i][1]==v) return lf[i][0];
		}

		// build args
		$.extend(args, {
			'txt':strip(inp.value)
			,'doctype':d.sel_type
			,'query':q
			,'searchfield':get_sf_fieldname(sel_val(field_sel))
		});

		// run the query
		$c('webnotes.widgets.search.search_widget',
			args,
			function(r, rtxt) {
				btn.done_working();
				if(r.coltypes)r.coltypes[0]='Link'; // first column must always be selectable even if it is not a link
				d.values_len = r.values.length;
				d.set_result(r);
			}, function() { btn.done_working(); });
	}

	d.set_result = function(r) {
		d.rows['Result'].innerHTML = '';
		var c = $a(d.rows['Result'],'div','comment',{paddingBottom:'4px',marginBottom:'4px',borderBottom:'1px solid #CCC', marginLeft:'4px'});
		if(r.values.length==50)
			c.innerHTML = 'Showing max 50 results. Use filters to narrow down your search';
		else
			c.innerHTML = 'Showing '+r.values.length+' resuts.';

		var w = $a(d.rows['Result'],'div','',{height:'240px',overflow:'auto',margin:'4px'});
		for(var i=0; i<r.values.length; i++) {
			var div = $a(w,'div','',
				{marginBottom:'4px',paddingBottom:'4px',borderBottom:'1px dashed #CCC'});

			// link
			var l = $a($a(div,'div'),'span','link_type'); 
			l.innerHTML = r.values[i][0]; 
			l.link_name = r.values[i][0]; 
			l.dt = r.coloptions[0];

			if(d.input)
				l.onclick = function() { setlinkvalue(this.link_name); }
			else
				l.onclick = function() { loaddoc(this.dt, this.link_name); d.hide(); }

			// support
			var cl = []
			for(var j=1; j<r.values[i].length; j++) cl.push(r.values[i][j]);
			var c = $a(div,'div','comment',{marginTop:'2px'}); c.innerHTML = cl.join(', ');
		}

	}

	selector = d;
}
