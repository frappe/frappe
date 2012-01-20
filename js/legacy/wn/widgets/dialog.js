// opts { width, height, title, fields (like docfields) }

wn.widgets.FieldGroup = function() {
	
	this.make_fields = function(body, fl) {
		wn.require('lib/js/legacy/widgets/form/fields.js');
		$y(this.body, {padding:'11px'});
		this.fields_dict = {}; // reset
		for(var i=0; i<fl.length; i++) {
			var df = fl[i];
			var div = $a(body, 'div', '', {margin:'6px 0px'})
			f = make_field(df, null, div, null);
			f.not_in_form = 1;
			this.fields_dict[df.fieldname] = f
			f.refresh();
		}
	}
	
	/* get values */
	this.get_values = function() {
		var ret = {};
		var errors = [];
		for(var key in this.fields_dict) {
			var f = this.fields_dict[key];
			var v = f.get_value ? f.get_value() : null;

			if(f.df.reqd && !v) 
				errors.push(f.df.label + ' is mandatory');

			if(v) ret[f.df.fieldname] = v;
		}
		if(errors.length) {
			msgprint('<b>Please check the following Errors</b>\n' + errors.join('\n'));
			return null;
		}
		return ret;
	}
	
	/* set field value */
	this.set_value = function(key, val){
		var f = this.fields_dict[key];
		if(f) {
			f.set_input(val);
			f.refresh_mandatory();
		}		
	}

	/* set values from a dict */
	this.set_values = function(dict) {	
		for(var key in dict) {
			if(this.fields_dict[key]) {
				this.set_value(key, dict[key]);
			}
		}
	}
}

wn.widgets.Dialog = function(opts) {
	
	this.opts = opts;
	this.display = false;
	
	this.make = function(opts) {
		if(opts) 
			this.opts = opts;
		if(!this.opts.width) this.opts.width = 480;
		
		this.wrapper = $a(popup_cont, 'div', 'dialog_wrapper');

		if(this.opts.width)
			this.wrapper.style.width = this.opts.width + 'px';

		this.make_head();
		this.body = $a(this.wrapper, 'div', 'dialog_body');	
		if(this.opts.fields)
			this.make_fields(this.body, this.opts.fields);
	}
	
	this.make_head = function() {
		var me = this;
		this.head = $a(this.wrapper, 'div', 'dialog_head');

		var t = make_table(this.head,1,2,'100%',['100%','16px'],{padding:'2px'});

		$y($td(t,0,0),{paddingLeft:'16px',fontWeight:'bold',fontSize:'14px',textAlign:'center'});
		$y($td(t,0,1),{textAlign:'right'});	

		var img = $a($td(t,0,01),'img','',{cursor:'pointer'});
		img.src='lib/images/icons/close.gif';

		this.title_text = $td(t,0,0);
		this.set_title(this.opts.title);

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