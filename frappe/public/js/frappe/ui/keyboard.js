frappe.provide('frappe.ui.keys.handlers');

frappe.ui.keys.setup = function() {
	$(window).on('keydown', function(e) {
		var key = e.key;
		if(key.substr(0, 5)==='Arrow') {
			// ArrowDown -> down
			key = key.substr(5).toLowerCase();
		}
		if(e.ctrlKey || e.metaKey) {
			// add ctrl+ the key
			key = 'ctrl+' + key;
		}
		if(e.shiftKey) {
			// add ctrl+ the key
			key = 'shift+' + key;
		}
		if(frappe.ui.keys.handlers[key]) {
			var out = null;
			for(var i=0, l = frappe.ui.keys.handlers[key].length; i<l; i++) {
				var handler = frappe.ui.keys.handlers[key][i];
				var _out = handler.apply(this, [e]);

				if(_out===false) {
					out = _out;
				}
			}
			return out;
		}
	});
}

frappe.ui.keys.on = function(key, handler) {
	if(!frappe.ui.keys.handlers[key]) {
		frappe.ui.keys.handlers[key] = [];
	}
	frappe.ui.keys.handlers[key].push(handler);
}

frappe.ui.keys.on('ctrl+s', function(e) {
	frappe.app.trigger_primary_action();
	e.preventDefault();
	return false;
});

frappe.ui.keys.on('ctrl+g', function(e) {
	$("#navbar-search").focus();
	e.preventDefault();
	return false;
});

frappe.ui.keys.on('ctrl+b', function(e) {
	var route = frappe.get_route();
	if(route[0]==='Form' || route[0]==='List') {
		frappe.new_doc(route[1], true);
		e.preventDefault();
		return false;
	}
});

frappe.ui.keys.on('Escape', function(e) {
	// close open grid row
	var open_row = $(".grid-row-open");
	if(open_row.length) {
		var grid_row = open_row.data("grid_row");
		grid_row.toggle_view(false);
		return false;
	}

	// close open dialog
	if(cur_dialog && !cur_dialog.no_cancel_flag) {
		cur_dialog.cancel();
		return false;
	}
});


frappe.ui.keys.on('Enter', function(e) {
	if(cur_dialog && cur_dialog.confirm_dialog) {
		cur_dialog.get_primary_btn().trigger('click');
	}
});

frappe.ui.keys.on('ctrl+down', function(e) {
	var grid_row = frappe.ui.form.get_open_grid_form();
	grid_row && grid_row.toggle_view(false, function() { grid_row.open_next() });
});

frappe.ui.keys.on('ctrl+up', function(e) {
	var grid_row = frappe.ui.form.get_open_grid_form();
	grid_row && grid_row.toggle_view(false, function() { grid_row.open_prev() });
});

frappe.ui.keys.on('shift+ctrl+r', function(e) {
	frappe.ui.toolbar.clear_cache();
});
