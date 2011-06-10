//

wn.widgets.notify = function(msg) {
	new wn.widgets.Notification(msg, 10);
}

wn.widgets.Notification = function(msg, expire_in) {
	var me = this;
	$.extend(this, {
		get_parent: function() {
			if(!wn.widgets.notify_area) {
				wn.widgets.notify_area = wn.add(document.getElementsByTagName('body')[0], 'div', 'notify_area');
			}
			return wn.widgets.notify_area;
		},
		
		make: function() {
			this.wrapper = wn.add(this.get_parent(), 'div', '', {position:'relative'});
			this.body = wn.add(this.wrapper, 'div', 'notice');
			this.make_close_btn();
			
			return this;
		},
		
		make_close_btn: function() {
			var c = wn.add(this.body, 'div', 'wn-icon ic-round_delete', {cssFloat:'right'});
			$(c).click(function() { wn.hide(this.wrapper) });
			c.wrapper = this.wrapper;
		},
		
		set_text: function(txt) {
			// text
			var t = $a(this.body, 'div', '', { color:'#440' });
			$(t).html(txt);
			$(this.wrapper).hide().fadeIn(1000);			
		},
		
		hide: function() {
			wn.hide(this.wrapper);
		}
	})
	this.make(msg).set_text(txt);
	setTimeout(this.hide, expire_in*1000);
}