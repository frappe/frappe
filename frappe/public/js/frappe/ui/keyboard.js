import './alt_keyboard_shortcuts';

frappe.provide('frappe.ui.keys.handlers');

frappe.ui.keys.setup = function() {
	$(window).on('keydown', function(e) {
		var key = frappe.ui.keys.get_key(e);
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

let standard_shortcuts = [];
frappe.ui.keys.standard_shortcuts = standard_shortcuts;
frappe.ui.keys.add_shortcut = (shortcut, action, description, page) => {
	if (action instanceof jQuery) {
		let $target = action;
		action = () => {
			$target[0].click();
		}
	}
	frappe.ui.keys.on(shortcut, (e) => {
		if (!page || page.wrapper.is(':visible')) {
			e.preventDefault();
			action(e);
		}
	});
	let existing_shortcut_index = standard_shortcuts.findIndex(
		s => s.shortcut === shortcut
	);
	let new_shortcut = { shortcut, action, description, page };
	if (existing_shortcut_index === -1) {
		standard_shortcuts.push(new_shortcut);
	} else {
		standard_shortcuts[existing_shortcut_index] = new_shortcut;
	}
}

frappe.ui.keys.show_keyboard_shortcut_dialog = () => {
	let global_shortcuts = standard_shortcuts.filter(shortcut => !shortcut.page);
	let current_page_shortcuts = standard_shortcuts.filter(
		shortcut => shortcut.page && shortcut.page === window.cur_page.page.page);

	function generate_shortcuts_html(shortcuts, heading) {
		if (!shortcuts.length) {
			return '';
		}
		let html = shortcuts.map(shortcut => {
			let shortcut_label = shortcut.shortcut
				.split('+')
				.map(frappe.utils.to_title_case)
				.join('+');
			if (frappe.utils.is_mac()) {
				shortcut_label = shortcut_label.replace('Ctrl', '⌘');
			}
			return `<tr>
				<td width="40%"><kbd>${shortcut_label}</kbd></td>
				<td width="60%">${shortcut.description || ''}</td>
			</tr>`;
		}).join('');
		html = `<h5 style="margin: 0;">${heading}</h5>
			<table style="margin-top: 10px;" class="table table-bordered">
				${html}
			</table>`;
		return html;
	}

	let global_shortcuts_html = generate_shortcuts_html(global_shortcuts, __('Global Shortcuts'));
	let current_page_shortcuts_html = generate_shortcuts_html(current_page_shortcuts, __('Page Shortcuts'));

	let dialog = new frappe.ui.Dialog({
		title: __('Keyboard Shortcuts'),
	});

	dialog.$body.append(global_shortcuts_html);
	dialog.$body.append(current_page_shortcuts_html);
	dialog.$body.append(`
		<div class="text-muted">
			${__('Press Alt Key to trigger additional shortcuts in Menu and Sidebar')}
		</div>
	`);

	dialog.show();
}

frappe.ui.keys.get_key = function(e) {
	var keycode = e.keyCode || e.which;
	var key = frappe.ui.keys.key_map[keycode] || String.fromCharCode(keycode);

	if(e.ctrlKey || e.metaKey) {
		// add ctrl+ the key
		key = 'ctrl+' + key;
	}
	if(e.shiftKey) {
		// add ctrl+ the key
		key = 'shift+' + key;
	}
	if (e.altKey) {
		// add alt+ the key
		key = 'alt+' + key;
	}
	if (e.altKey && e.ctrlKey) {
		// add alt+ctrl+ the key or single key e.g f1,f2,etc..
		return key.toLowerCase();
	}
	return key.toLowerCase();
}

frappe.ui.keys.on = function(key, handler) {
	if(!frappe.ui.keys.handlers[key]) {
		frappe.ui.keys.handlers[key] = [];
	}
	frappe.ui.keys.handlers[key].push(handler);
}

frappe.ui.keys.add_shortcut('ctrl+s', function(e) {
	frappe.app.trigger_primary_action();
	e.preventDefault();
	return false;
}, __('Trigger Primary Action'));

frappe.ui.keys.add_shortcut('ctrl+g', function(e) {
	$("#navbar-search").focus();
	e.preventDefault();
	return false;
}, __('Open Awesomebar'));

frappe.ui.keys.add_shortcut('ctrl+h', function(e) {
	e.preventDefault();
	$('.navbar-home img').click();
}, __('Home'));

frappe.ui.keys.add_shortcut('alt+s', function(e) {
	e.preventDefault();
	$('.dropdown-navbar-user a').eq(0).click();
}, __('Settings'));

frappe.ui.keys.add_shortcut('shift+/', function() {
	frappe.ui.keys.show_keyboard_shortcut_dialog();
}, __('Keyboard Shortcuts'));

frappe.ui.keys.add_shortcut('alt+h', function(e) {
	e.preventDefault();
	$('.dropdown-help a').eq(0).click();
}, __('Help'));

frappe.ui.keys.on('escape', function(e) {
    close_grid_and_dialog();
});

frappe.ui.keys.on('esc', function(e) {
    close_grid_and_dialog();
});

frappe.ui.keys.on('enter', function(e) {
	if(window.cur_dialog && cur_dialog.confirm_dialog) {
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

frappe.ui.keys.add_shortcut('shift+ctrl+r', function(e) {
	frappe.ui.toolbar.clear_cache();
}, __('Clear Cache and Reload'));

frappe.ui.keys.key_map = {
	8: 'backspace',
	9: 'tab',
	13: 'enter',
	16: 'shift',
	17: 'ctrl',
	91: 'meta',
	18: 'alt',
	27: 'escape',
	37: 'left',
	39: 'right',
	38: 'up',
	40: 'down',
	32: 'space',
	112: 'f1',
	113: 'f2',
	114: 'f3',
	115: 'f4',
	116: 'f5',
	191: '/'
}

'abcdefghijklmnopqrstuvwxyz'.split('').forEach((letter, i) => {
	frappe.ui.keys.key_map[65 + i] = letter;
});

// keyCode map
frappe.ui.keyCode = {
	ESCAPE: 27,
	LEFT: 37,
	RIGHT: 39,
	UP: 38,
	DOWN: 40,
	ENTER: 13,
	TAB: 9,
	SPACE: 32,
	BACKSPACE: 8
}

function close_grid_and_dialog() {
	// close open grid row
	var open_row = $(".grid-row-open");
	if (open_row.length) {
		var grid_row = open_row.data("grid_row");
		grid_row.toggle_view(false);
		return false;
	}

	// close open dialog
	if (cur_dialog && !cur_dialog.no_cancel_flag) {
		cur_dialog.cancel();
		return false;
	}
}

// blur when escape is pressed on dropdowns
$(document).on('keydown', '.dropdown-toggle', (e) => {
    if (e.which === frappe.ui.keyCode.ESCAPE) {
        $(e.currentTarget).blur();
    }
})