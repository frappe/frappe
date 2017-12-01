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

		this.make();
	},

	make: function() {
		this.setup_sidebar();
		this.setup_help();
		this.setup_progress_dialog();
		this.bind_events();

		$(document).trigger('toolbar_setup');
	},

	bind_events: function() {
		$(document).on("notification-update", function() {
			frappe.ui.notifications.update_notifications();
		});

		// clear all custom menus on page change
		$(document).on("page-change", function() {
			$("header .navbar .custom-menu").remove();
		});

		//focus search-modal on show in mobile view
		$('#search-modal').on('shown.bs.modal', function () {
			var search_modal = $(this);
			setTimeout(function() {
				search_modal.find('#modal-search').focus();
			}, 300);
		});
	},

	setup_sidebar: function () {
		var header = $('header');
		header.find(".toggle-sidebar").on("click", function () {
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
			layout_side_section.on("click", "a", close_sidebar);

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

	setup_help: function () {
		frappe.provide('frappe.help');
		frappe.help.show_results = show_results;

		this.search = new frappe.search.SearchDialog();
		frappe.provide('frappe.searchdialog');
		frappe.searchdialog.search = this.search;

		$(".dropdown-help .dropdown-toggle").on("click", function () {
			$(".dropdown-help input").focus();
		});

		$(".dropdown-help .dropdown-menu").on("click", "input, button", function (e) {
			e.stopPropagation();
		});

		$("#input-help").on("keydown", function (e) {
			if(e.which == 13) {
				var keywords = $(this).val();
				show_help_results(keywords);
				$(this).val("");
			}
		});

		$("#input-help + span").on("click", function () {
			var keywords = $("#input-help").val();
			show_help_results(keywords);
			$(this).val("");
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
			}
			else {
				$help_links.next().show();
			}

			for (var i = 0; i < links.length; i++) {
				var link = links[i];
				var url = link.url;
				var app_name = url.split('//', 2)[1].split('/', 2)[1];
				var data_path = url.slice(url.indexOf('/user'));
				if(data_path.lastIndexOf('.')){
					data_path = data_path.slice(0, data_path.lastIndexOf('.'));
				}
				data_path = data_path.replace('user', app_name);

				$("<a>", {
					href: link.url,
					text: link.label,
					target: "_blank",
					"data-path": data_path
				}).appendTo($help_links);
			}

			$('.dropdown-help .dropdown-menu').on('click', 'a', show_results);
		});

		var $result_modal = frappe.get_modal("", "");
		$result_modal.addClass("help-modal");

		$(document).on("click", ".help-modal a", show_results);

		var me = this;
		function show_help_results(keywords) {
			me.search.init_search(keywords, "help");
		}

		function show_results(e) {
			//edit links
			var href = e.target.href;
			if(href.indexOf('blob') > 0) {
				window.open(href, '_blank');
			}
			var converter = new Showdown.converter();
			var path = $(e.target).attr("data-path");
			if(path) {
				e.preventDefault();
				frappe.call({
					method: "frappe.utils.help.get_help_content",
					args: {
						path: path
					},
					callback: function (r) {
						if(r.message && r.message.title) {
							$result_modal.find('.modal-title').html("<span>"
								+ r.message.title + "</span>");
							$result_modal.find('.modal-body').html(r.message.content);
							$result_modal.modal('show');
						}
					}
				});
			}
		}
	},

	setup_progress_dialog: function() {
		var me = this;
		frappe.call({
			method: "frappe.desk.user_progress.get_user_progress_slides",
			callback: function(r) {
				if(r.message) {
					let slides = r.message;
					if(slides.length && slides.map(s => parseInt(s.done)).includes(0)) {
						frappe.require("assets/frappe/js/frappe/ui/toolbar/user_progress_dialog.js", function() {
							me.progress_dialog = new frappe.setup.UserProgressDialog({
								slides: slides
							});
							$('.user-progress').removeClass('hide');
							$('.user-progress .dropdown-toggle').on('click', () => {
								me.progress_dialog.show();
							});

							if (frappe.boot.is_first_startup) {
								me.progress_dialog.show();
								frappe.call({
									method: "frappe.desk.page.setup_wizard.setup_wizard.reset_is_first_startup",
									args: {},
									callback: () => {}
								});
							}

						});
					}
				}
			},
			freeze: false
		});
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
	}
});

frappe.ui.toolbar.clear_cache = function() {
	frappe.assets.clear_local_storage();
	frappe.call({
		method: 'frappe.sessions.clear',
		callback: function(r) {
			if(!r.exc) {
				frappe.show_alert({message:r.message, indicator:'green'});
				location.reload(true);
			}
		}
	})
	return false;
}

frappe.ui.toolbar.download_backup = function() {
	frappe.msgprint(__("Your download is being built, this may take a few moments..."));
	$c('frappe.utils.backups.get_backup',{},function(r,rt) {});
	return false;
}

frappe.ui.toolbar.show_about = function() {
	try {
		frappe.ui.misc.about();
	} catch(e) {
		console.log(e);
	}
	return false;
}
