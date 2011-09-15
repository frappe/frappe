// requires
// menu.js
// search.js
// datatype.js
// dom.js

var about_dialog;

function WNToolbar(parent) {
	var me = this;
	
	this.setup = function() {
		this.wrapper = $a(parent, 'div', '', {color:'#FFF', padding:'2px 0px' });
		set_gradient(this.wrapper, '#444', '#000');

		this.table_wrapper = $a(this.wrapper, 'div', '', {marginLeft:'4px', padding:'2px'});
		this.body_tab = make_table(this.table_wrapper, 1, 3, '100%', ['0%','64%','36%'],{verticalAlign:'middle'});
		
		this.menu = new MenuToolbar($td(this.body_tab,0,1));
		this.setup_home();
		this.setup_new();
		this.setup_search();
		this.setup_recent();
		if(in_list(user_roles, 'Administrator'))
			this.setup_options();
		this.setup_help();

		this.setup_report_builder();

		this.setup_logout();
	}
	
	// Options
	// ----------------------------------------------------------------------------------------
	this.setup_options = function() {
		var tm = this.menu.add_top_menu('Pages', function() { }, "sprite-pages");
		
		var fn = function() {
			if(this.dt=='Page')
				loadpage(this.dn);
			else
				loaddoc(this.dt, this.dn);
			mclose();
		}
	
		// add start items
		profile.start_items.sort(function(a,b){return (a[4]-b[4])});
		for(var i=0;i< profile.start_items.length;i++) {
			var d = profile.start_items[i];
			var mi = this.menu.add_item('Pages',d[1], fn);
			mi.dt = d[0]; mi.dn = d[5]?d[5]:d[1];
		}
	}
	
	// Home
	// ----------------------------------------------------------------------------------------

	this.setup_home = function() {
		me.menu.add_top_menu('Home', function() { loadpage(home_page); }, "sprite-home");		
	}

	// Recent
	// ----------------------------------------------------------------------------------------
	this.setup_recent = function() {
	
		this.rdocs = me.menu.add_top_menu('Recent', function() {  }, "sprite-recent");
		this.rdocs.items = {};
	
		var fn = function() { // recent is only for forms
			loaddoc(this.dt, this.dn);
			mclose();
		}
		
		// add to recent
		this.rdocs.add = function(dt, dn, on_top) {
			var has_parent = false;
			if(locals[dt] && locals[dt][dn] && locals[dt][dn].parent) has_parent = true;
			
			if(!in_list(['Start Page','ToDo Item','Event','Search Criteria'], dt) && !has_parent) {
	
				// if there in list, only bring it to top
				if(this.items[dt+'-'+dn]) {
					var mi = this.items[dt+'-'+dn];
					mi.bring_to_top();
					return;
				}
	
				var tdn = dn;
				var rec_label = '<table style="width: 100%" cellspacing=0><tr>'
					+'<td style="width: 10%; vertical-align: middle;"><div class="status_flag" id="rec_'+dt+'-'+dn+'"></div></td>'
					+'<td style="width: 50%; text-decoration: underline; color: #22B; padding: 2px;">'+tdn+'</td>'
					+'<td style="font-size: 11px;">'+get_doctype_label(dt)+'</td></tr></table>';
			
				var mi = me.menu.add_item('Recent',rec_label,fn, on_top);
				mi.dt = dt; mi.dn = dn;	
				this.items[dt+'-'+dn] = mi;
				if(pscript.on_recent_update)pscript.on_recent_update();
			}
		}
		
		// remove from recent
		this.rdocs.remove = function(dt, dn) {
			var it = me.rdocs.items[dt+'-'+dn];
			if(it)$dh(it);
			if(pscript.on_recent_update)pscript.on_recent_update();
		}

		this.rename_notify = function(dt, old, name) {
			me.rdocs.remove(dt, old);
			me.rdocs.add(dt, name, 1);
		}
		rename_observers.push(this);

		// add menu items
		try{ var rlist = JSON.parse(profile.recent); }
		catch(e) { return; /*old style-do nothing*/ }
		
		var m = rlist.length;
		if(m>15)m=15;
		for (var i=0;i<m;i++) {
			var rd = rlist[i]
			if(rd[1]) {
				var dt = rd[0]; var dn = rd[1];
				this.rdocs.add(dt, dn, 0);
			}
		}

	}
	
	// Tools
	// ----------------------------------------------------------------------------------------
	this.setup_help = function() {
		me.menu.add_top_menu('Tools', function() {  }, "sprite-tools");
		this.menu.add_item('Tools','Error Console', function() { err_console.show(); });
		this.menu.add_item('Tools','Clear Cache', function() { $c('webnotes.session_cache.clear',{},function(r,rt){ show_alert(r.message); }) });
		if(has_common(user_roles,['Administrator','System Manager'])) {
			this.menu.add_item('Tools','Download Backup', function() { me.download_backup(); });
		}
		this.menu.add_item('Tools','Web Notes Framework', function() { show_about(); });
	}	

	// New
	// ----------------------------------------------------------------------------------------
	this.setup_new = function() {	
		me.menu.add_top_menu('New', function() { me.show_new(); }, 'sprite-new' );
		me.show_new = function() {
			if(!me.new_dialog) {
				var d = new Dialog(240, 140, "Create a new record");
				d.make_body(
					[['HTML','Select']
					,['Button','Go', function() { me.new_dialog.hide(); new_doc(me.new_sel.inp.value); }]]);
				d.onshow = function(){
					me.new_sel.inp.focus();	
				}
				me.new_dialog = d;
				
				// replace by labels
				var nl = profile.can_create.join(',').split(',');
				for(var i=0;i<nl.length;i++) nl[i]=get_doctype_label(nl[i]);
								
				// labels
				me.new_sel = new SelectWidget(d.widgets['Select'], nl.sort(), '200px');
				me.new_sel.onchange = function() { me.new_dialog.hide(); new_doc(me.new_sel.inp.value); }
			}
			me.new_dialog.show();
		}

		//this.new_sel.inp.onchange = function() { new_doc(me.new_sel.inp.value); this.value = 'Create New...'; }
	}
	
	// Report Builder
	// ----------------------------------------------------------------------------------------
	this.setup_report_builder = function() {
		me.menu.add_top_menu('Report', function() { me.show_rb(); }, 'sprite-report' );
		me.show_rb = function() {
			if(!me.rb_dialog) {
				var d = new Dialog(240, 140, "Build a report for");
				d.make_body(
					[['HTML','Select']
					,['Button','Go', function() { me.rb_dialog.hide(); loadreport(me.rb_sel.inp.value, null, null, null, 1); }]]);
				d.onshow = function(){
					me.rb_sel.inp.focus();	
				}
				me.rb_dialog = d;			

				// replace by labels
				var nl = profile.can_get_report.join(',').split(',');
				for(var i=0;i<nl.length;i++) nl[i]=get_doctype_label(nl[i]);
				
				me.rb_sel = new SelectWidget(d.widgets['Select'], nl.sort(), '200px');
				me.rb_sel.onchange = function() { me.rb_dialog.hide(); loadreport(me.rb_sel.inp.value, null, null, null, 1); };
			}
			me.rb_dialog.show();
		}
	}

	// Setup Search
	// ----------------------------------------------------------------------------------------

	this.setup_search = function() {

		me.menu.add_top_menu('Search', function() { me.search_dialog.show(); }, 'sprite-search' );

		// make the dialog
		// ----------------
		var d = new Dialog(240, 140, "Quick Search");
		d.make_body(
			[['HTML','Select']
			,['Button','Go', function() { me.open_quick_search(); }]]);
		d.onshow = function(){
			me.search_sel.inp.focus();	
		}
		me.search_dialog = d;
		
		// enter key
		keypress_observers.push({notify_keypress: function(ev, keycode) { 
			if(keycode==13 && me.search_dialog.display) me.open_quick_search();	
		}});
		
		
		// select
		me.search_sel = new SelectWidget(d.widgets['Select'], [], '120px');
		me.search_sel.inp.value = 'Select...';
	
		me.open_quick_search = function() {
			me.search_dialog.hide();
			var v = sel_val(me.search_sel);
			if(v) selector.set_search(v);
			me.search_sel.disabled = 1;
			selector.show();
		}

		// replace by labels
		var nl = profile.can_read.join(',').split(',');

		for(var i=0;i<nl.length;i++) nl[i]=get_doctype_label(nl[i]);
		
		me.search_sel.set_options(nl.sort());
		me.search_sel.onchange = function() { me.open_quick_search(); }
		
		// make the selector dialog
		makeselector();
	}
	
	// Setup User / Logout area
	// ----------------------------------------------------------------------------------------

	this.setup_logout = function() {
		
		var w = $a($td(this.body_tab, 0, 2),'div','',{paddingTop:'2px', textAlign:'right'});
		this.right_table_style = {fontSize:'11px',verticalAlign:'middle',height:'20px',paddingLeft:'4px',paddingRight:'4px'};
		var t = make_table(w, 1, 6, null, [], this.right_table_style);
		
		$y(t,{cssFloat:'right', color:'#FFF'});
		$td(t,0,0).innerHTML = user_fullname;
		$td(t,0,1).innerHTML = '<span style="cursor: pointer;font-weight: bold" onclick="get_help()">Help</span>';
		$td(t,0,2).innerHTML = '<span style="cursor: pointer;font-weight: bold" onclick="get_feedback()">Feedback</span>';
		$td(t,0,3).innerHTML = '<span style="cursor: pointer;" onclick="loaddoc(\'Profile\', user)">Profile</span>';
		$td(t,0,4).innerHTML = '<span style="cursor: pointer;" onclick="logout()">Logout</span>';
		this.menu_table_right = t;
		$y($td(t,0,5), {width:'18px'});
		this.spinner = $a($td(t,0,5),'img','',{display:'none'}); this.spinner.src = 'lib/images/ui/spinner.gif';
	}

	this.download_backup = function() {
		$c('webnotes.utils.backups.get_backup',{},function(r,rt) {});
	}
	
	this.setup();
}

var get_help = function() {
	msgprint('Help not implemented');
}

var get_feedback = function() {
	// dialog
	var d = new Dialog(640, 320, "Please give your feedback");
	d.make_body(
		[['Text','Feedback']
		,['Button','Send', function() { 
			$c_obj('Feedback Control', 'get_feedback', d.widgets['Feedback'].value, function(r,rt) { 
				d.hide(); if(r.message) msgprint(r.message); 
			})
		} ]]
	);
	d.show();
	
	// send to Feedback Control
}
