
wn.ui.StatusBar = function() {
	var me = this;
	$.extend(this, {
		render: function() {
			wn.require('lib/js/wn/ui/overlay.js');
			wn.require('lib/css/ui/status_bar.css');

			me.dialog = wn.dom.add(null, 'div', 'dialog round shadow');
			me.outer = wn.dom.add(me.dialog, 'div', 'status_bar_outer');
			me.inner = wn.dom.add(me.outer, 'div', 'status_bar_inner');
			me.overlay = new wn.ui.Overlay(me.dialog);
		},
		set_value: function(percent) {
			me.inner.style.width = percent + '%';
		},
		hide: function() {
			me.overlay.hide();
		}
	});
	me.render();
}