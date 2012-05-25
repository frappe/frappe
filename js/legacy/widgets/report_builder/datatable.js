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

/// Data Table


_r.scroll_head = function(ele) {
	var h = ele.childNodes[0];
	h.style.top = cint(ele.scrollTop) + 'px';
}

_r.DataTable = function(html_fieldname, dt, repname, hide_toolbar) {
	
	
  var me = this;
  if(html_fieldname.substr) {
	  var html_field = cur_frm.fields_dict[html_fieldname];
  
	  // override onrefresh
	  html_field.onrefresh = function() {
	  	if(me.docname != cur_frm.docname) {
	  	  me.clear_all();
	  	  me.docname = cur_frm.docname;
	  	}
	  }
  
	  var parent = html_field.wrapper;
	  datatables[html_fieldname] = this;
  } else {
  	var parent = html_fieldname;
  }

  this.start_rec = 1;
  this.page_len = 50;
  this.repname = repname;
  this.dt = dt;
  this.no_limit = false;
  this.query = '';
  this.has_index = 1;
  this.has_headings = 1;  //this.sort_options = {};
  this.disabled_options = {};
  
  this.levels = [];
  
  // make ui

  // new link
  if(this.dt) {
    var tw = $a(parent, 'div');
  	var t = $a(tw, 'div', 'link_type');
  	t.style.cssFloat = 'right';
  	$h(tw, '14px');
  	t.style.margin = '2px 0px';
  	t.style.fontSize = '11px';
  	t.onclick = function() { new_doc(me.dt); }
  	t.innerHTML = 'New '+ this.dt;
  }

  // toolbar
  if(!hide_toolbar) this.make_toolbar(parent);

  this.wrapper = $a(parent, 'div', 'report_tab');
  $h(this.wrapper, cint(screen.height * 0.35) + 'px');

  this.wrapper.onscroll = function() {_r.scroll_head(this); }
  
  this.hwrapper = $a(this.wrapper, 'div', 'report_head_wrapper');
  this.twrapper = $a(this.wrapper, 'div', 'report_tab_wrapper');
  
  this.no_data_tag = $a(this.wrapper, 'div', 'report_no_data');
  this.no_data_tag.innerHTML = 'No Records Found';

  this.fetching_tag = $a(this.wrapper, 'div', '', {height:'100%', background:'url("images/lib/ui/square_loading.gif") center no-repeat', display:'none'});  
}

_r.DataTable.prototype.add_icon = function(parent, imgsrc) {
  var i = $a(parent, 'img');
  i.style.padding = '2px';
  i.style.cursor = 'pointer';
  i.setAttribute('src', 'images/lib/icons/'+imgsrc+'.gif');
  return i;
}

_r.DataTable.prototype.set_no_limit = function(v) {
	if(v) {
		this.no_limit = 1;
		$dh(this.page_len_sel.wrapper);
	} else {
		this.no_limit = 0;
		$ds(this.page_len_sel.wrapper);		
	}
}

_r.DataTable.prototype.make_toolbar = function(parent) {
  var me = this;
  
  // headbar
  this.hbar = $a(parent, 'div', '', {margin:'8px 0px 16px 0px'});

  var ht = make_table(this.hbar,1,3,'100%',['40%','40%','20%'],{verticalAlign:'middle'});
  var div = $a($td(ht,0,0), 'div');
  
  // sort select
  var t = make_table($td(ht,0,1),1,6,null,[null,null,null,'20px',null,null],{verticalAlign:'middle'});

  $td(t,0,0).innerHTML = 'Sort By:'; $y($td(t,0,1),{textAlign:'right',paddingRight:'4px'});
  
  this.sort_sel = $a($td(t,0,2), 'select','',{width:'100px'});

  this.sort_sel.onchange = function() {
    me.start_rec = 1;
    me.run();
  }

  // sort order
  this.sort_icon = this.add_icon($td(t,0,3), 'arrow_down');
  this.sort_order = 'DESC';
  
  this.sort_icon.onclick = function() {
  	if(me.sort_order=='ASC') me.set_desc();
    else me.set_asc();

    me.start_rec = 1;
    me.run();
  }

  // page len

  $td(t,0,4).innerHTML = 'Per Page:'; $y($td(t,0,4),{textAlign:'right',paddingRight:'4px'});  
  var s = new SelectWidget($td(t,0,5), ['50','100','500','1000'], '70px');
  s.inp.value = '50';

  s.inp.onchange = function() { 
  	me.page_len = flt(this.value);
  }
  this.page_len_sel = s;

  var c1 = $td(ht,0,2);
  c1.style.textAlign = 'right';

  // first page
  var ic = this.add_icon(c1, 'resultset_first');
  ic.onclick = function() {
  	me.start_rec = 1;
  	me.run();
  }
  
  // prev page
  var ic = this.add_icon(c1, 'resultset_previous');
  ic.onclick = function() {
    if(me.start_rec - me.page_len <= 0)return;
  	me.start_rec = me.start_rec - me.page_len;
  	me.run();
  }
  
  // next page
  this.has_next = false;
  var ic = this.add_icon(c1, 'resultset_next');
  ic.onclick = function() {
    if(!me.has_next)return;
  	me.start_rec = me.start_rec + me.page_len;
  	me.run();
  }

}

