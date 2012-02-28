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

/* ItemBrowserPage
 	+ this.my_page
		+ this.page_layout (wn.PageLayout)
		+ this.wrapper
		+ this.body
			+ ItemBrowser
				+ this.wrapper
					+ this.wtab
						+ body
							+ has_results
								+ head
								+ toolbar_area
							+ no_result
							+ loading_div
						+ sidebar


*/


ItemBrowserPage = function() {
	if(user=='Guest') {
		msgprint("Not Allowed");
		return;
	}
	this.lists = {};
	this.dt_details = {};
	this.cur_list = null;

	this.my_page = page_body.add_page('ItemBrowser');
	this.wrapper = $a(this.my_page,'div');
}

// -------------------------------------------------

ItemBrowserPage.prototype.show = function(dt, label, field_list) {
	var me = this;

	if(wn.boot.profile.can_read.indexOf(dt)==-1) {
		msgprint("No read permission");
		return;
	}
	
	if(this.cur_list && this.cur_list.dt != dt) $dh(this.cur_list.layout.wrapper);
		
	if(!me.lists[dt]) {
		me.lists[dt] = new ItemBrowser(me.wrapper, dt, label, field_list);
	}

	me.cur_list = me.lists[dt];
	me.cur_list.show();
	
	page_body.change_to('ItemBrowser');
}

// -------------------------------------------------

ItemBrowser = function(parent, dt, label, field_list) {	
	var me = this;
	this.label = label ? label : dt;
	this.dt = dt;
	this.field_list = field_list;
	this.tag_filter_dict = {};
	this.items = [];
	this.cscript = {}; // dictionary for custom scripting

	// heading
	var l = get_doctype_label(dt);
	l = (l.toLowerCase().substr(-4) == 'list') ? l : (l + ' List')	

	// make the layout
	this.layout = new wn.PageLayout({
		parent: parent,
		heading: l
	})

	$dh(this.layout.page_head.separator);


	this.layout.results = $a(this.layout.main, 'div');

	// no records
	this.layout.no_records = $a(this.layout.main, 'div');
	this.no_result_area = $a(this.layout.no_records, 
		'div','',{fontSize:'14px', textAlign:'center', padding:'200px 0px'});
	
	// loading...
	this.layout.loading = $a(this.layout.main, 'div','',{padding:'200px 0px', textAlign:'center', fontSize:'14px', color:'#444', display:'none'});
	this.layout.loading.innerHTML = 'Loading<img src="lib/images/ui/button-load.gif" style="margin-bottom: -2px; margin-left: 8px">';
	
	// setup toolbar
	this.setup_toolbar();
		
	// setup list and sidebar
	this.setup_sidebar();
}

// one of "loading", "no_result", "main"
ItemBrowser.prototype.show_area = function(area) {
	$ds(this.layout[area]);
	var al = ['loading','no_records','results'];
	for(var a in al) {
		if(al[a]!=area) 
			$dh(this.layout[al[a]]);
	}
}

ItemBrowser.prototype.setup_sidebar = function() {
	var me = this;
		
	// sidebar
	this.sidebar = new wn.widgets.PageSidebar(this.layout.sidebar_area, {
		sections: [
			{
				title: 'Top Tags',
				render: function(body) {
					new wn.widgets.TagCloud(body, me.dt, function(tag) { me.set_tag_filter(tag) });
				}				
			}
		]
	});
}

