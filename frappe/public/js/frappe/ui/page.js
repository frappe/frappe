// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

/**
 * Make a standard page layout with a toolbar and title
 *
 * @param {Object} opts
 *
 * @param {string} opts.parent [HTMLElement] Parent element
 * @param {boolean} opts.single_column Whether to include sidebar
 * @param {string} [opts.title] Page title
 * @param {Object} [opts.make_page]
 *
 * @returns {frappe.ui.Page}
 */

/**
 * @typedef {Object} frappe.ui.Page
 */


frappe.ui.make_app_page = function(opts) {
	opts.parent.page = new frappe.ui.Page(opts);
	return opts.parent.page;
}

frappe.ui.pages = {};

frappe.ui.Page = Class.extend({
	init: function(opts) {
		$.extend(this, opts);

		this.set_document_title = true;
		this.buttons = {};
		this.fields_dict = {};
		this.views = {};

		this.make();
		frappe.ui.pages[frappe.get_route_str()] = this;
	},

	make: function() {
		this.wrapper = $(this.parent);
		this.add_main_section();
		this.setup_scroll_handler();
		this.setup_sidebar_toggle();
	},

	setup_scroll_handler() {
		window.addEventListener('scroll', () => {
			if (document.documentElement.scrollTop) {
				$('.page-head').toggleClass('drop-shadow', true);
			} else {
				$('.page-head').removeClass('drop-shadow');
			}
		});
	},

	get_empty_state: function(title, message, primary_action) {
		let $empty_state = $(`<div class="page-card-container">
			<div class="page-card">
				<div class="page-card-head">
					<span class="indicator blue">
						${title}</span>
				</div>
				<p>${message}</p>
				<div>
					<button class="btn btn-primary btn-sm">${primary_action}</button>
				</div>
			</div>
		</div>`);

		return $empty_state;
	},

	load_lib: function(callback) {
		frappe.require(this.required_libs, callback);
	},

	add_main_section: function() {
		$(frappe.render_template("page", {})).appendTo(this.wrapper);
		if (this.single_column) {
			// nesting under col-sm-12 for consistency
			this.add_view("main", '<div class="row layout-main">\
					<div class="col-md-12 layout-main-section-wrapper">\
						<div class="layout-main-section"></div>\
						<div class="layout-footer hide"></div>\
					</div>\
				</div>');
		} else {
			this.add_view("main", `
				<div class="row layout-main">
					<div class="col-lg-2 layout-side-section"></div>
					<div class="col layout-main-section-wrapper">
						<div class="layout-main-section"></div>
						<div class="layout-footer hide"></div>
					</div>
				</div>
			`);
		}

		this.setup_page();
	},

	setup_page: function() {
		this.$title_area = this.wrapper.find(".title-area");

		this.$sub_title_area = this.wrapper.find("h6");

		if(this.title)
			this.set_title(this.title);

		if(this.icon)
			this.get_main_icon(this.icon);

		this.body = this.main = this.wrapper.find(".layout-main-section");
		this.container = this.wrapper.find(".page-body");
		this.sidebar = this.wrapper.find(".layout-side-section");
		this.footer = this.wrapper.find(".layout-footer");
		this.indicator = this.wrapper.find(".indicator-pill");

		this.page_actions = this.wrapper.find(".page-actions");

		this.btn_primary = this.page_actions.find(".primary-action");
		this.btn_secondary = this.page_actions.find(".btn-secondary");

		this.menu = this.page_actions.find(".menu-btn-group .dropdown-menu");
		this.menu_btn_group = this.page_actions.find(".menu-btn-group");

		this.actions = this.page_actions.find(".actions-btn-group .dropdown-menu");
		this.actions_btn_group = this.page_actions.find(".actions-btn-group");

		this.standard_actions = this.page_actions.find(".standard-actions");
		this.custom_actions = this.page_actions.find(".custom-actions");

		this.page_form = $('<div class="page-form row hide"></div>').prependTo(this.main);
		this.inner_toolbar = this.custom_actions;
		this.icon_group = this.page_actions.find(".page-icon-group");

		if(this.make_page) {
			this.make_page();
		}

		this.card_layout && this.main.addClass('frappe-card');

		// keyboard shortcuts
		let menu_btn = this.menu_btn_group.find('button');
		menu_btn.attr("title", __("Menu")).tooltip({ delay: { "show": 600, "hide": 100 } });
		frappe.ui.keys
			.get_shortcut_group(this.page_actions[0])
			.add(menu_btn, menu_btn.find('.menu-btn-group-label'));

		let action_btn = this.actions_btn_group.find('button');
		frappe.ui.keys
			.get_shortcut_group(this.page_actions[0])
			.add(action_btn, action_btn.find('.actions-btn-group-label'));
	},

	setup_sidebar_toggle() {
		let sidebar_toggle = $('.page-head').find('.sidebar-toggle-btn');
		let sidebar_wrapper = this.wrapper.find('.layout-side-section');
		if (this.disable_sidebar_toggle || !sidebar_wrapper.length) {
			sidebar_toggle.remove();
		} else {
			sidebar_toggle.attr("title", __("Toggle Sidebar")).tooltip({
				delay: { "show": 600, "hide": 100 },
				trigger: "hover",
			});
			sidebar_toggle.click(() => {
				if (frappe.utils.is_xs() || frappe.utils.is_sm()) {
					this.setup_overlay_sidebar();
				} else {
					sidebar_wrapper.toggle();
				}
				$(document.body).trigger('toggleSidebar');
				this.update_sidebar_icon();
			});
		}
	},

	setup_overlay_sidebar() {
		let overlay_sidebar = this.sidebar.find('.overlay-sidebar')
			.addClass('opened');
		$('<div class="close-sidebar">').hide().appendTo(this.sidebar).fadeIn();
		let scroll_container = $('html')
			.css("overflow-y", "hidden");

		this.sidebar.find(".close-sidebar").on('click', (e) => close_sidebar(e));
		this.sidebar.on("click", "button:not(.dropdown-toggle)", (e) => close_sidebar(e));

		let close_sidebar = () => {
			scroll_container.css("overflow-y", "");
			this.sidebar.find("div.close-sidebar").fadeOut(() => {
				overlay_sidebar.removeClass('opened')
					.find('.dropdown-toggle')
					.removeClass('text-muted');
			});
		};
	},

	update_sidebar_icon() {
		let sidebar_toggle = $('.page-head').find('.sidebar-toggle-btn');
		let sidebar_toggle_icon = sidebar_toggle.find('.sidebar-toggle-icon');
		let sidebar_wrapper = this.wrapper.find('.layout-side-section');
		let is_sidebar_visible = $(sidebar_wrapper).is(":visible");
		sidebar_toggle_icon.html(frappe.utils.icon(is_sidebar_visible ? 'sidebar-collapse' : 'sidebar-expand', 'md'));
	},

	set_indicator: function(label, color) {
		this.clear_indicator().removeClass("hide").html(`<span>${label}</span>`).addClass(color);
	},

	add_action_icon: function(icon, click, css_class='', tooltip_label) {
		const button = $(`
			<button class="text-muted btn btn-default ${css_class} icon-btn">
				${frappe.utils.icon(icon)}
			</button>
		`);

		button.appendTo(this.icon_group.removeClass("hide"));
		button.click(click);
		button.attr("title", __(tooltip_label || frappe.unscrub(icon)))
			.tooltip({ delay: { "show": 600, "hide": 100 }, trigger: "hover" });

		return button;
	},

	clear_indicator: function() {
		return this.indicator.removeClass().addClass("indicator-pill whitespace-nowrap hide");
	},

	get_icon_label: function(icon, label) {
		let icon_name = icon;
		let size = 'xs';
		if (typeof icon === 'object') {
			icon_name = icon.icon;
			size = icon.size || 'xs';
		}
		return `${icon ? frappe.utils.icon(icon_name, size) : ''} <span class="hidden-xs"> ${__(label)} </span>`;
	},

	set_action: function(btn, opts) {
		let me = this;
		if (opts.icon) {
			opts.label = this.get_icon_label(opts.icon, opts.label);
		}

		this.clear_action_of(btn);

		btn.removeClass("hide")
			.prop("disabled", false)
			.html(opts.label)
			.on("click", function() {
				let response = opts.click.apply(this);
				me.btn_disable_enable(btn, response);
			});

		if (opts.working_label) {
			btn.attr("data-working-label", opts.working_label);
		}

		// alt shortcuts
		let text_span = btn.find('span');
		frappe.ui.keys
			.get_shortcut_group(this)
			.add(btn, text_span.length ? text_span : btn);
	},

	set_primary_action: function(label, click, icon, working_label) {
		this.set_action(this.btn_primary, {
			label: label,
			click: click,
			icon: icon,
			working_label: working_label
		});
		return this.btn_primary;

	},

	set_secondary_action: function(label, click, icon, working_label) {
		this.set_action(this.btn_secondary, {
			label: label,
			click: click,
			icon: icon,
			working_label: working_label
		});

		return this.btn_secondary;
	},


	clear_action_of: function(btn) {
		btn.addClass("hide").unbind("click").removeAttr("data-working-label");
	},

	clear_primary_action: function() {
		this.clear_action_of(this.btn_primary);
	},

	clear_secondary_action: function() {
		this.clear_action_of(this.btn_secondary);
	},

	clear_actions: function() {
		this.clear_primary_action();
		this.clear_secondary_action();
	},

	clear_custom_actions() {
		this.custom_actions.addClass("hide").empty();
	},

	clear_icons: function() {
		this.icon_group.addClass("hide").empty();
	},

	//--- Menu --//

	add_menu_item: function(label, click, standard, shortcut, show_parent) {
		return this.add_dropdown_item({
			label,
			click,
			standard,
			parent: this.menu,
			shortcut,
			show_parent,
		});
	},

	add_custom_menu_item: function(parent, label, click, standard, shortcut, icon=null) {
		return this.add_dropdown_item({
			label,
			click,
			standard,
			parent: parent,
			shortcut,
			icon
		});
	},

	clear_menu: function() {
		this.clear_btn_group(this.menu);
	},

	show_menu: function() {
		this.menu_btn_group.removeClass("hide");
	},

	hide_menu: function() {
		this.menu_btn_group.addClass("hide");
	},

	show_icon_group: function() {
		this.icon_group.removeClass("hide");
	},

	hide_icon_group: function() {
		this.icon_group.addClass("hide");
	},

	//--- Actions Menu--//

	show_actions_menu: function() {
		this.actions_btn_group.removeClass("hide");
	},

	hide_actions_menu: function() {
		this.actions_btn_group.addClass("hide");
	},


	add_action_item: function(label, click, standard) {
		return this.add_dropdown_item({
			label,
			click,
			standard,
			parent: this.actions
		});
	},

	add_actions_menu_item: function(label, click, standard) {
		return this.add_dropdown_item({
			label,
			click,
			standard,
			parent: this.actions,
			show_parent: false
		});
	},

	clear_actions_menu: function() {
		this.clear_btn_group(this.actions);
	},


	//-- Generic --//

	/*
	* Add label to given drop down menu. If label, is already contained in the drop
	* down menu, it will be ignored.
	* @param {string} label - Text for the drop down menu
	* @param {function} click - function to be called when `label` is clicked
	* @param {Boolean} standard
	* @param {object} parent - DOM object representing the parent of the drop down item lists
	* @param {string} shortcut - Keyboard shortcut associated with the element
	* @param {Boolean} show_parent - Whether to show the dropdown button if dropdown item is added
	*/
	add_dropdown_item: function({label, click, standard, parent, shortcut, show_parent=true, icon=null}) {
		if (show_parent) {
			parent.parent().removeClass("hide hidden-xl");
		}

		let $link = this.is_in_group_button_dropdown(parent, 'li > a.grey-link > span', label);
		if ($link) return $link;

		let $li;
		let $icon = ``;

		if (icon) {
			$icon = `<span class="menu-item-icon">${frappe.utils.icon(icon)}</span>`;
		}

		if (shortcut) {
			let shortcut_obj = this.prepare_shortcut_obj(shortcut, click, label);
			$li = $(`
				<li>
					<a class="grey-link dropdown-item" href="#" onClick="return false;">
						${$icon}
						<span class="menu-item-label">${label}</span>
						<kbd class="pull-right">
							<span>${shortcut_obj.shortcut_label}</span>
						</kbd>
					</a>
				</li>
			`);
			frappe.ui.keys.add_shortcut(shortcut_obj);
		} else {
			$li = $(`
				<li>
					<a class="grey-link dropdown-item" href="#" onClick="return false;">
						${$icon}
						<span class="menu-item-label">${label}</span>
					</a>
				</li>
			`);
		}

		$link = $li.find("a").on("click", click);

		if (standard) {
			$li.appendTo(parent);
		} else {
			this.divider = parent.find(".dropdown-divider");
			if(!this.divider.length) {
				this.divider = $('<li class="dropdown-divider user-action"></li>').prependTo(parent);
			}
			$li.addClass("user-action").insertBefore(this.divider);
		}

		// alt shortcut
		frappe.ui.keys
			.get_shortcut_group(parent.get(0))
			.add($link, $link.find('.menu-item-label'));

		return $link;
	},

	prepare_shortcut_obj(shortcut, click, label) {
		let shortcut_obj;
		// convert to object, if shortcut string passed
		if (typeof shortcut === 'string') {
			shortcut_obj = { shortcut };
		} else {
			shortcut_obj = shortcut;
		}
		// label
		if (frappe.utils.is_mac()) {
			shortcut_obj.shortcut_label = shortcut_obj.shortcut.replace('Ctrl', '⌘');
		} else {
			shortcut_obj.shortcut_label = shortcut_obj.shortcut;
		}
		// actual shortcut string
		shortcut_obj.shortcut = shortcut_obj.shortcut.toLowerCase();
		// action is button click
		if (!shortcut_obj.action) {
			shortcut_obj.action = click;
		}
		// shortcut description can be button label
		if (!shortcut_obj.description) {
			shortcut_obj.description = label;
		}
		// page
		shortcut_obj.page = this;
		return shortcut_obj;
	},

	/*
	* Check if there already exists a button with a specified label in a specified button group
	* @param {object} parent - This should be the `ul` of the button group.
	* @param {string} selector - CSS Selector of the button to be searched for. By default, it is `li`.
	* @param {string} label - Label of the button
	*/
	is_in_group_button_dropdown: function(parent, selector, label) {

		if (!selector) selector = 'li';

		if (!label || !parent) return false;

		const item_selector = `${selector}[data-label="${encodeURIComponent(label)}"]`;

		const existing_items = $(parent).find(item_selector);
		if (existing_items && existing_items.length > 0) return existing_items;
	},

	clear_btn_group: function(parent) {
		parent.empty();
		parent.parent().addClass("hide");
	},

	add_divider: function() {
		return $('<li class="dropdown-divider"></li>').appendTo(this.menu);
	},

	get_or_add_inner_group_button: function(label) {
		var $group = this.inner_toolbar.find(`.inner-group-button[data-label="${encodeURIComponent(label)}"]`);
		if (!$group.length) {
			$group = $(
				`<div class="inner-group-button" data-label="${encodeURIComponent(label)}">
					<button type="button" class="btn btn-default ellipsis" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
						${label}
						${frappe.utils.icon('select', 'xs')}
					</button>
					<div role="menu" class="dropdown-menu"></div>
				</div>`
			).appendTo(this.inner_toolbar);
		}
		return $group;
	},

	get_inner_group_button: function(label) {
		return this.inner_toolbar.find(`.inner-group-button[data-label="${encodeURIComponent(label)}"]`);
	},

	set_inner_btn_group_as_primary: function(label) {
		this.get_or_add_inner_group_button(label).find("button").removeClass("btn-default").addClass("btn-primary");
	},

	btn_disable_enable: function(btn, response) {
		if (response && response.then) {
			btn.prop('disabled', true);
			response.then(() => {
				btn.prop('disabled', false);
			})
		} else if (response && response.always) {
			btn.prop('disabled', true);
			response.always(() => {
				btn.prop('disabled', false);
			});
		}
	},

	/*
	* Add button to button group. If there exists another button with the same label,
	* `add_inner_button` will not add the new button to the button group even if the callback
	* function is different.
	*
	* @param {string} label - Label of the button to be added to the group
	* @param {object} action - function to be called when button is clicked
	* @param {string} group - Label of the group button
	*/
	add_inner_button: function(label, action, group, type="default") {
		var me = this;
		let _action = function() {
			let btn = $(this);
			let response = action();
			me.btn_disable_enable(btn, response);
		};
		// Add actions as menu item in Mobile View
		let menu_item_label = group ? `${group} > ${label}` : label;
		let menu_item = this.add_menu_item(menu_item_label, _action, false, false, false);
		menu_item.parent().addClass("hidden-xl");
		if (this.menu_btn_group.hasClass("hide")) {
			this.menu_btn_group.removeClass("hide").addClass("hidden-xl");
		}

		if (group) {
			var $group = this.get_or_add_inner_group_button(group);
			$(this.inner_toolbar).removeClass("hide");

			if (!this.is_in_group_button_dropdown($group.find(".dropdown-menu"), 'a', label)) {
				return $(`<a class="dropdown-item" href="#" onclick="return false;" data-label="${encodeURIComponent(label)}">${label}</a>`)
					.on('click', _action)
					.appendTo($group.find(".dropdown-menu"));
			}

		} else {
			let button = this.inner_toolbar.find(`button[data-label="${encodeURIComponent(label)}"]`);
			if (button.length == 0) {
				button = $(`<button data-label="${encodeURIComponent(label)}" class="btn btn-${type} ellipsis">
					${__(label)}
				</button>`);
				button.on("click", _action);
				button.appendTo(this.inner_toolbar.removeClass("hide"));
			}
			return button;
		}
	},

	remove_inner_button: function(label, group) {
		if (typeof label === 'string') {
			label = [label];
		}
		// translate
		label = label.map(l => __(l));

		if (group) {
			var $group = this.get_inner_group_button(__(group));
			if ($group.length) {
				$group.find(`.dropdown-item[data-label="${encodeURIComponent(label)}"]`).remove();
			}
			if ($group.find('.dropdown-item').length === 0) $group.remove();
		} else {
			this.inner_toolbar.find(`button[data-label="${encodeURIComponent(label)}"]`).remove();
		}
	},

	change_inner_button_type: function(label, group, type) {
		let btn;

		if (group) {
			var $group = this.get_inner_group_button(__(group));
			if ($group.length) {
				btn = $group.find(`.dropdown-item[data-label="${encodeURIComponent(label)}"]`);
			}
		} else {
			btn = this.inner_toolbar.find(`button[data-label="${encodeURIComponent(label)}"]`);
		}

		if (btn) {
			btn.removeClass().addClass(`btn btn-${type} ellipsis`);
		}
	},

	add_inner_message: function(message) {
		let $message = $(`<span class='inner-page-message text-muted small'>${message}</div>`);
		this.inner_toolbar.find('.inner-page-message').remove();
		this.inner_toolbar.removeClass("hide").prepend($message);

		return $message;
	},

	clear_inner_toolbar: function() {
		this.inner_toolbar.empty().addClass("hide");
	},

	//-- Sidebar --//

	add_sidebar_item: function(label, action, insert_after, prepend) {
		var parent = this.sidebar.find(".sidebar-menu.standard-actions");
		var li = $('<li>');
		var link = $('<a>').html(label).on("click", action).appendTo(li);

		if (insert_after) {
			li.insertAfter(parent.find(insert_after));
		} else {
			if(prepend) {
				li.prependTo(parent);
			} else {
				li.appendTo(parent);
			}
		}
		return link;
	},

	//---//

	clear_user_actions: function() {
		this.menu.find(".user-action").remove();
	},

	// page::title
	get_title_area: function() {
		return this.$title_area;
	},

	set_title: function(title, icon=null, strip=true, tab_title="") {
		if (!title) title = "";
		if (strip) {
			title = strip_html(title);
		}
		this.title = title;
		frappe.utils.set_title(tab_title || title);
		if (icon) {
			title = `${frappe.utils.icon(icon)} ${title}`;
		}
		let title_wrapper = this.$title_area.find(".title-text");
		title_wrapper.html(title);
		title_wrapper.attr('title', this.title);
	},

	set_title_sub: function(txt) {
		// strip icon
		this.$sub_title_area.html(txt).toggleClass("hide", !!!txt);
	},

	get_main_icon: function(icon) {
		return this.$title_area.find(".title-icon")
			.html('<i class="'+icon+' fa-fw"></i> ')
			.toggle(true);
	},

	add_help_button: function(txt) {
		//
	},

	add_button: function(label, click, opts) {
		if (!opts) opts = {};
		let button = $(`<button
			class="btn ${opts.btn_class || 'btn-default'} ${opts.btn_size || 'btn-sm'} ellipsis">
				${opts.icon ? frappe.utils.icon(opts.icon): ''}
				${label}
		</button>`);
		// Add actions as menu item in Mobile View (similar to "add_custom_button" in forms.js)
		let menu_item = this.add_menu_item(label, click, false);
		menu_item.parent().addClass("hidden-xl");

		button.appendTo(this.custom_actions);
		button.on('click', click);
		this.custom_actions.removeClass('hide');

		return button;
	},

	add_custom_button_group: function(label, icon, parent) {
		let dropdown_label = `<span class="hidden-xs">
			<span class="custom-btn-group-label">${__(label)}</span>
			${frappe.utils.icon('select', 'xs')}
		</span>`;

		if (icon) {
			dropdown_label = `<span class="hidden-xs">
				${frappe.utils.icon(icon)}
				<span class="custom-btn-group-label">${__(label)}</span>
				${frappe.utils.icon('select', 'xs')}
			</span>
			<span class="visible-xs">
				${frappe.utils.icon(icon)}
			</span>`;
		}

		let custom_btn_group = $(`
			<div class="custom-btn-group">
				<button type="button" class="btn btn-default btn-sm ellipsis" data-toggle="dropdown" aria-expanded="false">
					${dropdown_label}
				</button>
				<ul class="dropdown-menu" role="menu"></ul>
			</div>
		`);

		if (!parent) parent = this.custom_actions;
		parent.removeClass('hide').append(custom_btn_group);

		return custom_btn_group.find('.dropdown-menu');
	},

	add_dropdown_button: function(parent, label, click, icon) {
		frappe.ui.toolbar.add_dropdown_button(parent, label, click, icon);
	},

	// page::form
	add_label: function(label) {
		this.show_form();
		return $("<label class='col-md-1 page-only-label'>"+label+" </label>")
			.appendTo(this.page_form);
	},
	add_select: function(label, options) {
		var field = this.add_field({label:label, fieldtype:"Select"});
		return field.$wrapper.find("select").empty().add_options(options);
	},
	add_data: function(label) {
		var field = this.add_field({label: label, fieldtype: "Data"});
		return field.$wrapper.find("input").attr("placeholder", label);
	},
	add_date: function(label, date) {
		var field = this.add_field({label: label, fieldtype: "Date", "default": date});
		return field.$wrapper.find("input").attr("placeholder", label);
	},
	add_check: function(label) {
		return $("<div class='checkbox'><label><input type='checkbox'>" + label + "</label></div>")
			.appendTo(this.page_form)
			.find("input");
	},
	add_break: function() {
		// add further fields in the next line
		this.page_form.append('<div class="clearfix invisible-xs"></div>');
	},
	add_field: function(df, parent) {
		this.show_form();

		if (!df.placeholder) {
			df.placeholder = df.label;
		}

		df.input_class = 'input-xs';

		var f = frappe.ui.form.make_control({
			df: df,
			parent: parent || this.page_form,
			only_input: df.fieldtype == "Check" ? false : true,
		})
		f.refresh();
		$(f.wrapper)
			.addClass('col-md-2')
			.attr("title", __(df.label)).tooltip({
				delay: { "show": 600, "hide": 100},
				trigger: "hover"
			});

		// html fields in toolbar are only for display
		if (df.fieldtype=='HTML') {
			return;
		}

		// hidden fields dont have $input
		if (!f.$input) f.make_input();

		f.$input.attr("placeholder", __(df.label));

		if(df.fieldtype==="Check") {
			$(f.wrapper).find(":first-child")
				.removeClass("col-md-offset-4 col-md-8");
		}

		if(df.fieldtype=="Button") {
			$(f.wrapper).find(".page-control-label").html("&nbsp;");
			f.$input.addClass("btn-xs").css({"width": "100%", "margin-top": "-1px"});
		}

		if(df["default"])
			f.set_input(df["default"])
		this.fields_dict[df.fieldname || df.label] = f;
		return f;
	},
	clear_fields: function() {
		this.page_form.empty();
	},
	show_form: function() {
		this.page_form.removeClass("hide");
	},
	hide_form: function() {
		this.page_form.addClass("hide");
	},
	get_form_values: function() {
		var values = {};
		this.page_form.fields_dict.forEach(function(field, key) {
			values[key] = field.get_value();
		});
		return values;
	},
	add_view: function(name, html) {
		let element = html;
		if(typeof (html) === "string") {
			element = $(html);
		}
		this.views[name] = element.appendTo($(this.wrapper).find(".page-content"));
		if(!this.current_view) {
			this.current_view = this.views[name];
		} else {
			this.views[name].toggle(false);
		}
		return this.views[name];
	},
	set_view: function(name) {
		if(this.current_view_name===name)
			return;
		this.current_view && this.current_view.toggle(false);
		this.current_view = this.views[name];

		this.previous_view_name = this.current_view_name;
		this.current_view_name = name;

		this.views[name].toggle(true);

		this.wrapper.trigger('view-change');
	},
});
