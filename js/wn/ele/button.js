wn.ele.Button = function(args) {
	var btn = $a(args.parent, 'button');
	btn.loading_img = $a(args.parent,'img','',{margin:'0px 4px -2px 4px', display:'none'});
	btn.loading_img.src= 'images/ui/button-load.gif';
	$wid_make(btn,color);
	if(args.is_ajax) wn.style(btn,{marginRight:'24px'});

	// click
	btn.innerHTML = args.label;
	btn.user_onclick = args.onclick; 
	btn.color = args.color;
	btn.onclick = function() { if(!this.disabled) this.user_onclick(this); }

	// color
	$(btn).hover(
		function() { $wid_active(this); },
		function() { $wid_normal(this); }
	)
	btn.onmousedown = function() { $wid_pressed(this); }
	btn.onmouseup = function() { $wid_active(this); }

	// disabled
	btn.set_disabled = function() {
		$wid_disabled(this);
	}
	btn.set_enabled = function() {
		this.disabled = 0;
		$wid_normal(this);
	}

	// working
	btn.set_working = function() {
		this.set_disabled();
		$di(this.loading_img);
		if(args.is_ajax) wn.style(btn,{marginRight:'0px'});
	}
	btn.done_working = function() {
		this.set_enabled();
		wn.hide(this.loading_img);
		if(args.is_ajax) wn.style(btn,{marginRight:'24px'});
	}

	if(args.style) wn.style(btn, args.style);
	this.button = btn;
	return btn;
}

function $btn(parent, label, onclick, style, color, is_ajax) {
	return wn.ele.Button({parent:parent, label:label, onclick:onclick, style:style, is_ajax: is_ajax}).button;
}
