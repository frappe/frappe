frappe.provide('frappe.ui.keys');

let shortcut_groups = new WeakMap();
let shortcut_group_list = [];
frappe.ui.keys.shortcut_groups = shortcut_groups;

frappe.ui.keys.get_shortcut_group = (parent) => {
	// parent must be an object
	if (!shortcut_groups.has(parent)) {
		shortcut_groups.set(parent, new frappe.ui.keys.AltShortcutGroup());
	}
	return shortcut_groups.get(parent);
};

let listener_added = false;
let $current_dropdown = null;
let $body = $(document.body);

frappe.ui.keys.bind_shortcut_group_event = () => {
	if (listener_added) return;
	listener_added = true;

	function highlight_alt_shortcuts() {
		if ($current_dropdown) {
			$current_dropdown.addClass('alt-pressed');
			$body.removeClass('alt-pressed');
		} else {
			$body.addClass('alt-pressed');
			$current_dropdown && $current_dropdown.removeClass('alt-pressed');
		}
	}

	function unhighlight_alt_shortcuts() {
		$current_dropdown && $current_dropdown.removeClass('alt-pressed');
		$body.removeClass('alt-pressed');
	}

	$(document).on('keydown', (e) => {
		let key = (frappe.ui.keys.key_map[e.which] || '').toLowerCase();

		if (key === 'alt') {
			highlight_alt_shortcuts();
		}

		if (e.shiftKey || e.ctrlKey || e.metaKey) {
			return;
		}

		if (key && e.altKey) {
			let shortcut = get_shortcut_for_key(key);
			if (shortcut) {
				e.preventDefault();
				shortcut.$target[0].click();
			}
			highlight_alt_shortcuts();
		}
	});
	$(document).on('keyup', (e) => {
		if (e.key === 'Alt') {
			unhighlight_alt_shortcuts();
		}
	});
	$(document).on('mousemove', () => {
		unhighlight_alt_shortcuts();
	});
};

function get_shortcut_for_key(key) {
	// Get the shortcut for combination of alt+key
	// Priority 1: Open dropdown
	// Priority 2: Current Page

	let shortcuts = shortcut_group_list
		.filter(shortcut_group => key in shortcut_group.shortcuts_dict)
		.map(shortcut_group => shortcut_group.shortcuts_dict[key])
		.filter(shortcut => shortcut.$target.is(':visible'));

	let shortcut = null;

	if ($current_dropdown && $current_dropdown.is('.open')) {
		shortcut = shortcuts.find(
			shortcut => $.contains($current_dropdown[0], shortcut.$target[0])
		);
	}

	if (shortcut) return shortcut;

	shortcut = shortcuts.find(
		shortcut => $.contains(window.cur_page.page.page.wrapper[0], shortcut.$target[0])
	);

	return shortcut;
}

frappe.ui.keys.AltShortcutGroup = class AltShortcutGroup {
	constructor() {
		this.shortcuts_dict = {};
		$current_dropdown = null;
		this.bind_events();
		frappe.ui.keys.bind_shortcut_group_event();
		shortcut_group_list.push(this);
	}

	bind_events() {
		$(document).on('show.bs.dropdown', (e) => {
			$current_dropdown && $current_dropdown.removeClass('alt-pressed');
			let $target = $(e.target);
			if ($target.is('.dropdown, .btn-group')) {
				$current_dropdown = $target;
			}
		});
		$(document).on('hide.bs.dropdown', () => {
			$current_dropdown && $current_dropdown.removeClass('alt-pressed');
			$current_dropdown = null;
		});
	}

	add($target, $text_el) {
		if (!$text_el) {
			$text_el = $target;
		}
		let text_content = $text_el.text().trim();
		let letters = text_content.split('');
		// first unused letter
		let shortcut_letter = letters.find(letter => {
			letter = letter.toLowerCase();
			let is_valid_char = letter >= 'a' && letter <= 'z';
			return !this.is_taken(letter) && is_valid_char;
		});
		if (!shortcut_letter) {
			$text_el.attr('data-label', text_content);
			return;
		}
		for (let key in this.shortcuts_dict) {
			let shortcut = this.shortcuts_dict[key];
			if (shortcut.text === text_content) {
				shortcut.$target = $target;
				shortcut.$text_el = $text_el;
				this.underline_text(shortcut);
				return;
			}
		}

		let shortcut = {
			$target,
			$text_el,
			letter: shortcut_letter,
			text: text_content
		};
		this.shortcuts_dict[shortcut_letter.toLowerCase()] = shortcut;
		this.underline_text(shortcut);
	}

	underline_text(shortcut) {
		shortcut.$text_el.attr('data-label', shortcut.text);
		let underline_el_found = false;
		let text_html = shortcut.text.split('').map(letter => {
			if (letter === shortcut.letter && !underline_el_found) {
				letter = `<span class="alt-underline">${letter}</span>`;
				underline_el_found = true;
			}
			return letter;
		}).join('');
		let original_text_html = shortcut.$text_el.html();
		text_html = original_text_html.replace(shortcut.text.trim(), text_html.trim());
		shortcut.$text_el.html(text_html);
	}

	is_taken(letter) {
		let is_in_global_shortcut = frappe.ui.keys.standard_shortcuts
			.filter(s => !s.page)
			.some(s => s.shortcut === `alt+${letter}`);
		return letter in this.shortcuts_dict || is_in_global_shortcut;
	}
};