// setup the toolbar and archiving and deleteing functionality
ItemBrowser.prototype.setup_toolbar = function() {
	var me = this;
	var parent = $a(this.layout.results, 'div');
	// toolbar
	this.main_toolbar = $a(parent, 'div', '', {padding: '3px', backgroundColor:'#EEE'});
	$br(this.main_toolbar, '3px'); 
	
	this.sub_toolbar = $a(parent, 'div', '', {marginBottom:'7px', padding: '3px', textAlign:'right', fontSize:'11px', color:'#444'});
	
	// archives label
	//this.archives_label = $a(parent, 'div', 'help_box_big',{display:'none'},'Showing from Archives');
	//var span = $a(this.archives_label, 'span', 'link_type', {marginLeft:'8px'}, 'Show Active');
	//span.onclick = function() { me.show_archives.checked = 0; me.show_archives.onclick(); }
	
	this.trend_area = $a(parent, 'div', '', {marginBottom:'16px', padding: '4px', backgroundColor:'#EEF', border: '1px solid #CCF', display:'none'});
	$br(this.trend_area, '5px');
	
	// tag filters
	this.tag_filters = $a(parent, 'div', '', {marginBottom:'8px', display:'none', padding:'6px 8px 8px 8px', backgroundColor:'#FFD'});
	var span = $a(this.tag_filters,'span','',{marginRight:'4px',color:'#444'}); span.innerHTML = '<i>Showing for:</i>';
	this.tag_area = $a(this.tag_filters, 'span');
	
	// select all area
	var div = $a(parent, 'div', '', {margin:'3px 5px'});
	var chk = $a_input(div, 'checkbox');
	var lab = $a(div, 'span', '', {marginLeft:'9px'}, 'Select All');
	chk.onclick = function() {
		for(var i=0; i<me.items.length; i++) {
			me.items[i].check.checked = this.checked;
			me.items[i].check.onclick();
		}
	}
	this.select_all = chk;
}

// -------------------------------------------------

ItemBrowser.prototype.make_checkbox = function(status, checked) {
	var me = this;
	var chk = $a_input(this.sub_toolbar, 'checkbox');
	var lab = $a(this.sub_toolbar, 'span', '', {marginRight:'8px'}, 'Show ' + status);
	chk.onclick = function() { me.run(); }
	chk.checked = checked;
	this['check_'+status] = chk;
}

ItemBrowser.prototype.get_status_check = function() {
	ret = [];
	if(this.check_Draft.checked) ret.push(0);
	if(this.check_Submitted.checked) ret.push(1);
	if(this.check_Cancelled.checked) ret.push(2);
	if(!ret.length) {
		msgprint('Atleast of Draft, Submitted or Cancelled must be checked!');
		return
	}
	return ret;
}

ItemBrowser.prototype.make_toolbar = function() {
	var me = this;

	// new button
	if(inList(profile.can_create, this.dt)) {
		this.new_button = $btn(this.main_toolbar, '+ New ' + get_doctype_label(this.dt), function() { newdoc(me.dt) }, {fontWeight:'bold',marginRight:'0px'}, 'green');
	}
	
	// archive, delete
	//if(in_list(profile.can_write, this.dt)) {
	//	this.archive_btn = $btn(this.main_toolbar, 'Archive', function() { me.archive_items(); }, {marginLeft:'24px'});
	//} 
	if(this.dt_details.can_cancel) {
		this.delete_btn = $btn(this.main_toolbar, 'Delete', function() { me.delete_items(); }, {marginLeft: '24px'});
	}
		
	// search box
	this.search_input = $a(this.main_toolbar, 'input', '', {width:'120px', marginLeft:'24px', border:'1px solid #AAA'});
	this.search_btn = $btn(this.main_toolbar, 'Search', function() { me.run(); }, {marginLeft:'4px'});	

	// show hide filters
	this.filters_on = 0;
	this.filter_btn = $ln(this.main_toolbar, 'Show Filters', function() { me.show_filters(); }, {marginLeft:'24px'});

	// show hide trend
	//this.trend_on = 0; this.trend_loaded = 0;
	//this.trend_btn = $ln(this.main_toolbar, 'Show Activity', function() { me.show_activity(); }, {marginLeft:'24px'});

	// checks for show cancelled and show archived
	if(this.dt_details.submittable) {
		this.make_checkbox('Draft', 1)
		this.make_checkbox('Submitted', 1)
		this.make_checkbox('Cancelled', 0)
	}
	
	//this.set_archiving();

}

// -------------------------------------------------

ItemBrowser.prototype.set_archiving = function() {
	var me = this;
	
	this.show_archives = $a_input(this.sub_toolbar, 'checkbox');
	var lab = $a(this.sub_toolbar, 'span'); lab.innerHTML = 'Show Archives';
	
	this.show_archives.onclick = function() {
		if(this.checked) {
			if(me.archive_btn) me.archive_btn.innerHTML = 'Restore';
			$(me.archives_label).slideDown();
		} else {
			if(me.archive_btn) me.archive_btn.innerHTML = 'Archive';
			$(me.archives_label).slideUp();
		}
		me.run();
	}
	
}

