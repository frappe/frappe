/* 

standard dialog class
	options:
		title
		width
		fields (docfields)
*/	

wn.widgets.Dialog = function(opts) {
	
	$.extend(this, opts)
	this.display = false;
	
	this.make = function(opts) {
		if(opts) $.extend(this, opts);
		
		this.wrapper = $a(popup_cont, 'div', 'dialog_wrapper');

		if(this.width)
			$w(this.wrapper, this.width + 'px');

		this.make_head();
		this.body = $a(this.wrapper, 'div', 'dialog_body');	
		if(this.fields)
			this.make_fields(this.body, this.fields);
	}
	
	this.make_head = function() {
		var me = this;
		this.head = $a(this.wrapper, 'div', 'dialog_head');

		var t = make_table(this.head,1,2,'100%',['100%','16px'],{padding:'2px'});

		$y($td(t,0,0),{paddingLeft:'16px',fontWeight:'bold',fontSize:'14px',textAlign:'center'});
		$y($td(t,0,1),{textAlign:'right'});	

		var img = $a($td(t,0,01),'img','',{cursor:'pointer'});
		img.src='images/icons/close.gif';

		this.title_text = $td(t,0,0);
		this.set_title(this.title);

		img.onclick = function() { if(me.oncancel)me.oncancel(); me.hide(); }
		this.cancel_img = img;		
	}
	
	this.set_title = function(t) {
		this.title_text.innerHTML = t ? t : '';
	}
	
	this.set_postion = function() {
		// place it at the center
		var d = get_screen_dims();

		this.wrapper.style.left  = ((d.w - cint(this.wrapper.style.width))/2) + 'px';
        this.wrapper.style.top = (get_scroll_top() + 60) + 'px';

		// place it on top
		top_index++;
		$y(this.wrapper,{zIndex:top_index});		
	}
	
	/** show the dialog */
	this.show = function() {
		// already live, do nothing
		if(this.display) return;

		// set position
		this.set_postion()

		// show it
		$ds(this.wrapper);

		// hide background
		freeze();

		this.display = true;
		cur_dialog = this;

		// call onshow
		if(this.onshow)this.onshow();
	}

	this.hide = function() {
		// call onhide
		if(this.onhide) this.onhide();

		// hide
		unfreeze();
		$dh(this.wrapper);

		// clear open autosuggests
		if(cur_autosug) cur_autosug.clearSuggestions();

		// flags
		this.display = false;
		cur_dialog = null;
	}
		
	this.no_cancel = function() {
		$dh(this.cancel_img);
	}

	if(opts) this.make();

}

wn.widgets.Dialog.prototype = new wn.widgets.FieldGroup();

// Close dialog on Escape
keypress_observers.push(new function() {
	this.notify_keypress = function(e, kc) {
		if(cur_dialog && kc==27 && !cur_dialog.no_cancel_flag) 
			cur_dialog.hide();
	}
});