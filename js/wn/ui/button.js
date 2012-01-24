wn.ui.Button = function(args) {
	var me = this;
	$.extend(this, {
		make: function() {
			me.btn = wn.dom.add(args.parent, 'button', 'btn small ' + (args.css_class || ''));
			me.btn.args = args;

			// ajax loading
			me.loading_img = wn.dom.add(me.btn.args.parent,'img','',{margin:'0px 4px -2px 4px', display:'none'});
			me.loading_img.src= 'lib/images/ui/button-load.gif';
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
			wn.dom.show(me.loading_img, 'inline');
		},
		
		done_working: function() {
			me.btn.disabled = false;
			if(me.btn.args.is_ajax) {
				$(me.btn).css('margin-right', '24px');				
			}
			wn.dom.hide(me.loading_img);
		}
	});
	this.make();
}
