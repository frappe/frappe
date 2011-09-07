// overlay an element
// http://blog.learnboost.com/blog/a-css3-overlay-system/

wn.ui.Overlay = function(ele) {
	wn.require('lib/css/ui/overlay.css');

	var me = this;
	$.extend(this, {
		render: function() {
			me.wrap = wn.dom.add(
				wn.dom.add(
					wn.dom.add($('body').get(0), 'div', 'overlay')
				, 'div', 'wrap-outer')
			, 'div', 'wrap');
			me.wrap.appendChild(ele);
			$('body').addClass('overlaid');
		},
		hide: function() {
			wn.dom.hide(me.wrap);
			$('body').removeClass('overlaid');
		}
	});
	me.render();	
}