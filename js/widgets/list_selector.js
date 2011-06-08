ListSelector = function(title, intro, list, onupdate, selectable) {
	var me = this; this.list = list; this.selectable = selectable;
	
	this.dialog = new Dialog(400,600,title);
	this.items = [];
	
	// intro
	if(intro) {
		intro_area = $a(this.dialog.body, 'div', 'help_box', {margin:'16px', marginBottom:'0px', width:'312px'});
		intro_area.innerHTML = intro;
	}
	
	// body	
	this.body = $a(this.dialog.body, 'div', '', {margin:'16px', position: 'relative'});
	
	// items
	this.render();
	
	// ---------------------------------------
	
	// update button
	var btn = $btn(this.dialog.body, 'Update', function() { me.update() }, {margin:'0px 0px 16px 16px'}, 'green', 1);
	this.update = function() {
		if(me.selected_item) $bg(me.selected_item, '#FFF');
		var ret = [];
		for(var i=0; i<me.items.length; i++) {
			// [label, idx, selected, det]
			ret.push([me.items[i].label, me.items[i].idx, (me.items[i].check ? (me.items[i].check.checked ? 1 : 0) : 0), me.items[i].det]);
		}
		
		me.dialog.hide();
		
		// call the user with (done!)
		onupdate(ret);
	}
	
	this.dialog.show();
}

// ---------------------------------------

ListSelector.prototype.render = function(to_hide) {
	this.body.innerHTML = ''; this.items = [];
	
	// sort
	this.list.sort(function(a,b) { return a[1] > b[1]; });
	
	// items
	for(i=0; i<this.list.length; i++) {
		// make checkbox for if selectable
		this.list[i][1]=i;
		this.items.push(new ListSelectorItem(this, this.list[i], i));
		if(i==to_hide) $dh(this.items[i].body);
	}
}

// ---------------------------------------

ListSelector.prototype.insert_at = function(item, new_idx) {
	for(var i=0;i<this.list.length; i++) {
		if(this.list[i][1] >= new_idx) this.list[i][1]++;
	}
	for(var i=0;i<this.list.length; i++) {
		if(this.list[i][1] >= item.idx) this.list[i][1]--;
	}
	this.list[item.idx][1] = new_idx;

	var n = new_idx - ((new_idx > item.idx) ? 1 : 0);
	this.render(n);
	this.items[n].body.onmousedown();
	$(this.items[n].body).slideDown();
}

// =====================================

ListSelectorItem = function(ls, det, idx) {
	this.det = det; this.ls = ls; this.idx = idx;
	
	this.body = $a(ls.body, 'div', '', {padding: '8px', margin:'4px 0px', 
		border:'1px solid #AAA', position: 'relative', width:'320px', height:'14px', cursor:'move'});

	if(ls.selectable) {
		// with checkbox
		this.make_with_checkbox();
	} else {
		// no checkbox (only label)
		this.body.innerHTML = det[0];
	}
	this.set_drag();
}

// ---------------------------------------

ListSelectorItem.prototype.make_with_checkbox = function() {
	this.body.tab = make_table(this.body, 1, 2, null, ['28px',null], {verticalAlign:'top'});
	this.check = $a_input($td(this.body.tab, 0, 0), 'checkbox');
	if(this.det[2]) this.check.checked = 1;
	$td(this.body.tab, 0, 1).innerHTML = this.det[0];
}

// ---------------------------------------

ListSelectorItem.prototype.set_drag = function() {
	var me = this;
	this.body.item = this;	
	
	// color on mousedown
	this.body.onmousedown = function() { 
		$bg(this, '#FFC'); 
		if(me.ls.selected_item && me.ls.selected_item != this) $bg(me.ls.selected_item, '#FFF'); 
		me.ls.selected_item = this;
	}

	// setup draggable
	$(this.body).draggable({ 
		opacity: 0.6, 
		helper: 'clone',
		containment: 'parent', 
		scroll: false,
		cursor: 'move',
		drag:function(event, ui){
			me.ls.drag_item = this.item;
		}
	});
	
	$(this.body).droppable({
		drop: function(event, ui) {
			me.ls.insert_at(me.ls.drag_item, me.idx + (me.ls.drag_item.idx < me.idx ? 1 : 0));
		}
	});
}