_r.DataTable.prototype.set_desc = function() {
	this.sort_icon.src = 'images/lib/icons/arrow_down.gif'; this.sort_order='DESC';
}
_r.DataTable.prototype.set_asc = function(icon) {
	this.sort_icon.src = 'images/lib/icons/arrow_up.gif'; this.sort_order='ASC'; 
}

////

_r.DataTable.prototype.set_sort_option_disabled = function(label, disabled) {
  // has bugs due to sequencing
  // may not set during load
	
  var s = this.sort_sel;
  if(disabled) {
  	// remove this option
    for(var i=0; i<s.options.length; i++) {
      if(s.options[i] && s.options[i].text==label) {
        this.disabled_options[label] = s.options[i];
        s.remove(i);
      }
    }
  } else {
  	// get it back
    if(this.disabled_options[label]) {
      try {
        s.add(this.disabled_options[label], s.options[s.options.length-1]);
      } catch(e) {
      	try {
      	  s.add(this.disabled_options[label], s.options.length-1);
      	} catch (e) { }
      }
      this.disabled_options[label] = null;
    }
  }
  
  
}

_r.DataTable.prototype.add_sort_option = function(label, val) {
  var s = this.sort_sel;
  s.options[s.options.length] = 
         new Option(label, val, false, s.options.length==0?true:false);
}


_r.DataTable.prototype.update_query = function(no_limit) { 

  // add sorting
  if((_r.rb_con.cur_rb && _r.rb_con.cur_rb.get_query) || (this.search_criteria && this.search_criteria.custom_query)) {
  	// no sorting if custom_query or get_query
  } else {
	if(!sel_val(this.sort_sel)) {
		this.sort_sel.selectedIndex = 0; // select the first value (IE)
	}
	this.query += NEWLINE 
             + ' ORDER BY ' + sel_val(this.sort_sel)
             + ' ' + this.sort_order;
  }
  
  if(no_limit || this.no_limit) {
    if(this.show_query) alert(this.query);
  	return;
  }
  
  // add paging  
  this.query += ' LIMIT ' + (this.start_rec-1) + ',' + this.page_len;
  if(this.show_query)
	alert(this.query);

}

_r.DataTable.prototype._get_query = function(no_limit) {
	$dh(this.no_data_tag);
	this.show_query = 0;
  	if(this.make_query)
  		this.make_query();
	this.update_query(no_limit);
}

_r.DataTable.prototype.run = function() {
  if(this.validate && !this.validate())
    return;

  if(_r.rb_con.cur_rb) {
  	if(_r.rb_con.cur_rb.large_report == 1) {
  	  msgprint("This is a very large report and cannot be shown in the browser as it is likely to make your browser very slow.<br><br>Please click on 'Export' to open in a spreadsheet");
  	  return;
  	}
  	_r.rb_con.cur_rb.mytabs.items['Result'].expand();
  }
  
  var me = this;
  this._get_query();
  
  // preset data
  if(this.set_data) {
  	this.show_result(this.set_data);
  	this.set_data = null;
  	return;
  }
    
  $ds(this.fetching_tag);
  if($.browser.mozilla)this.clear_all();
  
  var args = { 
			'query':me.query,
			'report_name': '_r.DataTable', 
			'show_deleted':1,
			'sc_id':me.search_criteria ? me.search_criteria.name : '',
			'filter_values':me.filter_vals ? docstring(me.filter_vals) : '',
			'roles':'["'+user_roles.join('","')+'"]'
		}

  if(this.is_simple) args.is_simple = 1;

  $c('webnotes.widgets.query_builder.runquery', args, function(r,rt) {  
  	$dh(me.fetching_tag); 
  	me.show_result(r,rt); 
  });
  
}

