wn.ui.Button = function(args) {
	var me = this;
	$.extend(this, {
		make: function() {
			me.btn = wn.dom.add(args.parent, 'button', 'btn small ' + (args.css_class || ''));

			// ajax loading
			me.loading_img = wn.dom.add(args.parent,'img','',{margin:'0px 4px -2px 4px', display:'none'});
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
			if(args.style) 
				wn.dom.css(me.btn, args.style);
		},

		set_working: function() {
			me.btn.disabled = 'disabled';
			wn.dom.show(me.loading_img, 'inline');
			if(args.is_ajax) 
				wn.dom.css(me.btn,{marginRight:'0px'});
		},
		
		done_working: function() {
			me.btn.disabled = false;
			wn.dom.hide(me.loading_img);
			if(args.is_ajax) 
				wn.dom.css(me.btn,{marginRight:'24px'});
		}
	});
	this.make();
}
