// Menu Bar

function MenuToolbar(parent) {
	this.ul = $a(parent, 'ul', 'menu_toolbar');
	this.cur_top_menu = null;
	this.max_rows = 10;
	this.dropdown_width = '280px';
	this.top_menus = {};

	this.top_menu_style = 'top_menu';
	this.top_menu_mo_style = 'top_menu_mo';
	this.top_menu_icon_style = 'top_menu_icon';
	
}
MenuToolbar.prototype.add_top_menu = function(label, onclick, add_icon) {
	var li = $a(this.ul, 'li');
	
	li.item = new MenuToolbarItem(this, li, label, onclick, add_icon);

	this.top_menus[label] = li.item.wrapper;
	return li.item.wrapper;
}

function MenuToolbarItem(tbar, parent, label, onclick, add_icon) {
	var me = this;
	this.wrapper = $a(parent, 'div', tbar.top_menu_style);
	
	// add icon
	if(add_icon) {
		var t = make_table(this.wrapper, 1, 2, null, ['22px', null], {verticalAlign:'middle'});
		$y(t,{borderCollapse:'collapse'});
		var icon = $a($td(t,0,0), 'div', 'wntoolbar-icon ' + add_icon);
		$td(t,0,1).innerHTML = label;
	} else {
		this.wrapper.innerHTML = label;	
	}
	
	this.wrapper.onclick = function() { onclick(); };
	this.def_class = tbar.top_menu_style;
	
	// mouseovers
	this.wrapper.onmouseover = function() { 
		this.set_selected();
		if(this.my_mouseover)this.my_mouseover(this);
	}
	this.wrapper.onmouseout = function() { 
		if(this.my_mouseout)
			this.my_mouseout(this);
		this.set_unselected();
	}
	
	// select / unselect
	this.wrapper.set_unselected = function() {
		if(me.wrapper.dropdown && me.wrapper.dropdown.is_active) {
			return;
		}
		me.wrapper.className = me.def_class;
	}
	this.wrapper.set_selected = function() { 
		if(me.cur_top_menu)
			me.cur_top_menu.set_unselected();
		me.wrapper.className = me.def_class + ' '+tbar.top_menu_mo_style;
		me.cur_top_menu = this;
	}
	
	
}
var closetimer;
function mclose(opt) { // close all active
	for(var i=0;i<all_dropdowns.length;i++) {
		if(all_dropdowns[i].is_active)
			if(opt && opt==all_dropdowns[i]) { /* don't hide caller */ }
			else all_dropdowns[i].hide();
	}
}
function mclosetime() { closetimer = window.setTimeout(mclose, 700); }
function mcancelclosetime() { if(closetimer) { window.clearTimeout(closetimer); closetimer = null; } }

MenuToolbar.prototype.make_dropdown = function(tm) {
	var me = this;
	tm.dropdown = new DropdownMenu(tm, this.dropdown_width);
	
	// triggers on top menu
	tm.my_mouseover = function() {
		this.dropdown.show();
	}
	tm.my_mouseout = function() {
		this.dropdown.clear();
	}
}

MenuToolbar.prototype.add_item = function(top_menu_label, label, onclick, on_top) {
	var me = this;
	var tm = this.top_menus[top_menu_label];
	if(!tm.dropdown) 
		this.make_dropdown(tm, this.dropdown_width);
	
	return tm.dropdown.add_item(label, onclick, on_top);
}

var all_dropdowns = []; var cur_dropdown;
function DropdownMenu(parent, width) {
	this.body = $a(parent, 'div', 'menu_toolbar_dropdown', {width:(width ? width : '140px'), display:'none'});
	this.parent = parent;
	this.items = {};
	this.item_style = 'dd_item';
	this.item_mo_style = 'dd_item_mo';
	this.list = [];
	this.max_height = 400;
	this.keypressdelta = 500;
		
	var me = this;
	
	this.body.onmouseout = function() { me.clear(); }
	this.body.onmouseover = function() { 
		mcancelclosetime(); 		
	} // re-entered
	this.clear_user_inp = function() { me.user_inp = '';}

	this.show = function() {
		// close others
		mclose(me);
		
		// clear menu timeout
		mcancelclosetime();
		
		hide_selects(); 

		me.is_active = 1;
		
		$ds(me.body); // show

		if(cint(me.body.clientHeight) >= me.max_height) {
			$y(me.body, {height:me.max_height + 'px'});
			me.scrollbars = 1;
		} else {
			$y(me.body, {height:null});
			me.scrollbars = 0;
		}		
		
	}

	this.hide = function() {
		$dh(me.body);

		//$dh(me.body); // hide
		if(!frozen)show_selects();
		
		// clear from active list
		me.is_active = 0;
		
		// events on label
		if(me.parent && me.parent.set_unselected) {
			me.parent.set_unselected();
		}
	}

	this.clear = function() {
		mcancelclosetime();
		mclosetime();
	}
	all_dropdowns.push(me);
}

DropdownMenu.prototype.add_item = function(label, onclick, on_top) {
	var me = this;
	
	if(on_top) {
		var mi = document.createElement('div');
		me.body.insertBefore(mi, me.body.firstChild);
		mi.className = this.item_style;
	} else {
		var mi = $a(this.body, 'div', this.item_style);
	}
	
	mi.innerHTML = label;
	mi.label = label;
	mi.my_onclick = onclick;
	mi.onclick = function() { mclose(); this.my_onclick(); };
	
	mi.highlight = function() {
		if(me.cur_mi) me.cur_mi.clear();
		this.className = me.item_style + ' ' + me.item_mo_style;
		me.cur_mi=this;
	}
	mi.clear = function() { 
		this.className = me.item_style; 
	}

	mi.onmouseover = mi.highlight;
	mi.onmouseout = mi.clear;
	
	mi.bring_to_top = function() { me.body.insertBefore(this, me.body.firstChild); }
	
	//var k=0, e=mi;
	//while (e = e.previousSibling) { ++k;}
	
	//mi.idx = k;
	return mi;
}
