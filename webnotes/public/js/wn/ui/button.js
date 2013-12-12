// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

wn.ui.Button = function(args) {
	var me = this;
	$.extend(this, {
		make: function() {
			me.btn = wn.dom.add(args.parent, 'button', 'btn ' + (args.css_class || 'btn-default'));
			me.btn.args = args;

			// ajax loading
			me.loading_img = wn.dom.add(me.btn.args.parent,'img','',{margin:'0px 4px -2px 4px', display:'none'});
			me.loading_img.src= 'assets/webnotes/images/ui/button-load.gif';

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
			$(me.loading_img).css('display','inline');
		},
		
		done_working: function() {
			me.btn.disabled = false;
			$(me.loading_img).toggle(false);
		}
	});
	this.make();
}