// -------------------------------------------------

ItemBrowser.prototype.show_filters = function() {
	if(this.filters_on) {
		$(this.lst.filter_wrapper).slideUp();
		this.filters_on = 0;
		this.filter_btn.innerHTML = 'Advanced Search';
	} else {
		$(this.lst.filter_wrapper).slideDown();
		this.filters_on = 1;
		this.filter_btn.innerHTML = 'Hide Filters';
	}
}

// -------------------------------------------------

ItemBrowser.prototype.show_activity = function() {
	var me = this;
	if(this.trend_on) {
		$(this.trend_area).slideUp();
		me.trend_btn.innerHTML = 'Show Activity';
		me.trend_on = 0;
		
	} else {
		
		// show
		if(!this.trend_loaded) {
			// load the trend
			var callback = function(r,rt) {
				me.show_trend(r.message.trend);
				$(me.trend_area).slideDown();
				me.trend_btn.done_working();
				me.trend_btn.innerHTML = 'Hide Activity';
				me.trend_loaded = 1;
				me.trend_on = 1;
			}
			$c('webnotes.widgets.menus.get_trend', {'dt':this.dt}, callback);
			me.trend_btn.set_working();

		} else {
			// slide up and dwon
			$(this.trend_area).slideDown();
			me.trend_btn.innerHTML = 'Hide Activity';
			me.trend_on = 1;
		}
	}
}

// -------------------------------------------------

ItemBrowser.prototype.show = function(onload) {
	$ds(this.layout.wrapper);
	
	if(onload) this.cscript.onload = onload
	
	if(this.loaded && this.lst.n_records) return;
	
	this.show_area('loading');
	
	var me = this;
	var callback = function(r, rt) {
		if(r.message == 'Yes') {
			if(!me.loaded) {
				me.load_details();
			} else {
				me.show_results();
			}
		} else {
			if(me.cscript.onload) me.cscript.onload(this);
			me.show_no_result();
		}
	}
	$c('webnotes.widgets.menus.has_result', {'dt': this.dt}, callback);	
}

// -------------------------------------------------

ItemBrowser.prototype.load_details = function() {
	var me = this;
	var callback = function(r,rt) { 
		me.dt_details = r.message;
		if(r.message) {
			me.make_toolbar();
			me.make_the_list(me.dt, me.layout.results);
			
			// fire onload
			if(me.cscript.onload) 
				me.cscript.onload(me);
			
			me.show_results();
		}
	}

	var fl = this.field_list ? this.field_list.split('\n') : [];
	$c('webnotes.widgets.menus.get_dt_details', {'dt': this.dt, 'fl': JSON.stringify(fl)}, callback);
	this.loaded = 1;
}

// -------------------------------------------------

ItemBrowser.prototype.show_results = function() {
	this.show_area('results');

	set_title(get_doctype_label(this.label));
}

// -------------------------------------------------

ItemBrowser.prototype.show_trend = function(trend) {
	var maxval = 0;
	for(var key in trend) { if(trend[key]>maxval) maxval = trend[key] };

	// head
	var div = $a(this.trend_area, 'div','',{marginLeft:'32px'}); div.innerHTML = 'Activity in last 30 days';
	var wrapper_tab = make_table(this.trend_area, 1, 2, '100%', ['20px',null], {padding:'2px 4px',fontSize:'10px',color:'#888'});

	// y-label
	var ylab_tab = make_table($td(wrapper_tab,0,0),2,1,'100%',['100%'],{verticalAlign:'top', textAlign:'right',height:'24px'});
	$td(ylab_tab,0,0).innerHTML = maxval;

	$y($td(ylab_tab,1,0),{verticalAlign:'bottom'});
	$td(ylab_tab,1,0).innerHTML = '0';

	// infogrid
	var tab = make_table($td(wrapper_tab,0,1), 1, 30, '100%', [], 
		{width:10/3 + '%', border:'1px solid #DDD', height:'40px', verticalAlign:'bottom', textAlign:'center', padding:'2px', backgroundColor:'#FFF'});
		
	// labels
	var labtab = make_table($td(wrapper_tab,0,1), 1, 6, '100%', [], 
		{width:100/6 + '%', border:'1px solid #EEF', height:'16px',color:'#888',textAlign:'right',fontSize:'10px'});
	
	for(var i=0; i<30; i++) {
		var div = $a($td(tab,0,29-i),'div','',{backgroundColor:'#4AC', width:'50%', margin:'auto', height:(trend[i+''] ? (trend[i+'']*100/maxval) : 0) + '%'});
		div.setAttribute('title', trend[i] + ' records');
		
		// date string
		if(i % 5 == 0) {
			$td(labtab,0,5-(i/5)).innerHTML = dateutil.obj_to_user(dateutil.add_days(new Date(), -i));
			$y($td(tab,0,i-1),{'backgroundColor':'#EEE'});
		}
	}
	$td(labtab,0,5).innerHTML = 'Today';
}

