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