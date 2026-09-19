// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views.pageview");
frappe.provide("frappe.standard_pages");

// Set on <body> while a Frappe UI page is on screen. `island_page.scss` keys the
// bounded box off this class. The island scrolls its own body, which needs a
// definite height to scroll in, and desk's page is document-scrolled.
const ISLAND_PAGE_CLASS = "island-page";

frappe.views.pageview = {
	with_page: function (name, callback) {
		if (frappe.standard_pages[name]) {
			if (!frappe.pages[name]) {
				frappe.standard_pages[name]();
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
		} else if (localStorage["_page:" + name] && frappe.boot.developer_mode != 1) {
			// cached in local storage
			frappe.model.sync(JSON.parse(localStorage["_page:" + name]));
			callback();
		} else if (name) {
			// get fresh
			return frappe.call({
				method: "frappe.desk.desk_page.getpage",
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
				error: function () {
					frappe.search.utils.results_to_hide.push(name);
				},
				freeze: true,
			});
		}
	},

	show: function (name) {
		if (!name) {
			name = frappe.boot ? frappe.boot.home_page : window.page_name;
		}
		frappe.model.with_doctype("Page", function () {
			frappe.views.pageview.with_page(name, function (r) {
				if (r && r.exc) {
					if (!r["403"]) frappe.show_not_found(name);
				} else if (!frappe.pages[name]) {
					new frappe.views.Page(name);
				}
				frappe.container.change_to(name);
			});
		});
	},
};

frappe.views.Page = class Page {
	constructor(name) {
		this.name = name;
		var me = this;

		// web home page
		if (name == window.page_name) {
			this.wrapper = document.getElementById("page-" + name);
			this.wrapper.label = document.title || window.page_name;
			this.wrapper.page_name = window.page_name;
			frappe.pages[window.page_name] = this.wrapper;
		} else {
			this.pagedoc = locals.Page[this.name];
			if (!this.pagedoc) {
				frappe.show_not_found(name);
				return;
			}

			this.wrapper = frappe.container.add_page(this.name);
			this.wrapper.page_name = this.pagedoc.name;

			if (this.pagedoc.island) {
				// A Frappe UI page. `island` is the name its Page row registered,
				// and desk ships no script or style for one of these.
				this.setup_island_page();
			} else {
				// set content, script and style
				if (this.pagedoc.content) this.wrapper.innerHTML = this.pagedoc.content;
				frappe.dom.eval(this.pagedoc.__script || this.pagedoc.script);
				frappe.dom.set_style(this.pagedoc.style || "");
			}

			// set breadcrumbs
			frappe.breadcrumbs.add(this.pagedoc.module || null);
		}

		this.trigger_page_event("on_page_load");
		frappe.breadcrumbs.add({
			type: "Custom",
			label: __(this.pagedoc.title),
			route: frappe.get_route_str(),
		});

		// set events
		$(this.wrapper).on("show", function () {
			window.cur_frm = null;
			me.trigger_page_event("on_page_show");
			me.trigger_page_event("refresh");
		});
	}

	/**
	 * A Frappe UI page: desk builds the page, and an island draws its body.
	 *
	 * Desk keeps its page head and sets the chrome from what the island reports.
	 * `title` names the page and `actions` fill the page menu. See
	 * ui/island/decisions/0010-a-page-island-reports-title-and-actions.md.
	 *
	 * The island stays mounted while the page is hidden, so coming back keeps
	 * what the reader left. A route change inside the page updates its props
	 * instead of re-mounting it.
	 */
	setup_island_page() {
		frappe.ui.make_app_page({ parent: this.wrapper, single_column: true });
		this.island_container = $('<div class="island-page-body">').appendTo(
			$(this.wrapper).find(".page-content")
		);

		// What the island last reported. Desk re-applies both on every visit,
		// because another page owns the head in between.
		this.island_title = null;
		this.island_actions = [];

		$(this.wrapper).on("show", () => {
			document.body.classList.add(ISLAND_PAGE_CLASS);
			this.show_island();
			this.set_island_chrome();
		});

		$(this.wrapper).on("hide", () => {
			document.body.classList.remove(ISLAND_PAGE_CLASS);
		});
	}

	/**
	 * Mounts the island on the first visit and updates its props on the rest.
	 *
	 * The props are the part of the URL below the page. An island reads its own
	 * address from them rather than from desk's router, so the same component
	 * runs under a host that has no desk.
	 */
	show_island() {
		const props = {
			route: frappe.get_route().slice(1),
			query: Object.fromEntries(new URLSearchParams(window.location.search)),
		};

		if (this.island) {
			this.island.update(props);
			return;
		}

		this.island = frappe.ui.mount_island(this.pagedoc.island, this.island_container[0], {
			...props,
			onTitle: (title) => {
				this.island_title = title;
				this.set_island_chrome();
			},
			onActions: (actions) => {
				this.island_actions = actions || [];
				this.set_island_chrome();
			},
		});

		this.island.ready.catch((error) => this.show_island_error(error));
	}

	/**
	 * The page head, from what the island reported.
	 *
	 * The title goes to the last breadcrumb and to the browser tab, not to
	 * `page.set_title`: that writes into the `.title-text` crumb, which the next
	 * `breadcrumbs.update()` overwrites.
	 *
	 * An action is `{ label, icon? }` plus either an `onClick` or an `href`. An
	 * `href` leads out of desk, so desk opens it in a new tab. A desk menu row is
	 * a click handler rather than a link, because `add_dropdown_item` writes its
	 * own `href="#"`. Desk's menu rows carry no icon, so the icon goes unread.
	 */
	set_island_chrome() {
		const label = this.island_title || __(this.pagedoc.title) || this.pagedoc.name;
		frappe.breadcrumbs.add({
			type: "Custom",
			label: label,
			route: frappe.get_route_str(),
		});
		frappe.utils.set_title(label);

		const page = this.wrapper.page;
		page.clear_menu();
		this.island_actions.forEach((action) => {
			const click = action.href ? () => window.open(action.href, "_blank") : action.onClick;
			page.add_menu_item(action.label, click);
		});
	}

	/**
	 * The island did not load. It is the whole page here, so desk says so where
	 * the page would have been. Nearly every cause is a bundle that was never
	 * built, and the loader's own message names the asset and the fix, so
	 * developer mode shows it as it is.
	 */
	show_island_error(error) {
		console.error(`could not mount the "${this.pagedoc.island}" island`, error);

		this.island_container.empty().append(
			frappe.ui.empty_state({
				icon: "package",
				title: __("This page has not been built"),
				description: frappe.boot.developer_mode
					? error.message
					: __("Its assets are missing. Build the app that ships this page."),
			})
		);
	}

	trigger_page_event(eventname) {
		var me = this;
		if (me.wrapper[eventname]) {
			me.wrapper[eventname](me.wrapper);
		}
	}
};

frappe.show_not_found = function (page_name) {
	frappe.show_message_page({
		page_name: page_name,
		message: __("Sorry! I could not find what you were looking for."),
		img: "/assets/frappe/images/ui/bubble-tea-sorry.svg",
	});
};

frappe.show_not_permitted = function (page_name) {
	frappe.show_message_page({
		page_name: page_name,
		message: __("Sorry! You are not permitted to view this page."),
		img: "/assets/frappe/images/ui/bubble-tea-sorry.svg",
	});
};

frappe.show_message_page = function (opts) {
	// opts can include `page_name`, `message`, `icon` or `img`
	if (!opts.page_name) {
		opts.page_name = frappe.get_route_str();
	}

	if (opts.icon) {
		opts.img = repl('<span class="%(icon)s message-page-icon"></span> ', opts);
	} else if (opts.img) {
		opts.img = repl('<img src="%(img)s" class="message-page-image">', opts);
	}

	var page = frappe.pages[opts.page_name] || frappe.container.add_page(opts.page_name);
	$(page).html(
		repl(
			'<div class="page message-page">\
			<div class="text-center message-page-content">\
				%(img)s\
				<p class="lead">%(message)s</p>\
				<a class="btn btn-default btn-sm btn-home" href="/desk">%(home)s</a>\
			</div>\
		</div>',
			{
				img: opts.img || "",
				message: opts.message || "",
				home: __("Home"),
			}
		)
	);

	frappe.container.change_to(opts.page_name);
};
