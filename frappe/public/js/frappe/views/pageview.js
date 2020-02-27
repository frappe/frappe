// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import Desktop from './desktop/desktop.js';

frappe.provide('frappe.views.pageview');
frappe.provide("frappe.standard_pages");

frappe.views.pageview = {
	show: function(name) {
		if(!name) {
			name = (frappe.boot ? frappe.boot.home_page : window.page_name);

			if(name === "workspace") {
				if(!frappe.workspace) {
					let page = frappe.container.add_page('workspace');
					let container = $('<div class="container"></div>').appendTo(page);
					container = $('<div></div>').appendTo(container);

					frappe.workspace = new Desktop({
						wrapper: container
					})
				}

				frappe.container.change_to('workspace');
				frappe.workspace.route();
				frappe.utils.set_title(__('Desk'));
				return;
			}
		}
	}
};

frappe.views.Page = Class.extend({
	init: function(name) {
		this.name = name;
		var me = this;
		// web home page
		if(name==window.page_name) {
			this.wrapper = document.getElementById('page-' + name);
			this.wrapper.label = document.title || window.page_name;
			this.wrapper.page_name = window.page_name;
			frappe.pages[window.page_name] = this.wrapper;
		} else {
			this.pagedoc = locals.Page[this.name];
			if(!this.pagedoc) {
				frappe.show_not_found(name);
				return;
			}
			this.wrapper = frappe.container.add_page(this.name);
			this.wrapper.label = this.pagedoc.title || this.pagedoc.name;
			this.wrapper.page_name = this.pagedoc.name;

			// set content, script and style
			if(this.pagedoc.content)
				this.wrapper.innerHTML = this.pagedoc.content;
			frappe.dom.eval(this.pagedoc.__script || this.pagedoc.script || '');
			frappe.dom.set_style(this.pagedoc.style || '');

			// set breadcrumbs
			frappe.breadcrumbs.add(this.pagedoc.module || null);
		}

		this.trigger_page_event('on_page_load');
		// set events
		$(this.wrapper).on('show', function() {
			window.cur_frm = null;
			me.trigger_page_event('on_page_show');
			me.trigger_page_event('refresh');
		});
	},
	trigger_page_event: function(eventname) {
		var me = this;
		if(me.wrapper[eventname]) {
			me.wrapper[eventname](me.wrapper);
		}
	}
});

frappe.show_not_found = function(page_name) {
	frappe.show_message_page({
		page_name: page_name,
		message: __("Sorry! I could not find what you were looking for."),
		img: "/assets/frappe/images/ui/bubble-tea-sorry.svg"
	});
};

frappe.show_not_permitted = function(page_name) {
	frappe.show_message_page({
		page_name: page_name,
		message: __("Sorry! You are not permitted to view this page."),
		img: "/assets/frappe/images/ui/bubble-tea-sorry.svg",
		// icon: "octicon octicon-circle-slash"
	});
};

frappe.show_message_page = function(opts) {
	// opts can include `page_name`, `message`, `icon` or `img`
	if(!opts.page_name) {
		opts.page_name = frappe.get_route_str();
	}

	if(opts.icon) {
		opts.img = repl('<span class="%(icon)s message-page-icon"></span> ', opts);
	} else if (opts.img) {
		opts.img = repl('<img src="%(img)s" class="message-page-image">', opts);
	}

	var page = frappe.pages[opts.page_name] || frappe.container.add_page(opts.page_name);
	$(page).html(
		repl('<div class="page message-page">\
			<div class="text-center message-page-content">\
				%(img)s\
				<p class="lead">%(message)s</p>\
				<a class="btn btn-default btn-sm btn-home" href="#">%(home)s</a>\
			</div>\
		</div>', {
				img: opts.img || "",
				message: opts.message || "",
				home: __("Home")
			})
	);

	frappe.container.change_to(opts.page_name);
};

frappe.views.ModulesFactory = class ModulesFactory extends frappe.views.Factory {
	show() {
		if (frappe.pages.modules) {
			frappe.container.change_to('modules');
		} else {
			this.make('modules');
		}
	}

	make(page_name) {
		const assets = [
			'/assets/js/modules.min.js'
		];

		frappe.require(assets, () => {
			frappe.modules.home = new frappe.modules.Home({
				parent: this.make_page(true, page_name)
			});
		});
	}
};