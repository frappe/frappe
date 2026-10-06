frappe.provide("frappe.ui");

/**
 * The bottom tab bar on phones. The bar itself is frappe-ui's <frappe-mobile-nav>
 * custom element (prebuilt into lib/frappe-mobile-nav.js and loaded with Vue from
 * mobile_nav.bundle.js once the screen is phone-sized). This class only picks
 * the tabs and wires each one to something Desk already has. Search, Notifications and
 * Profile are pages of their own (desk/page/search, notifications, profile), for phones only.
 *
 * The tabs are the same everywhere. Where you are lives in the page header instead: tapping
 * the page title opens a sheet with the dock across the top and the sidebar under it
 * (see open_navigation). New opens a sheet too; both are a frappe.ui.BottomSheet.
 *
 * It is always in the DOM; mobile_nav.scss shows it below the md breakpoint only, so
 * rotating or resizing past 768px needs no JS.
 */
frappe.ui.MobileNav = class MobileNav {
	constructor() {
		this.nav = document.createElement("frappe-mobile-nav");
		this.nav.className = "desk-mobile-nav";
		this.tabs = this.get_tabs().map((tab) => this.make_tab(tab));
		document.body.appendChild(this.nav);

		// .main-section makes room for the bar only once the element can draw it, so a
		// missing frappe-mobile-nav.js costs no blank strip at the bottom of the page.
		customElements.whenDefined("frappe-mobile-nav").then(() => {
			this.defined = true;
			this.apply_page_visibility();
		});
		$(document).on("page-change", () => this.apply_page_visibility());

		frappe.router.on("change", () => {
			this.set_active();
			this.route_changed = true;
			this.close_sheet();
		});
		this.set_active();

		// The title is the trail's last crumb (Page.set_title), redrawn on every paint, so
		// the tap is delegated. Pages inside dialogs draw no trail and are left out.
		$(document).on("click", ".page-head .navbar-breadcrumbs li:last-child", () => {
			if (frappe.is_mobile() && document.body.classList.contains("mobile-nav-title")) {
				this.open_navigation();
			}
		});

		// A form on a phone has a back button in place of the tab bar (see apply_page_visibility).
		$(document).on("click", ".page-head .page-back-button", () => this.go_back());
	}

	get_tabs() {
		const { search_bar, notifications } = frappe.boot.desk_settings || {};
		return [
			{ name: "home", label: __("Home"), icon: "house", to: "/desk" },
			search_bar && {
				name: "search",
				label: __("Search"),
				icon: "search",
				to: "/desk/search",
			},
			{
				name: "new",
				label: __("New"),
				icon: "plus",
				on_click: () => this.open_new(),
			},
			notifications && {
				name: "notifications",
				label: __("Notifications"),
				icon: "bell",
				to: "/desk/notifications",
			},
			{
				name: "profile",
				label: __("Profile"),
				icon: "user",
				to: "/desk/profile",
			},
		].filter(Boolean);
	}

	make_tab(tab) {
		const item = document.createElement("frappe-mobile-nav-item");
		item.setAttribute("label", tab.label);
		// with `to` the item is a link Desk's router picks up; without, a button
		if (tab.to) item.setAttribute("to", tab.to);
		item.innerHTML = frappe.utils.icon(tab.icon, "md");
		if (tab.on_click) {
			item.addEventListener("click", (e) => {
				// the element also re-emits its Vue `click` as a CustomEvent; act once
				if (e instanceof MouseEvent) tab.on_click(e);
			});
		}
		this.nav.appendChild(item);
		return { ...tab, el: item };
	}

	// A page keeps the bar off with `hide_mobile_nav`, as it does the dock with `hide_dock`.
	// `has-mobile-nav` on <body> is what shows the bar and makes room for it.
	apply_page_visibility() {
		const page = frappe.container?.page?.page;
		const route = frappe.get_route() || [];
		// A form is a step into a list, not a place of its own: it gets the screen and a way
		// back instead of the tabs. A single doctype has no list, so it is a place.
		const form = route[0] === "Form" && !frappe.get_meta(route[1])?.issingle;
		const shown = !!this.defined && !page?.hide_mobile_nav && !form;
		document.body.classList.toggle("has-mobile-nav", shown);
		document.body.classList.toggle("mobile-form-view", !!this.defined && form);
		// A system page opens in no shell, so it has no sidebar for its title to open.
		const system_page = frappe.router.page_info_for(route)?.system_page;
		document.body.classList.toggle("mobile-nav-title", shown && !system_page);
	}

	// Back to where the form was opened from, or to its list when it was opened directly.
	go_back() {
		if (frappe.get_prev_route().length) {
			window.history.back();
			return;
		}
		const doctype = frappe.get_route()[1];
		frappe.set_route(doctype ? ["List", doctype] : "/desk");
	}

	// Every tab but New is a place; New opens a sheet over the page.
	set_active() {
		const route = frappe.get_route() || [];
		// /desk (the app launcher) routes as [""]
		const place = !route[0] || route[0] === "Workspaces" ? "home" : route[0];
		for (const tab of this.tabs) {
			tab.el.toggleAttribute("active", tab.name === place);
		}
	}

	// frappe.ui.BottomSheet comes from bottom_sheet.bundle.js, loaded with the tab bar
	// (see the startup handler below), so a tap before it arrives does nothing.
	open_sheet(title, render) {
		if (!frappe.ui.BottomSheet) return;
		this.close_sheet();
		this.sheet = new frappe.ui.BottomSheet({
			title,
			...render(),
			on_close: () => {
				this.sheet = null;
				this.return_sidebar();
			},
		});
		this.sheet.open();
	}

	close_sheet() {
		this.sheet?.close();
	}

	// The page title, tapped on a phone. The dock is a row of its entries; tapping
	// one shows that module's sidebar in place, and nothing navigates until a row is picked.
	//
	// The sidebar is Desk's own: its items list is moved into the sheet while it is open, so
	// section breaks, highlighting and saved collapsed state all work as on a desktop.
	open_navigation() {
		const sidebar = frappe.app.sidebar;
		if (!sidebar?.$items_container) return;

		this.open_sheet(this.module_label(sidebar.current_module), () => ({
			content: () => {
				this.opened_on = sidebar.current_module;
				this.route_changed = false;
				const $body = $(`<div class="desk-mobile-sheet"></div>`);

				const $dock = $(`<div class="desk-mobile-sheet-dock"></div>`).appendTo($body);
				this.render_dock($dock);

				// .body-sidebar carries the row styles; mobile_nav.scss undoes its drawer layout
				const $sidebar = $(`<div class="body-sidebar desk-mobile-sheet-sidebar"></div>`);
				this.items_home = sidebar.$items_container.parent();
				sidebar.$items_container.appendTo($sidebar);
				$sidebar.appendTo($body);

				// Rows that navigate close the sheet through the route change; this catches a
				// tap on the row for the page already open, which changes no route. A picked
				// row keeps the module it is in: putting the sidebar back would rebuild it
				// under the tap, and the browser would follow the link as a full page load.
				$body.on("click", "a[href]", (e) => {
					// a new tab leaves this page as it is, so the sidebar goes back too
					const new_tab = e.currentTarget.target === "_blank" || e.ctrlKey || e.metaKey;
					if (!new_tab) this.route_changed = true;
					this.close_sheet();
				});
				return $body[0];
			},
		}));
	}

	render_dock($dock) {
		const sidebar = frappe.app.sidebar;
		$dock.empty();
		for (const entry of sidebar.collect_dock_entries(sidebar.get_sidebar_app())) {
			if (!entry.label) continue;
			const active = entry.module && entry.module === sidebar.current_module;
			const $entry = $(`<button type="button" class="desk-mobile-sheet-dock-item ${
				active ? "active" : ""
			}">
				<span class="dock-item-icon">${
					entry.icon
						? frappe.utils.icon(entry.icon, "md")
						: frappe.utils.desktop_icon(entry.label, "gray", "sm")
				}</span>
				<span class="dock-item-label">${frappe.utils.escape_html(entry.label)}</span>
			</button>`).appendTo($dock);
			$entry.on("click", () => this.browse_dock_entry(entry, $dock));
		}
	}

	browse_dock_entry(entry, $dock) {
		const sidebar = frappe.app.sidebar;
		if (!entry.module) {
			// a URL or a module-less workspace has no sidebar to show
			const route = sidebar.dock_entry_route(entry);
			this.close_sheet();
			if (route?.startsWith("/desk/")) frappe.set_route(route);
			else if (route) window.open(route, "_blank", "noopener");
			return;
		}
		sidebar.select_shell(entry.module);
		this.sheet.set_title(this.module_label(entry.module));
		this.render_dock($dock);
		// the tapped tile was just rebuilt; focus left on <body> would miss the sheet's Escape
		$dock.find(".active").trigger("focus");
	}

	// Put the items list back in the drawer, and the sidebar back on the module the page
	// is in if the sheet browsed away without going anywhere.
	return_sidebar() {
		const sidebar = frappe.app.sidebar;
		if (!this.items_home || !sidebar) return;

		sidebar.$items_container.appendTo(this.items_home);
		this.items_home = null;
		if (!this.route_changed) sidebar.select_shell(this.opened_on);
	}

	module_label(module) {
		const label = frappe.boot.module_sidebars?.[module]?.label || module;
		return label ? __(label) : __("Apps");
	}

	// A new document of any doctype the sidebar on screen lists and the user can create.
	open_new() {
		const sidebar = frappe.app.sidebar;
		const seen = new Set();
		const items = (sidebar?.sidebar_data?.items || []).filter((item) => {
			const doctype = item.type === "Link" && item.link_type === "DocType" && item.link_to;
			if (!doctype || seen.has(doctype) || !frappe.model.can_create(doctype)) return false;
			seen.add(doctype);
			return true;
		});

		this.open_sheet(__("New"), () =>
			items.length
				? {
						options: items.map((item) => ({
							// the doctype, not the row's label: rows are often views such as "All"
							label: __(item.link_to),
							icon: item.icon || "file",
							onclick: () => frappe.new_doc(item.link_to),
						})),
				  }
				: {
						content: __("Nothing to create in {0}", [
							this.module_label(sidebar?.current_module),
						]),
				  }
		);
	}
};

$(document).on("startup", () => {
	// Nothing is built on a wider screen. Same breakpoint as mobile_nav.scss; a window
	// narrowed later builds the bar then. Until its element loads, the bar is an inert tag.
	// load_asset, not frappe.require, which would freeze the screen while it loads.
	const phone = window.matchMedia("(max-width: 767.98px)");
	const load = () => {
		if (!phone.matches) return;
		phone.removeEventListener("change", load);
		if (!frappe.ui.mobile_nav) frappe.ui.mobile_nav = new frappe.ui.MobileNav();
		for (const asset of [
			"mobile_nav.bundle.js",
			"bottom_sheet.bundle.js",
			"bottom_sheet.bundle.css",
		]) {
			const path = frappe.assets.bundled_asset(asset);
			frappe.assets.load_asset(path, path);
		}
	};
	phone.addEventListener("change", load);
	load();
});
