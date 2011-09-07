// convert to superfish menu

provide('wn.menus.superfish');
wn.menus.superfish = function(parent, data) {
	var _make_list = function(myparent, lst) {
		var ul = wn.dom.add(myparent, 'ul');
		$.each(lst, function(i,v) {
			var li = wn.dom.add(ul, 'li')
			var a = wn.dom.add(li, 'a', '', '', v.label);
			a.action = v.action
			
			// action
			if(v.action) {
				a.onclick = function() { window[action](); };
			} 
			
			// link
			if(v.href) {
				a.href = v.href;
			}
			
			// sub menu
			if(v.subitems) {
				_make_list(li, v.subitems);
			}			
		})
		return ul;
	}
	ul = _make_list(parent, data);
	ul.className = 'sf-menu';
	
	// build it
	$(ul).superfish();
}