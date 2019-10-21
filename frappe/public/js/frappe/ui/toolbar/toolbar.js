// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.toolbar");
frappe.provide('frappe.search');

frappe.ui.toolbar.Toolbar = Class.extend({
	init: function() {
		$('header').append(frappe.render_template("navbar", {
			avatar: frappe.avatar(frappe.session.user)
		}));
		$('.dropdown-toggle').dropdown();

		let awesome_bar = new frappe.search.AwesomeBar();
		awesome_bar.setup("#navbar-search");
		awesome_bar.setup("#modal-search");

		this.setup_notifications();
		this.make();
	},

	make: function() {
		this.setup_sidebar();
		this.setup_help();

		this.bind_events();

		$(document).trigger('toolbar_setup');
	},

	bind_events: function() {
		// clear all custom menus on page change
		$(document).on("page-change", function() {
			$("header .navbar .custom-menu").remove();
		});

		//focus search-modal on show in mobile view
		$('#search-modal').on('shown.bs.modal', function() {
			var search_modal = $(this);
			setTimeout(function() {
				search_modal.find('#modal-search').focus();
			}, 300);
		});
		$('.navbar-toggle-full-width').click(() => {
			frappe.ui.toolbar.toggle_full_width();
		});
	},

	setup_sidebar: function() {
		var header = $('header');
		header.find(".toggle-sidebar").on("click", function() {
			var layout_side_section = $('.layout-side-section');
			var overlay_sidebar = layout_side_section.find('.overlay-sidebar');

			overlay_sidebar.addClass('opened');
			overlay_sidebar.find('.reports-dropdown')
				.removeClass('dropdown-menu')
				.addClass('list-unstyled');
			overlay_sidebar.find('.dropdown-toggle')
				.addClass('text-muted').find('.caret')
				.addClass('hidden-xs hidden-sm');

			$('<div class="close-sidebar">').hide().appendTo(layout_side_section).fadeIn();

			var scroll_container = $('html');
			scroll_container.css("overflow-y", "hidden");

			layout_side_section.find(".close-sidebar").on('click', close_sidebar);
			layout_side_section.on("click", "a:not(.dropdown-toggle)", close_sidebar);

			function close_sidebar(e) {
				scroll_container.css("overflow-y", "");

				layout_side_section.find("div.close-sidebar").fadeOut(function() {
					overlay_sidebar.removeClass('opened')
						.find('.dropdown-toggle')
						.removeClass('text-muted');
					overlay_sidebar.find('.reports-dropdown')
						.addClass('dropdown-menu');
				});
			}
		});
	},

	setup_help: function() {
		frappe.provide('frappe.help');
		frappe.help.show_results = show_results;

		this.search = new frappe.search.SearchDialog();
		frappe.provide('frappe.searchdialog');
		frappe.searchdialog.search = this.search;

		$(".dropdown-help .dropdown-toggle").on("click", function() {
			$(".dropdown-help input").focus();
		});

		$(".dropdown-help .dropdown-menu").on("click", "input, button", function(e) {
			e.stopPropagation();
		});

		$("#input-help").on("keydown", function(e) {
			if(e.which == 13) {
				$(this).val("");
			}
		});

		$(document).on("page-change", function () {
			var $help_links = $(".dropdown-help #help-links");
			$help_links.html("");

			var route = frappe.get_route_str();
			var breadcrumbs = route.split("/");

			var links = [];
			for (var i = 0; i < breadcrumbs.length; i++) {
				var r = route.split("/", i + 1);
				var key = r.join("/");
				var help_links = frappe.help.help_links[key] || [];
				links = $.merge(links, help_links);
			}

			if(links.length === 0) {
				$help_links.next().hide();
			} else {
				$help_links.next().show();
			}

			for (var i = 0; i < links.length; i++) {
				var link = links[i];
				var url = link.url;
				$("<a>", {
					href: link.url,
					text: link.label,
					target: "_blank"
				}).appendTo($help_links);
			}

			$('.dropdown-help .dropdown-menu').on('click', 'a', show_results);
		});

		var $result_modal = frappe.get_modal("", "");
		$result_modal.addClass("help-modal");

		$(document).on("click", ".help-modal a", show_results);

		function show_results(e) {
			//edit links
			var href = e.target.href;
			if(href.indexOf('blob') > 0) {
				window.open(href, '_blank');
			}
			var path = $(e.target).attr("data-path");
			if(path) {
				e.preventDefault();
			}
		}
	},

	setup_notifications: function() {
		this.notifications = new frappe.ui.Notifications();
	}

});