// -------------------------------------------------

ItemBrowser.prototype.show_no_result = function() {
	this.show_area('no_records');

	this.no_result_area.innerHTML = 
		repl('No %(dt)s found. <span class="link_type" onclick="newdoc(\'%(dt)s\')">Click here</span> to create your first %(dt)s!', {dt:get_doctype_label(this.dt)});
	set_title(get_doctype_label(this.label));
}

// -------------------------------------------------

ItemBrowser.prototype.make_new = function(dt, label, field_list) {
	// make the list
	this.make_the_list(dt, this.layout.results);
}

// -------------------------------------------------

ItemBrowser.prototype.add_search_conditions = function(q) {
	if(this.search_input.value) {
		q.conds += ' AND ' + q.table + '.name LIKE "%'+ this.search_input.value +'%"';
	}
}	
	
// -------------------------------------------------

ItemBrowser.prototype.add_tag_conditions = function(q) {
	var me = this;
	
	if(keys(me.tag_filter_dict).length) {
		var cl = [];
		for(var key in me.tag_filter_dict) {
			var val = key;
			var op = '=';
				
			var fn = me.tag_filter_dict[key].fieldname;
			fn = fn ? fn : '_user_tags';
				
			// conditions based on user tags
			if(fn=='docstatus')val=(key=='Draft'?'0':'1');
			else if(fn=='_user_tags'){ val='%,'+key + '%'; op=' LIKE '; }
						
			cl.push(q.table + '.`' + fn + '`'+op+'"' + val + '"');
		}
		if(cl)
			q.conds += ' AND ' + cl.join(' AND ') + ' ';
	}
}
	
// -------------------------------------------------
	