_r.DataTable.prototype.clear_all = function() {
	// clear old
	if(this.htab && this.htab.parentNode) {
		this.htab.parentNode.removeChild(this.htab); delete this.htab; }
	if(this.tab && this.tab.parentNode) {
		this.tab.parentNode.removeChild(this.tab); delete this.tab; }
	$dh(this.no_data_tag);

}

_r.DataTable.prototype.has_data = function() {
	if(this.htab && this.htab.rows.length)return 1;
	else return 0;
}

_r.DataTable.prototype.show_result = function(r, rt) {
	// clear old
	var me = this;
	this.clear_all();

	this.rset = eval(r.values);

	if(this.rset && this.rset.length) {

		// add 
		if(this.has_headings) {
			this.htab = $a(this.hwrapper, 'table');
			$y(this.twrapper,{top:'25px',borderTop:'0px'});
		}
		this.tab = $a(this.twrapper, 'table');
	
		this.colwidths  = eval(r.colwidths);
		this.coltypes   = eval(r.coltypes);
		this.coloptions = eval(r.coloptions);
		this.colnames = eval(r.colnames);
	
		$y(this.tab,{tableLayout:'fixed'});
	
		if(this.beforetableprint)this.beforetableprint(this);

		// heading
		if(this.has_headings) this.make_head_tab(this.colnames);
	
		// data
	 	var start = this.start_rec;
	 	
		// show max 1000
	 	var rset_len = this.rset.length;
	 	if(rset_len > 1000) {
	 		msgprint("Showing only 1000 records out of " + rset_len + ". Use 'Export' to see all records");
	 		rset_len = 1000;
	 	}
	  
		for(var vi=0; vi<rset_len; vi++) {
			var row = this.tab.insertRow(vi);
			// for script

			if(this.has_index) {
				var c0 = row.insertCell(0);
				$w(c0, '30px');
				$a(c0, 'div', '', {width:'23px'}).innerHTML = start;
			}
	      
			// cells
			start++;      
			for(var ci=0;ci < this.rset[vi].length;ci++) {
				this.make_data_cell(vi, ci, this.rset[vi][ci]);
			}
		  
			if(this.afterrowprint) {
				row.data_cells = {}; row.data = {};
				for(var ci=0;ci< this.colnames.length;ci++) {
					row.data[this.colnames[ci]] = this.rset[vi][ci];
					row.data_cells[this.colnames[ci]] = row.cells[ci+1];
				}f
				this.afterrowprint(row);
			}
  
		}

		// has next page?
		if(this.rset.length && this.rset.length>=this.page_len)this.has_next = true;
	
		// style
		if(r.style) {
			for(var i=0;i<r.style.length;i++) {
				$yt(this.tab,r.style[i][0],r.style[i][1],r.style[i][2]);
			}
		}	
	
		// after table print
		if(this.aftertableprint) this.aftertableprint(this.tab);


	} else {
		$ds(this.no_data_tag);
	}
}

_r.DataTable.prototype.get_col_width = function(i) {
	if(this.colwidths 
		&& this.colwidths.length 
			&& this.colwidths[i])
				return cint(this.colwidths[i]) +'px';
	else return '100px';
}

_r.DataTable.prototype.make_head_tab = function(colnames) {
	var r0 = this.htab.insertRow(0);
	if(this.has_index) {
		var c0 = r0.insertCell(0);
		c0.className = 'report_head_cell';
		$w(c0, '30px');
		$a(c0, 'div').innerHTML = 'Sr';
		this.total_width = 30;  
	}
	
	for(var i=0;i<colnames.length;i++) {
		var w = this.get_col_width(i);
		this.total_width+=cint(w);  
	
		var c = r0.insertCell(r0.cells.length);
		c.className = 'report_head_cell';
		if(w)$w(c, w);
		$a(c,'div').innerHTML = colnames[i];
		c.val = colnames[i];
	}
	$w(this.htab, this.total_width + 'px');
	$w(this.tab, this.total_width + 'px');
}