$.extend(frappe.ui.toolbar, {
	add_dropdown_button: function(parent, label, click, icon) {
		var menu = frappe.ui.toolbar.get_menu(parent);
		if(menu.find("li:not(.custom-menu)").length && !menu.find(".divider").length) {
			frappe.ui.toolbar.add_menu_divider(menu);
		}

		return $('<li class="custom-menu"><a><i class="fa-fw '
			+icon+'"></i> '+label+'</a></li>')
			.insertBefore(menu.find(".divider"))
			.find("a")
			.click(function() {
				click.apply(this);
			});
	},
	get_menu: function(label) {
		return $("#navbar-" + label.toLowerCase());
	},
	add_menu_divider: function(menu) {
		menu = typeof menu == "string" ?
			frappe.ui.toolbar.get_menu(menu) : menu;

		$('<li class="divider custom-menu"></li>').prependTo(menu);
	},
	add_icon_link(route, icon, index, class_name) {
		let parent_element = $(".navbar-right").get(0);
		let new_element = $(`<li class="${class_name}">
			<a class="btn" href="${route}" title="${frappe.utils.to_title_case(class_name, true)}" aria-haspopup="true" aria-expanded="true">
				<div>
					<i class="octicon ${icon}"></i>
				</div>
			</a>
		</li>`).get(0);

		parent_element.insertBefore(new_element, parent_element.children[index]);
	},
	toggle_full_width() {
		let fullwidth = JSON.parse(localStorage.container_fullwidth || 'false');
		fullwidth = !fullwidth;
		localStorage.container_fullwidth = fullwidth;
		frappe.ui.toolbar.set_fullwidth_if_enabled();
	},
	set_fullwidth_if_enabled() {
		let fullwidth = JSON.parse(localStorage.container_fullwidth || 'false');
		$(document.body).toggleClass('full-width', fullwidth);
	},
	show_shortcuts (e) {
		e.preventDefault();
		frappe.ui.keys.show_keyboard_shortcut_dialog();
		return false;
	},
});

frappe.ui.toolbar.clear_cache = frappe.utils.throttle(function() {
	frappe.assets.clear_local_storage();
	frappe.xcall('frappe.sessions.clear').then(message => {
		frappe.show_alert({
			message: message,
			indicator: 'green'
		});
		location.reload(true);
	});
}, 10000);

frappe.ui.toolbar.show_about = function() {
	try {
		frappe.ui.misc.about();
	} catch(e) {
		console.log(e);
	}
	return false;
};

frappe.ui.toolbar.setup_session_defaults = function() {
	let fields = [];
	frappe.call({
		method: 'frappe.core.doctype.session_default_settings.session_default_settings.get_session_default_values',
		callback: function (data) {
			fields = JSON.parse(data.message);
			let perms = frappe.perm.get_perm('Session Default Settings');
			//add settings button only if user is a System Manager or has permission on 'Session Default Settings'
			if ((in_list(frappe.user_roles, 'System Manager')) || (perms[0].read == 1))  {
				fields[fields.length] = {
					'fieldname': 'settings',
					'fieldtype': 'Button',
					'label': __('Settings'),
					'click': () => {
						frappe.set_route('Form', 'Session Default Settings', 'Session Default Settings');
					}
				};
			}
			frappe.prompt(fields, function(values) {
				//if default is not set for a particular field in prompt
				fields.forEach(function(d) {
					if (!values[d.fieldname]) {
						values[d.fieldname] = "";
					}
				});
				frappe.call({
					method: 'frappe.core.doctype.session_default_settings.session_default_settings.set_session_default_values',
					args: {
						default_values: values,
					},
					callback: function(data) {
						if (data.message == "success") {
							frappe.show_alert({
								'message': __('Session Defaults Saved'),
								'indicator': 'green'
							});
							frappe.ui.toolbar.clear_cache();
						}	else {
							frappe.show_alert({
								'message': __('An error occurred while setting Session Defaults'),
								'indicator': 'red'
							});
						}
					}
				});
			},
			__('Session Defaults'),
			__('Save'),
			);
		}
	});
};