ItemBrowser.prototype.make_the_list  = function(dt, wrapper) {
	var me = this;
	var lst = new Listing(dt, 1);
	lst.dt = dt;
	lst.cl = this.dt_details.columns;

	lst.opts = {
		cell_style : {padding:'0px 2px'},
		alt_cell_style : {backgroundColor:'#FFFFFF'},
		hide_export : 1,
		hide_print : 1,
		hide_rec_label: 0,
		show_calc: 0,
		show_empty_tab : 0,
		show_no_records_label: 1,
		show_new: 0,
		show_report: 1,
		no_border: 1,
		append_records: 1,
		formatted: 1
	}
		
	if(user_defaults.hide_report_builder) lst.opts.show_report = 0;
	
	// build th query
	lst.is_std_query = 1;
	lst.get_query = function() {
		q = {};
		var fl = [];
		q.table = repl('`%(prefix)s%(dt)s`', {prefix: 'tab'/*(me.show_archives.checked ? 'arc' : 'tab')*/, dt:this.dt});
	
		// columns
		for(var i=0;i<this.cl.length;i++) {
			//if(!(me.show_archives && me.show_archives.checked && this.cl[i][0]=='_user_tags'))
			fl.push(q.table+'.`'+this.cl[i][0]+'`')
		}

		if(me.dt_details.submittable) {
			fl.push(q.table + '.docstatus');

			var tmp = me.get_status_check();
			if(!tmp) { this.query=null; return; }

			// docstatus conditions
			q.conds = q.table + '.docstatus in ('+ tmp.join(',') +') ';
			
		} else {
			q.conds = q.table + '.docstatus != 2'
		}

		// columns
		q.fields = fl.join(', ');

				
		// filter conditions
		me.add_tag_conditions(q);

		// filter conditions
		me.add_search_conditions(q);
				
		this.query = repl("SELECT %(fields)s FROM %(table)s WHERE %(conds)s", q);
		this.query_max = repl("SELECT COUNT(*) FROM %(table)s WHERE %(conds)s", q);
		//if(me.show_archives.checked)
		//	this.prefix = 'arc';
		//else
		this.prefix = 'tab'
		
	}
	
	// make the columns
	lst.colwidths=['100%']; lst.coltypes=['Data']; lst.coloptions = [''];
	
	// show cell
	lst.show_cell = function(cell, ri, ci, d) {
		me.items.push(new ItemBrowserItem(cell, d[ri], me));
	}
	
	lst.make(wrapper);

	// add the filters
	var sf = me.dt_details.filters;
	for(var i=0;i< sf.length;i++) {
		var fname = sf[i][0]; var label = sf[i][1]; var ftype = sf[i][2]; var fopts = sf[i][3];

		if(in_list(['Int','Currency','Float','Date'], ftype)) {
			lst.add_filter('From '+label, ftype, fopts, dt, fname, '>=');
			lst.add_filter('To '+label, ftype, fopts, dt, fname, '<=');
		} else {
			lst.add_filter(label, ftype, fopts, dt, fname, (in_list(['Data','Text','Link'], ftype) ? 'LIKE' : ''));
		}
	}

	$dh(lst.filter_wrapper);
			
	// default sort
	lst.set_default_sort('modified', 'DESC');
	this.lst = lst;
	lst.run();
}

// -------------------------------------------------

ItemBrowser.prototype.run = function() {
	this.items = [];
	this.select_all.checked = false;
	this.lst.run();
}

// -------------------------------------------------

ItemBrowser.prototype.get_checked = function() {
	var il = [];
	for(var i=0; i<this.items.length; i++) {
		if(this.items[i].check.checked) il.push([this.dt, this.items[i].dn]);
	}
	return il;
}

// -------------------------------------------------

ItemBrowser.prototype.delete_items = function() {
	var me = this;
	if(confirm('This is PERMANENT action and you cannot undo. Continue?'))
		$c('webnotes.widgets.menus.delete_items', {'items': JSON.stringify(this.get_checked()) }, function(r, rt) { if(!r.exc) me.run(); })
}

// -------------------------------------------------

ItemBrowser.prototype.archive_items = function() {
	var me = this;
	var arg = {
		'action': this.show_archives.checked ? 'Restore' : 'Archive'
		,'items': JSON.stringify(this.get_checked())
	}
	$c('webnotes.widgets.menus.archive_items', arg, function(r, rt) { if(!r.exc) me.run(); })
}

// -------------------------------------------------

ItemBrowser.prototype.set_tag_filter = function(tag) {
	var me = this;
		
	// check if exists
	if(in_list(keys(me.tag_filter_dict), tag.label)) return;
	
	// create a tag in filters
	var filter_tag = new SingleTag({
		parent: me.tag_area,
		label: tag.label,
		dt: me.dt,
		color: tag.color
	});

	filter_tag.fieldname = tag.fieldname;

	// remove tag from filters
	filter_tag.remove = function(tag_remove) {
		$(tag_remove.body).fadeOut();
		delete me.tag_filter_dict[tag_remove.label];
		
		// hide everything?
		if(!keys(me.tag_filter_dict).length) {
			$(me.tag_filters).slideUp(); // hide
		}
		
		// run
		me.run();
	}

	// add to dict
	me.tag_filter_dict[tag.label] = filter_tag;
	$ds(me.tag_filters);
	
	// run
	me.run();
}

// ========================== ITEM ==================================

