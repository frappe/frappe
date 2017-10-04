frappe.provide('frappe.desktop');

frappe.pages['desktop'].on_page_load = function(wrapper) {

	// load desktop
	if(!frappe.list_desktop) {
		frappe.desktop.set_background();
	}
	frappe.desktop.refresh(wrapper);
};

frappe.pages['desktop'].on_page_show = function(wrapper) {
	if(frappe.list_desktop) {
		$("body").attr("data-route", "list-desktop");
	}
};

$.extend(frappe.desktop, {
	refresh: function(wrapper) {
		if (wrapper) {
			this.wrapper = $(wrapper);
		}

		this.render();
		this.make_sortable();
	},

	render: function() {
		var me = this;
		frappe.utils.set_title(__("Desktop"));

		var template = frappe.list_desktop ? "desktop_list_view" : "desktop_icon_grid";

		var all_icons = frappe.get_desktop_icons();
		var explore_icon = {
			module_name: 'Explore',
			label: 'Explore',
			_label: __('Explore'),
			_id: 'Explore',
			_doctype: '',
			icon: 'octicon octicon-telescope',
			color: '#7578f6',
			link: 'modules'
		};
		explore_icon.app_icon = frappe.ui.app_icon.get_html(explore_icon);
		all_icons.push(explore_icon);

		frappe.desktop.wrapper.html(frappe.render_template(template, {
			// all visible icons
			desktop_items: all_icons,
		}));

		frappe.desktop.setup_module_click();

		// notifications
		frappe.desktop.show_pending_notifications();
		$(document).on("notification-update", function() {
			me.show_pending_notifications();
		});

		$(document).trigger("desktop-render");

	},

	render_help_messages: function(help_messages) {
		var wrapper = frappe.desktop.wrapper.find('.help-message-wrapper');
		var $help_messages = wrapper.find('.help-messages');

		var set_current_message = function(idx) {
			idx = cint(idx);
			wrapper.current_message_idx = idx;
			wrapper.find('.left-arrow, .right-arrow').addClass('disabled');
			wrapper.find('.help-message-item').addClass('hidden');
			wrapper.find('[data-message-idx="'+idx+'"]').removeClass('hidden');
			if(idx > 0) {
				wrapper.find('.left-arrow').removeClass('disabled');
			}
			if(idx < help_messages.length - 1) {
				wrapper.find('.right-arrow').removeClass('disabled');
			}
		}

		if(help_messages) {
			wrapper.removeClass('hidden');
			help_messages.forEach(function(message, i) {
				var $message = $('<div class="help-message-item hidden"></div>')
					.attr('data-message-idx', i)
					.html(frappe.render_template('desktop_help_message', message))
					.appendTo($help_messages);

			});

			set_current_message(0);

			wrapper.find('.close').on('click', function() {
				wrapper.addClass('hidden');
			});
		}

		wrapper.find('.left-arrow').on('click', function() {
			if(wrapper.current_message_idx) {
				set_current_message(wrapper.current_message_idx - 1);
			}
		})

		wrapper.find('.right-arrow').on('click', function() {
			if(help_messages.length > wrapper.current_message_idx + 1) {
				set_current_message(wrapper.current_message_idx + 1);
			}
		});

	},

	setup_module_click: function() {
		frappe.desktop.wiggling = false;

		if(frappe.list_desktop) {
			frappe.desktop.wrapper.on("click", ".desktop-list-item", function() {
				frappe.desktop.open_module($(this));
			});
		} else {
			frappe.desktop.wrapper.on("click", ".app-icon", function() {
				if ( !frappe.desktop.wiggling ) {
					frappe.desktop.open_module($(this).parent());
				}
			});
		}
		frappe.desktop.wrapper.on("click", ".circle", function() {
			var doctype = $(this).attr('data-doctype');
			if(doctype) {
				frappe.ui.notifications.show_open_count_list(doctype);
			}
		});

		frappe.desktop.setup_wiggle();
	},

	setup_wiggle: () => {
		// Wiggle, Wiggle, Wiggle.
		const DURATION_LONG_PRESS = 1000;
		// lesser the antidode, more the wiggle (like your drunk uncle)
		// 75 seems good to replicate the iOS feels.
		const WIGGLE_ANTIDODE     = 75;

		var   timer_id      = 0;
		const $cases        = frappe.desktop.wrapper.find('.case-wrapper');
		const $icons        = frappe.desktop.wrapper.find('.app-icon');
		const $notis        = $(frappe.desktop.wrapper.find('.circle').toArray().filter((object) => {
			// This hack is so bad, I should punch myself.
			// Seriously, punch yourself.
			const text      = $(object).find('.circle-text').html();
			
			return text;
		}));
		
		const clearWiggle   = () => {
			const $closes   = $cases.find('.module-remove');
			$closes.hide();
			$notis.show();

			$icons.trigger('stopRumble');

			frappe.desktop.wiggling   = false;
		};

		// initiate wiggling.
		$icons.jrumble({
			speed: WIGGLE_ANTIDODE // seems neat enough to match the iOS way
		});

		frappe.desktop.wrapper.on('mousedown', '.app-icon', () => {
			timer_id     = setTimeout(() => {
				frappe.desktop.wiggling = true;
				// hide all notifications.
				$notis.hide();
				
				$cases.each((i) => {
					const $case    = $($cases[i]);
					const template = 
					`
						<div class="circle module-remove" style="background-color:#E0E0E0; color:#212121">
							<div class="circle-text">
								<b>
									&times
								</b>
							</div>
						</div>
					`;

					$case.append(template);
					const $close  = $case.find('.module-remove');
					const name    = $case.attr('title');
					$close.click(() => {
						// good enough to create dynamic dialogs?
						const dialog = new frappe.ui.Dialog({
							title: __(`Hide ${name}?`)
						});
						dialog.set_primary_action(__('Hide'), () => {
							frappe.call({
								method: 'frappe.desk.doctype.desktop_icon.desktop_icon.hide',
								args: { name: name },
								freeze: true,
								callback: (response) => 
								{
									if ( response.message ) {
										location.reload();
									}
								}
							})

							dialog.hide();
							
							clearWiggle();
						});
						// Hacks, Hacks and Hacks.
						var $cancel = dialog.get_close_btn();
						$cancel.click(() => {
							clearWiggle();
						});
						$cancel.html(__(`Cancel`));

						dialog.show();
					});
				});
			
				$icons.trigger('startRumble');
			}, DURATION_LONG_PRESS);
		});
		frappe.desktop.wrapper.on('mouseup mouseleave', '.app-icon', () => {
			clearTimeout(timer_id);
		});

		// also stop wiggling if clicked elsewhere.
		$('body').click((event) => {
			if ( frappe.desktop.wiggling ) {
				const $target = $(event.target);
				// our target shouldn't be .app-icons or .close
				const $parent = $target.parents('.case-wrapper');
				if ( $parent.length == 0 )
					clearWiggle();
			}
		});
		// end wiggle
	},

	open_module: function(parent) {
		var link = parent.attr("data-link");
		if(link) {
			if(link.indexOf('javascript:')===0) {
				eval(link.substr(11));
			} else if(link.substr(0, 1)==="/" || link.substr(0, 4)==="http") {
				window.open(link, "_blank");
			} else {
				frappe.set_route(link);
			}
			return false;
		} else {
			var module = frappe.get_module(parent.attr("data-name"));
			if (module && module.onclick) {
				module.onclick();
				return false;
			}
		}
	},

	make_sortable: function() {
		if (frappe.dom.is_touchscreen() || frappe.list_desktop) {
			return;
		}

		new Sortable($("#icon-grid").get(0), {
			onUpdate: function(event) {
				var new_order = [];
				$("#icon-grid .case-wrapper").each(function(i, e) {
					new_order.push($(this).attr("data-name"));
				});

				frappe.call({
					method: 'frappe.desk.doctype.desktop_icon.desktop_icon.set_order',
					args: {
						'new_order': new_order,
						'user': frappe.session.user
					},
					quiet: true
				});
			}
		});
	},

	set_background: function() {
		frappe.ui.set_user_background(frappe.boot.user.background_image, null,
			frappe.boot.user.background_style);
	},

	show_pending_notifications: function() {
		var modules_list = frappe.get_desktop_icons();
		for (var i=0, l=modules_list.length; i < l; i++) {
			var module = modules_list[i];

			var module_doctypes = frappe.boot.notification_info.module_doctypes[module.module_name];

			var sum = 0;
			if(module_doctypes) {
				if(frappe.boot.notification_info.open_count_doctype) {
					// sum all doctypes for a module
					for (var j=0, k=module_doctypes.length; j < k; j++) {
						var doctype = module_doctypes[j];
						sum += (frappe.boot.notification_info.open_count_doctype[doctype] || 0);
					}
				}
			} else if(frappe.boot.notification_info.open_count_doctype
				&& frappe.boot.notification_info.open_count_doctype[module.module_name]!=null) {
				// notification count explicitly for doctype
				sum = frappe.boot.notification_info.open_count_doctype[module.module_name];

			} else if(frappe.boot.notification_info.open_count_module
				&& frappe.boot.notification_info.open_count_module[module.module_name]!=null) {
				// notification count explicitly for module
				sum = frappe.boot.notification_info.open_count_module[module.module_name];
			}

			// if module found
			if(module._id.indexOf('/')===-1) {
				var notifier = $(".module-count-" + module._id);
				if(notifier.length) {
					notifier.toggle(sum ? true : false);
					var circle = notifier.find(".circle-text");
					var text = sum || '';
					if(text > 99) {
						text = '99+';
					}

					if(circle.length) {
						circle.html(text);
					} else {
						notifier.html(text);
					}
				}
			}
		}
	}
});
