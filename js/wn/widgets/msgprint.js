// standard dialog boxes like
// msgprint, input, confirm

wn.widgets.msgprint = function(msg) {
	if(!msg) return;
	if(typeof(msg)!='string') msg = JSON.stringify(msg);
	
	// small message
	if(msg.substr(0,8)=='__small:') {
		wn.widgets.notify(msg.substr(8));
		return;
	}
	
	var make = function() {
		if(wn.widgets.msgprint_dialog) 
			return wn.widgets.msgprint_dialog;
			
		var d = wn.widgets.Dialog({
			title: 'Message',
			width: '500px',
		});
		$.extend(d, {
			message_area: $a(d.body, 'div', '', {padding:'13px', fontSize:'13px'}),
			
			set_message: function(msg) {
				if(d.message_area.innerHTML) 
					d.add_sep();
				$a(d.message_area, 'div', '', {}, msg);
				d.show();
			},
			
			add_sep: function() {
				$a(d.message_area, 'div', '', {margin:'7x 0px', borderTop:'1px dashed #AAA'});
			},
			
			on_hide: function() {
				d.message_area.innerHTML = '';
			}
		})
		
		
		wn.widgets.msgprint_dialog = d;
		return d;
	}
	
	make().set_message(msg);
}

// bc
msgprint = wn.widgets.msgprint