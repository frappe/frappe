wn.ui.Button = function(args) {
	wn.require('lib/css/ui/buttons.css')
	var me = this;
	$.extend(this, {
		make: function() {
			me.btn = wn.dom.add(args.parent, 'button', args.class || 'clean-gray');

			// ajax loading
			me.loading_img = wn.dom.add(args.parent,'img','',{margin:'0px 4px -2px 4px', display:'none'});
			me.loading_img.src= 'lib/images/ui/button-load.gif';
			if(args.is_ajax) wn.dom.css(me.btn,{marginRight:'24px'});

			// label
			me.btn.innerHTML = args.label;

			// onclick
			me.btn.user_onclick = args.onclick; 
			$(me.btn).bind('click', function() { 
				if(!this.disabled) this.user_onclick(this); 
			})
			
			// style
			if(args.style) 
				wn.dom.css(me.btn, args.style);
		},

		set_working: function() {
			me.btn.disabled = 'disabled';
			wn.dom.show(this.loading_img, 'inline');
			if(args.is_ajax) 
				wn.dom.css(me.btn,{marginRight:'0px'});
		},
		
		done_working: function() {
			me.btn.disabled = false;
			wn.dom.hide(this.loading_img);
			if(args.is_ajax) 
				wn.dom.css(me.btn,{marginRight:'24px'});
		}
	});
	this.make();
}
