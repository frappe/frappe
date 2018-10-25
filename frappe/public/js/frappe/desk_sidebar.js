frappe.provide("frappe.ui");
frappe.ui.DeskSidebar = class DeskSidebar {

	constructor() {

		this.update_reroute();

		this.container = $("#desk_sidebar_div");
		this.container.hide();

		this.update_dom();
		this.render();
		this.register_icon_events();
		this.make_sortable();
		this.setup_wiggle();
	}

	update_reroute() {
		if(frappe.re_route["#desktop"]) delete frappe.re_route["#desktop"];
		if(frappe.re_route[""]) delete frappe.re_route[""];

		if(frappe.session.user_nav == "Sidebar" && frappe.session.user_homepage && frappe.session.user_homepage != "" && frappe.session.user_homepage != "desktop"){
			frappe.re_route[""] = frappe.session.user_homepage;
			frappe.re_route["#desktop"] = frappe.session.user_homepage;
		} else {
			frappe.re_route[""] = "desktop";
		}
	}

	get_desk_navigation_settings() {
		frappe.call({
			method: "frappe.client.get_value",
			args: {"doctype": "User", "filters":{"name": frappe.session.user}, "fieldname": ["homepage", "desk_navigation", "full_width_desk"]}
		}).done((r) => {
			frappe.session.user_nav = r.message.desk_navigation;
			frappe.session.user_homepage = r.message.homepage;
			frappe.session.full_width_desk =  r.message.full_width_desk;
			frappe.session.app_container_class = r.message.full_width_desk ? "container-fluid container-margin-10" : "container";
			this.update_reroute();
			this.update_dom();
		}).fail((f) => {
			console.log(f);
		});
	}

	update_dom(){
		if(frappe.session.user_nav == "Sidebar"){
			$("#body_div").addClass("with-sidebar");
			this.container.show();
		} else {
			$("#body_div").removeClass("with-sidebar");
			this.container.hide();
		}
		if(frappe.session.full_width_desk) {
			$('.app-container').each(function(){
				$(this).removeClass("container");
				$(this).addClass("container-fluid container-margin-10");
			});
		} else {
			$('.app-container').each(function(){
				$(this).removeClass("container-fluid container-margin-10");
				$(this).addClass("container");
			});
		}
	}

	render() {
		var all_icons = frappe.get_desktop_icons();
		let all_html = "";
		for(var idx in all_icons) {
			let icon = all_icons[idx];
			let html = this.get_sidebar_icon_html(icon.module_name, icon.link, icon.label, icon.app_icon, icon._id, icon._doctype);
			all_html += html;
		}
		this.container.html(all_html);
		this.handle_route_change();
		var me = this;
		frappe.route.on("change", function(){
			me.handle_route_change();
		});
	}

	register_icon_events() {
		this.wiggling = false;
		this.scrolling = false;
		var me = this;
		this.container.on("click", ".app-icon, .app-icon-svg", function() {
			if ( !me.wiggling ) {
				me.go_to_route($(this).parent());
			}
		});
		$("#desk_sidebar_div .desk-sidebar-icon").each(function() {
			$(this).find(".app-icon").tooltip({
				container: ".main-section",
				placement: "right",
				template: "<div class='tooltip sidebar-tooltip'><div class='tooltip-arrow'></div><div class='tooltip-inner'></div></div>"
			});
		});
		$("#desk_sidebar_div").add(window).scroll(function() {
			if(!me.scrolling){
				me.scrolling = true;
				$("#desk_sidebar_div .desk-sidebar-icon .app-icon").each(function() {
					$(this).tooltip('disable');
					$(this).tooltip('hide');
				});
			}
			clearTimeout($.data(this, 'scrollTimer'));
			$.data(this, 'scrollTimer', setTimeout(function() {
				me.scrolling = false;
				$("#desk_sidebar_div .desk-sidebar-icon .app-icon").each(function() {
					$(this).tooltip('enable');
					if($(this).is(":hover")) {
						$(this).tooltip('show');
					}
				});
			}, 250));
		});
	}

	get_sidebar_icon_html(module_name, link, label, app_icon, id, doctype) {
		return `
		<div class="desk-sidebar-icon"
			data-name="${ module_name }" data-link="${ link }" title="${ label }">
			${ app_icon }
			<div class="case-label ellipsis">
				<div class="circle notis module-count-${ id }" data-doctype="${ doctype }" style="display: none;">
					<span class="circle-text"></span>
				</div>
			</div>
			<div class="circle module-remove" style="background-color:#E0E0E0; color:#212121; display: none;">
				<div class="circle-text">
					<b>
						&times
					</b>
				</div>
			</div>
		</div>
		`;
	}

	make_sortable() {
		new Sortable($("#desk_sidebar_div").get(0), {
			animation: 150,
			onUpdate: function() {
				var new_order = [];
				$("#desk_sidebar_div .desk-sidebar-icon").each(function() {
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
	}

	handle_route_change() {
		// Inactivate links
		$( "#desk_sidebar_div .desk-sidebar-icon" ).each(function() {

			let route = frappe.get_route().join('/');
			let data_link = $(this).attr("data-link");

			if(route.includes(data_link)){
				$(this).removeClass("inactive-sidebar-icon");
			} else if(!$(this).hasClass("inactive-sidebar-icon")) {
				$(this).addClass("inactive-sidebar-icon");
			}

		});
	}

	go_to_route(parent) {
		var link = parent.attr("data-link");
		if(link) {
			frappe.set_route(link);
		}
		return false;
	}

	setup_wiggle() {
		// Wiggle, Wiggle, Wiggle.
		const DURATION_LONG_PRESS = 1000;

		var   timer_id      = 0;
		const $cases        = this.container.find('.desk-sidebar-icon');
		const $icons        = this.container.find('.app-icon');
		const $notis        = $(this.container.find('.notis').toArray().filter((object) => {
			// This hack is so bad, I should punch myself.
			// Seriously, punch yourself.
			const text      = $(object).find('.circle-text').html();

			return text;
		}));
		const $closes   = $cases.find('.module-remove');

		const clearWiggle   = () => {

			$closes.hide();
			$notis.show();

			$icons.removeClass('wiggle');

			this.wiggling   = false;
		};

		var me = this;

		$cases.each((i) => {
			const $case    = $($cases[i]);

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

		this.container.on('mousedown', '.app-icon', () => {
			timer_id     = setTimeout(() => {
				me.wiggling = true;
				// hide all notifications.
				$notis.hide();
				$closes.show();

				$icons.addClass('wiggle');

			}, DURATION_LONG_PRESS);
		});
		this.container.on('mouseup mouseleave', '.app-icon', () => {
			clearTimeout(timer_id);
		});

		// also stop wiggling if clicked elsewhere.
		$('body').click((event) => {
			if ( me.wiggling ) {
				const $target = $(event.target);
				// our target shouldn't be .app-icons or .close
				const $parent = $target.parents('.desk-sidebar-icon');
				if ( $parent.length == 0 )
					clearWiggle();
			}
		});
		// end wiggle
	}
};

$(document).on('app_ready',function() {
	frappe.desk_sidebar = new frappe.ui.DeskSidebar();
});
