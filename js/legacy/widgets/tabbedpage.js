// Tabbed Page

function TabbedPage(parent, only_labels) { 
	this.tabs = {};
	this.items = this.tabs // bc
	this.cur_tab = null;

	this.label_wrapper = $a(parent, 'div','box_label_wrapper', {marginTop:'16px'}); // for border
	this.label_body = $a(this.label_wrapper, 'div', 'box_label_body'); // for height
	this.label_area = $a(this.label_body, 'ul', 'box_tabs');
	if(!only_labels)this.body_area = $a(parent, 'div', '', {backgroundColor:'#FFF'});
	else this.body_area = null;

	this.add_item = function(label, onclick, no_body, with_heading) {
		this.add_tab(label, onclick, no_body, with_heading);
		return this.items[label];
	}
}

TabbedPage.prototype.add_tab = function(n, onshow, no_body, with_heading) { 

	var tab = $a(this.label_area, 'li');
	tab.label = $a(tab,'a');
	tab.label.innerHTML = n;
	
	if(this.body_area && !no_body){
		tab.tab_body = $a(this.body_area, 'div');
		$dh(tab.tab_body);
		tab.body = tab.tab_body; // bc
	} else { 
		tab.tab_body = null; 
	}
	tab.onshow = onshow;
	var me = this;

	tab.collapse = function() { 
		if(this.tab_body)$dh(this.tab_body); this.className = '';
		if(hide_autosuggest)
			hide_autosuggest();
	}
	tab.set_selected = function() { 
		if(me.cur_tab) me.cur_tab.collapse();
		this.className = 'box_tab_selected';
		$op(this, 100); 
		me.cur_tab = this;
	}
	tab.expand = function(arg) { 
		this.set_selected(); 
		if(this.tab_body) $ds(this.tab_body);
		if(this.onshow)this.onshow(arg); 
	}
	tab.onmouseover = function() { 
		if(me.cur_tab!=this) this.className = 'box_tab_mouseover';
	}
	tab.onmouseout = function() {
		if(me.cur_tab!=this) this.className = ''
	}
	tab.hide = function() {
		this.collapse();
		$dh(this);
	}
	tab.show = function() {
		$ds(this);
	}
	tab.onclick = function() { this.expand(); }
	this.tabs[n] = tab;
	return tab;
}




// =================================================================================

function TrayPage(parent, height, width, width_body) {
	var me = this;
	if(!width) width=(100/8)+'%';

	this.body_style = {margin: '4px 8px'}
	
	this.cur_item = null;
	
	this.items = {};
	this.tabs = this.items // for tabs
	this.tab = make_table($a(parent, 'div'), 1, 2, '100%', [width, width_body]);
	
	// tray style
	$y($td(this.tab, 0, 0),{
		backgroundColor: this.tray_bg
		//,borderRight:'1px solid ' + this.tray_fg
		,width: width
	});

	// body style
	this.body = $a($td(this.tab, 0, 1), 'div');
	if(height) {
		$y(this.body, {height: height, overflow: 'auto'});
	}
	
	this.add_item = function(label, onclick, no_body, with_heading) {
		this.items[label] = new TrayItem(me, label, onclick, no_body, with_heading);
		return this.items[label];
	}
}

function TrayItem(tray, label, onclick, no_body, with_heading) {
	this.label = label;
	this.onclick = onclick;
	var me = this;
	
	this.ldiv = $a($td(tray.tab, 0, 0), 'div');
	$item_normal(this.ldiv);
	
	if(!no_body) {
		this.wrapper = $a(tray.body, 'div', '', tray.body_style);
		if(with_heading) {
			this.header = $a(this.wrapper, 'div', 'sectionHeading', {marginBottom:'16px', paddingBottom:'0px'});
			this.header.innerHTML = label;
		}
		this.body = $a(this.wrapper, 'div');
		this.tab_body = this.body; // for sync with tabs
		
		$dh(this.wrapper);
	}

	$(this.ldiv).html(label)
		.hover(
			function() { if(tray.cur_item.label != this.label) $item_active(this); },
			function() { if(tray.cur_item.label != this.label) $item_normal(this); }
		)
		.click(
			function() { me.expand(); }
		)

	this.ldiv.label = label;
	this.ldiv.setAttribute('title',label);
	this.ldiv.onmousedown = function() { $item_pressed(this); }
	this.ldiv.onmouseup = function() { $item_selected(this); }

	this.expand = function() {
		if(tray.cur_item) tray.cur_item.collapse();
		if(me.wrapper) $ds(me.wrapper);
		if(me.onclick) me.onclick(me.label);
		me.show_as_expanded();
	}
	
	this.show_as_expanded = function() {
		$item_selected(me.ldiv);
		tray.cur_item = me;
	}
	
	this.collapse = function() {
		if(me.wrapper)$dh(me.wrapper);
		$item_normal(me.ldiv);
	}
	this.hide = function() {
		me.collapse();
		$dh(me.ldiv);
	}
	this.show = function() {
		$ds(me.ldiv);
	}	
}