function ItemBrowserItem(parent, det, ib) {
	this.wrapper = $a(parent, 'div');
	$y(this.wrapper, {borderTop:'1px solid #DDD'});
	
	this.tab = make_table(this.wrapper, 1, 2, '100%', ['24px', null]);
	this.body = $a($td(this.tab, 0, 1), 'div');
	this.link_area = $a(this.body, 'div')
	this.details_area = this.link_area // $a(this.body, 'div');
	
	this.det = det;
	this.ib = ib;
	this.dn = det[0];
	
	this.make_check();
	this.make_tags();
	this.make_details();
	this.add_timestamp();
}

// -------------------------------------------------

ItemBrowserItem.prototype.make_check = function() {
	if(this.ib.archive_btn || this.ib.delete_btn) {
		var me = this;
		this.check = $a_input($td(this.tab, 0, 0), 'checkbox');
		this.check.onclick = function() {
			if(this.checked) {
				$y(me.wrapper, {backgroundColor:'#FFC'});
			} else {
				$y(me.wrapper, {backgroundColor:'#FFF'});
			}
		}
	}
}

// -------------------------------------------------

ItemBrowserItem.prototype.make_details = function() {

	// link
	var me = this;
	var div = this.details_area;
	
	var span = $a(this.link_area, 'span', 'link_type', {fontWeight:'bold', marginRight: '7px'});
	span.innerHTML = me.dn;
	span.onclick = function() { loaddoc(me.ib.dt, me.dn, null, null, (me.ib.show_archives ? me.ib.show_archives.checked : null)); }

	var cl = me.ib.dt_details.columns;
	var tag_fields = me.ib.dt_details.tag_fields ? me.ib.dt_details.tag_fields.split(',') : []; 
	for(var i=0;i<tag_fields.length;i++) tag_fields[i] = strip(tag_fields[i]);
	
	if(me.ib.dt_details.subject) {
		// if there is a subject mentioned in the
		// doctype, build the string based on the
		// subject string
		
		var det_dict = {};
		for(var i=0; i<cl.length; i++) {
			var fieldname = cl[i][0];
			det_dict[fieldname] = me.det[i] ? me.det[i] : '';
			
			// set tag (optionally)
			if(in_list(tag_fields, fieldname))
				me.taglist.add_tag(me.det[i], 1, fieldname);
		}
		// write the subject
		var s = repl(me.ib.dt_details.subject, det_dict);
		if(s.substr(0,5)=='eval:') s = eval(s.substr(5));
		$a(div, 'span', '', {color:'#444'}, s)
	} else {
		
		// old -style - based on search_fields!
		// properties
		
		var tmp = [];
		var first_property = 1;
		for(var i=3; i<me.det.length; i++) {
			if(cl[i] && cl[i][1] && me.det[i]) {
				// has status, group or type in the label
				if(cl[i][1].indexOf('Status') != -1 || 
					cl[i][1].indexOf('Group') != -1 || 
					cl[i][1].indexOf('Priority') != -1 || 
					cl[i][1].indexOf('Type') != -1) {
						me.taglist.add_tag(me.det[i], 1, cl[i][0], '#c0c0c0');	
				} else {

					// separator
					if(!first_property) {
						var span = $a(div,'span'); span.innerHTML = ',';
					} else first_property = 0;

					// label
					var span = $a(div,'span','',{color:'#888'});
					span.innerHTML = ' ' + cl[i][1] + ': ';

					// value
					var span = $a(div,'span');
					$s(span,me.det[i],(cl[i][2]=='Link'?'Data':cl[i][2]), cl[i][3]);
				}
			}
		}
		
	}
	

}

// -------------------------------------------------

ItemBrowserItem.prototype.make_tags = function() {
	// docstatus tag
	var docstatus = cint(this.det[this.det.length - 1]);

	// make custom tags
	var me = this;
	var tl = this.det[2] ? this.det[2].split(',') : [];
	var div = $a(this.body, 'div', '', {margin: '7px 0px'})
	this.taglist = new TagList(div, tl, this.ib.dt, this.dn, 0, function(tag) { me.ib.set_tag_filter(tag); });
}

// -------------------------------------------------

ItemBrowserItem.prototype.add_timestamp = function() {
	// time
	var div = $a(this.body, 'div', '', {color:'#888', fontSize:'11px'});
	div.innerHTML = comment_when(this.det[1]);
}

