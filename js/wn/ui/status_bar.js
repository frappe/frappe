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


wn.ui.StatusBar = function() {
	var me = this;
	$.extend(this, {
		render: function() {
			wn.require('lib/js/wn/ui/overlay.js');
			wn.require('lib/css/ui/status_bar.css');

			me.dialog = wn.dom.add(null, 'div', 'dialog round shadow');
			me.outer = wn.dom.add(me.dialog, 'div', 'status_bar_outer');
			me.inner = wn.dom.add(me.outer, 'div', 'status_bar_inner');
			me.overlay = new wn.ui.Overlay(me.dialog);
		},
		set_value: function(percent) {
			me.inner.style.width = percent + '%';
		},
		hide: function() {
			me.overlay.hide();
		}
	});
	me.render();
}