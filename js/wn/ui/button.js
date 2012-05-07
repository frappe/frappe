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

wn.ui.Button = function(args) {
	var me = this;
	$.extend(this, {
		make: function() {
			me.btn = wn.dom.add(args.parent, 'button', 'btn btn-small ' + (args.css_class || ''));
			me.btn.args = args;

			// ajax loading
			me.loading_img = wn.dom.add(me.btn.args.parent,'img','',{margin:'0px 4px -2px 4px', display:'none'});
			me.loading_img.src= 'images/lib/ui/button-load.gif';
			if(args.is_ajax) wn.dom.css(me.btn,{marginRight:'24px'});

			// label
			me.btn.innerHTML = args.label;

			// onclick
			me.btn.user_onclick = args.onclick; 
			$(me.btn).bind('click', function() { 
				if(!this.disabled && this.user_onclick) 
					this.user_onclick(this); 
			})
			
			// bc
			me.btn.set_working = me.set_working;
			me.btn.done_working = me.done_working;
			
			// style
			if(me.btn.args.style) 
				wn.dom.css(me.btn, args.style);
		},

		set_working: function() {
			me.btn.disabled = 'disabled';
			if(me.btn.args.is_ajax) {
				$(me.btn).css('margin-right', '0px');
			}
			$(me.loading_img).css('display','inline');
		},
		
		done_working: function() {
			me.btn.disabled = false;
			if(me.btn.args.is_ajax) {
				$(me.btn).css('margin-right', '24px');				
			}
			$(me.loading_img).toggle(false);
		}
	});
	this.make();
}