_r.DataTable.prototype.make_data_cell = function(ri, ci, val) {
  var row = this.tab.rows[ri];
  var c = row.insertCell(row.cells.length);
  
  // row style:
  if(row.style.color) 
  	c.style.color = row.style.color;
  if(row.style.backgroundColor) 
  	c.style.backgroundColor = row.style.backgroundColor;
  if(row.style.fontWeight) 
  	c.style.fontWeight = row.style.fontWeight;
  if(row.style.fontSize) 
  	c.style.fontSize = row.style.fontSize;
  
  var w = this.get_col_width(ci);
  if(w)$w(c, w);
  c.val = val;
  
  var me = this;

  c.div = $a(c, 'div', '', {width:(cint(w)-7)+'px'});
  $s(c.div, val, this.coltypes[ci], this.coloptions[ci])
}

_r.DataTable.prototype.do_print = function() {
	this._get_query(true);  
	
	args = {
		query : this.query,
		title : this.rep_name?this.rep_name:this.dt,
		colnames : null,
		colwidhts : null,
		coltypes : null, 
		has_index : this.has_index, 
		has_headings: this.has_headings,
		check_limit : 1,
		is_simple : (this.is_simple ? 'Yes' : ''),
		sc_id : (this.search_criteria ? this.search_criteria.name : ''),
		filter_values : docstring(this.filter_vals),
		//finder: this.finder ? this.finder : null
	};
	
	wn.require('js/print_query.js');	
	_p.print_query = new _p.PrintQuery();
	_p.print_query.show_dialog(args);
}

_r.DataTable.prototype.do_export = function() {
	this._get_query(true);

	var me = this;
	export_query(this.query, function(q) {
		export_csv(q, (me.rep_name?me.rep_name:me.dt), (me.search_criteria?me.search_criteria.name:''), me.is_simple, docstring(me.filter_vals));	
	});
}

// Calculator 
// ----------
_r.DataTable.prototype.do_calc = function() {
	_r.show_calc(this.tab, this.colnames, this.coltypes, 1);
}

_r.DataTable.prototype.get_col_data = function(colname) {
	var ci = 0;
	if(!this.htab) return [];
    for(var i=1;i<this.htab.rows[0].cells.length;i++) {
		var hc = this.htab.rows[0].cells[i];
    	if(hc.val == colname) {
    		ci = i;
    		break;
    	}
    }
	
	var ret = [];
	for(var ri=0;ri<this.tab.rows.length;ri++) {
		ret[ret.length] = this.tab.rows[ri].cells[ci].val;
	}
	return ret;
}

_r.DataTable.prototype.get_html = function() {
	var w = document.createElement('div');
	w = $a(w, 'div');
	w.style.marginTop = '16px';
	var tab = $a(w, 'table');

	var add_head_style = function(c, w) {
		c.style.fontWeight = 'bold';
		c.style.border = '1px solid #000';
		c.style.padding = '2px';
		if(w)$w(c, w);
		return c;
	}

	var add_cell_style = function(c) {
		c.style.padding = '2px';
		c.style.border = '1px solid #000';
		return c;
	}

	tab.style.borderCollapse = 'collapse';  
	var hr = tab.insertRow(0);
	var c0 = add_head_style(hr.insertCell(0), '30px');
	c0.innerHTML = 'Sr';
  
	// heading
	for(var i=1;i<this.htab.rows[0].cells.length;i++) {
		var hc = this.htab.rows[0].cells[i];
		var c = add_head_style(hr.insertCell(i), hc.style.width);
		c.innerHTML = hc.innerHTML;
	}
  
	// data
	for(var ri=0;ri<this.tab.rows.length;ri++) {
		var row = this.tab.rows[ri];
		var dt_row = tab.insertRow(tab.rows.length);
		for(var ci=0;ci<row.cells.length;ci++) {
			var c = add_cell_style(dt_row.insertCell(ci));
			c.innerHTML = row.cells[ci].innerHTML;
		}
	}
	return w.innerHTML;
}

