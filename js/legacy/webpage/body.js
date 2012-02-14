/** Page Body

	+ body
		+ body
			+ left_sidebar
			+ center
			+ right_sidebar
	+ dead session

**/

function Body() { 
	this.left_sidebar = null;
	this.right_sidebar = null;
	this.status_area = null;
	var me = this;
	page_body = this;	

	this.no_of_columns = function() {
		var n = 2;
		if(cint(me && me.cp && me.cp.right_sidebar_width)) 
			n = n + 1;
		return n;
	}
	
	this.ready = function() {
		$dh('startup_div');
		$ds('body_div');	
	}
	
	this.setup_page_areas = function() {		
		var n = this.no_of_columns();

		// has sidebars, make a table
		this.body_table = make_table(this.body, 1, n, '100%');
		$y(this.body_table, {tableLayout:'fixed'});
		var c = 0;
				
		// left sidebar
		this.left_sidebar = $td(this.body_table, 0, c);
		$y(this.left_sidebar, {width:cint(this.cp.left_sidebar_width) + 'px'});
		c++;
			
		// center
		this.center = $a($td(this.body_table, 0, c), 'div');
		c++;
			
		// right side bar
		if(cint(this.cp.right_sidebar_width)) {
			this.right_sidebar = $td(this.body_table, 0, c);
			$y(this.right_sidebar, {width:cint(this.cp.right_sidebar_width) + 'px'})
			c++;			
		}
		
		this.center.header = $a(this.center, 'div');
		this.center.body = $a(this.center, 'div');
		this.center.loading = $a(this.center, 'div', '', {margin:'200px 0px', fontSize:'14px', color:'#999', textAlign:'center'});
		this.center.loading.innerHTML = 'Loading...'
				
	}

	this.setup_sidebar_menu = function() {
		if(this.left_sidebar && this.cp.show_sidebar_menu){
			sidebar_menu = new SidebarMenu();
			sidebar_menu.make_menu('');
		}
	}
	
	this.run_startup_code = function() {
		$(document).trigger('startup');
		// startup code
		try{
			if(this.cp.custom_startup_code)
				eval(this.cp.custom_startup_code);
		} catch(e) {
			errprint(e);
		}
	}
	
	this.setup = function() {
		this.cp = wn.control_panel;
		
		this.wrapper = $a($i('body_div'),'div');
		this.body = $a(this.wrapper, 'div');
		
		// sidebars
		if(user_defaults.hide_sidebars) {
			this.cp.left_sidebar_width = null;
			this.cp.right_sidebar_width = null;
		}		

		this.setup_page_areas();

		// core areas;
		if(user=='Guest') user_defaults.hide_webnotes_toolbar = 1;
		if(!cint(user_defaults.hide_webnotes_toolbar) || user=='Administrator') {
			this.wntoolbar = new wn.ui.toolbar.Toolbar();
		}
		
		// page width
		if(this.cp.page_width) $y(this.wrapper,{width:cint(this.cp.page_width) + 'px'});
		
	}
	
	// Standard containers
	// - Forms
	// - Report Builder
	// - Item List
	// - [Pages by their names]

	this.pages = {};
	this.cur_page = null;
	this.add_page = function(label, onshow, onhide) {
		var c = $a(this.center.body, 'div');
		if(onshow)
			c.onshow = onshow;
		if(onhide)
			c.onhide = onhide;
		this.pages[label] = c;
		$dh(c);
		return c;
	}
	
	this.change_to = function(label) {
		// hide existing
		$dh(this.center.loading);
		if(me.cur_page &&  me.pages[label]!=me.cur_page) {
			if(me.cur_page.onhide)
				me.cur_page.onhide();
			$dh(me.cur_page);
		}
		// show
		me.cur_page = me.pages[label];
		me.cur_page_label = label;
		$(me.cur_page).fadeIn();
	
		// on show
		if(me.cur_page.onshow)
			me.cur_page.onshow(me.cur_page);
	}

	this.set_status = function(txt) {
		if(this.status_area)
			this.status_area.innerHTML = txt;
	}
	
	this.set_session_changed = function() {
		if(this.session_message_set) return;
		var div = $a($i('body_div').parentNode,'div','',{textAlign: 'center', fontSize:'14px', margin:'150px auto'});
		$dh('body_div');
		div.innerHTML = 'This session has been changed. Please <span class="link_type" onclick="window.location.reload()">refresh</span> to continue';
		this.session_message_set = 1;
	}
	
	this.setup();
}