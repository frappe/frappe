// link with ajax "working" indicator

wn.ele.Link = function(args) {
	var span = $a(args.parent, 'span', 'link_type', args.style);
	span.loading_img = $a(args.parent,'img','',{margin:'0px 4px -2px 4px', display:'none'});
	span.loading_img.src= 'images/ui/button-load.gif';

	span.innerHTML = args.label;
	span.user_onclick = args.onclick;
	span.onclick = function() { if(!this.disabled) this.user_onclick(this); }

	// working
	span.set_working = function() {
		this.disabled = 1;
		$di(this.loading_img);
	}
	span.done_working = function() {
		this.disabled = 0;
		$dh(this.loading_img);
	}

	this.span = span;

	return span;
}

// bc
function $ln(parent, label, onclick, style) { 
	return wn.ele.Link({parent:parent, label:label, onclick:onclick, style:style}).span;
}
