// Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

nts.provide("nts.views.pageview");
nts.provide("nts.standard_pages");

nts.views.pageview = {
	with_page: function (name, callback) {
		if (nts.standard_pages[name]) {
			if (!nts.pages[name]) {
				nts.standard_pages[name]();
			}
			callback();
			return;
		}

		if (
			(locals.Page && locals.Page[name] && locals.Page[name].script) ||
			name == window.page_name
		) {
			// already loaded
			callback();
		} else if (localStorage["_page:" + name] && nts.boot.developer_mode != 1) {
			// cached in local storage
			nts.model.sync(JSON.parse(localStorage["_page:" + name]));
			callback();
		} else if (name) {
			// get fresh
			return nts.call({
				method: "nts.desk.desk_page.getpage",
				args: { name: name },
				callback: function (r) {
					if (!r.docs._dynamic_page) {
						try {
							localStorage["_page:" + name] = JSON.stringify(r.docs);
						} catch (e) {
							console.warn(e);
						}
					}
					callback();
				},
				freeze: true,
			});
		}
	},

	show: function (name) {
		if (!name) {
			name = nts.boot ? nts.boot.home_page : window.page_name;
		}
		nts.model.with_doctype("Page", function () {
			nts.views.pageview.with_page(name, function (r) {
				if (r && r.exc) {
					if (!r["403"]) nts.show_not_found(name);
				} else if (!nts.pages[name]) {
					new nts.views.Page(name);
				}
				nts.container.change_to(name);
			});
		});
	},
};

nts.views.Page = class Page {
	constructor(name) {
		this.name = name;
		var me = this;

		// web home page
		if (name == window.page_name) {
			this.wrapper = document.getElementById("page-" + name);
			this.wrapper.label = document.title || window.page_name;
			this.wrapper.page_name = window.page_name;
			nts.pages[window.page_name] = this.wrapper;
		} else {
			this.pagedoc = locals.Page[this.name];
			if (!this.pagedoc) {
				nts.show_not_found(name);
				return;
			}
			this.wrapper = nts.container.add_page(this.name);
			this.wrapper.page_name = this.pagedoc.name;

			// set content, script and style
			if (this.pagedoc.content) this.wrapper.innerHTML = this.pagedoc.content;
			nts.dom.eval(this.pagedoc.__script || this.pagedoc.script || "");
			nts.dom.set_style(this.pagedoc.style || "");

			// set breadcrumbs
			nts.breadcrumbs.add(this.pagedoc.module || null);
		}

		this.trigger_page_event("on_page_load");

		// set events
		$(this.wrapper).on("show", function () {
			window.cur_frm = null;
			me.trigger_page_event("on_page_show");
			me.trigger_page_event("refresh");
		});
	}

	trigger_page_event(eventname) {
		var me = this;
		if (me.wrapper[eventname]) {
			me.wrapper[eventname](me.wrapper);
		}
	}
};

nts.show_not_found = function (page_name) {
	nts.show_message_page({
		page_name: page_name,
		message: __("Sorry! I could not find what you were looking for."),
		img: "/assets/nts/images/ui/bubble-tea-sorry.svg",
	});
};

nts.show_not_permitted = function (page_name) {
	nts.show_message_page({
		page_name: page_name,
		message: __("Sorry! You are not permitted to view this page."),
		img: "/assets/nts/images/ui/bubble-tea-sorry.svg",
		// icon: "octicon octicon-circle-slash"
	});
};

nts.show_message_page = function (opts) {
	// opts can include `page_name`, `message`, `icon` or `img`
	if (!opts.page_name) {
		opts.page_name = nts.get_route_str();
	}

	if (opts.icon) {
		opts.img = repl('<span class="%(icon)s message-page-icon"></span> ', opts);
	} else if (opts.img) {
		opts.img = repl('<img src="%(img)s" class="message-page-image">', opts);
	}

	var page = nts.pages[opts.page_name] || nts.container.add_page(opts.page_name);
	$(page).html(
		repl(
			'<div class="page message-page">\
			<div class="text-center message-page-content">\
				%(img)s\
				<p class="lead">%(message)s</p>\
				<a class="btn btn-default btn-sm btn-home" href="/app">%(home)s</a>\
			</div>\
		</div>',
			{
				img: opts.img || "",
				message: opts.message || "",
				home: __("Home"),
			}
		)
	);

	nts.container.change_to(opts.page_name);
};
