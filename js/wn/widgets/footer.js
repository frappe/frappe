// a simple footer

// args - parent, columns, items
// items as [{column:1, label:'x', description:'y', onclick:function}]
wn.widgets.Footer = function(args) {
	$.extend(this, args);
	this.make = function() {
		this.wrapper = $a(this.parent, 'div', 'std-footer');
		this.table = make_table(this.wrapper, 1, this.columns, [], {width:100/this.columns + '%'});
		this.render_items();
	}
	this.render_items = function() {
		for(var i=0; i<this.items.length; i++) {
			var item = this.items[i];
			
			var div = $a($td(this.table,0,item.column), 'div', 'std-footer-item');
			div.label = $a($a(div,'div'),'span','link_type','',item.label);
			div.label.onclick = item.onclick;
			if(item.description) {
				div.description = $a(div,'div','field_description','',item.description);
			}
		}
	}
	if(this.items)
		this.make();
}