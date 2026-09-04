// Dock: a slim vertical rail rendered to the left of the body sidebar. Its top slot says
// what you are inside and links back out of it, and below that it lists the modules you can switch
// to. Both come from the only question app context answers: which app owns the sidebar on screen
// (Sidebar.get_sidebar_app):
//
//   placed      logo = app icon      items = the app's other modules
//   standalone  logo = module icon   items = (empty)
//
// It is drawn only when the app on screen resolves to at least one visible entry
// (Sidebar.dock_enabled) and the page on screen allows it (page_allows_dock; the desktop
// or apps screen does not). An app that resolves to no entries gets no rail rather than an empty
// stripe: the user button moves back to the body sidebar and the sidebar header carries a switcher
// instead.
frappe.ui.Dock = class Dock {
	constructor(sidebar) {
		this.sidebar = sidebar;
		this.make();
	}

	make() {
		// The body is a horizontal flex row (body-sidebar-container, then main-section). Insert the
		// dock as the leftmost element so it sits to the left of the sidebar.
		this.$dock = $(`<div class="dock hidden" role="navigation" aria-label="${__(
			"Workspaces"
		)}">
			<div class="dock-logo">
				<div class="shell-header">
					<a class="shell-header-main" href="/desk" aria-label="${__("Apps")}">
						<div class="header-logo"></div>
						<div class="title-container">
							<div class="header-title"></div>
							<div class="header-subtitle">${frappe.utils.escape_html(frappe.session.user_fullname)}</div>
						</div>
					</a>
					<button class="btn-reset drop-icon" aria-label="${__("Sidebar Menu")}">
						${frappe.utils.icon("chevron-down", "sm", "", "", "", true)}
					</button>
				</div>
			</div>
			<div class="dock-shortcuts"></div>
			<div class="dock-items"></div>
			<button class="dock-user shell-header" aria-label="${__("User Menu")}"></button>
		</div>`);

		let $container = $(".body-sidebar-container");
		if ($container.length) {
			this.$dock.insertBefore($container);
		} else {
			this.$dock.prependTo("body");
		}
		// Right-edge handle, mirroring the body sidebar's own collapse handle. While the sidebar is
		// collapsed and only the rail shows, clicking the rail's right edge reopens it. CSS shows it
		// only in the collapsed state (body.sidebar-collapsed), so it does not compete with the
		// sidebar handle while expanded.
		let $resize = $(`<div class="dock-resize-handle" aria-hidden="true"></div>`);
		$resize.on("click", () => this.sidebar.open());
		this.$dock.append($resize);

		// Built once and never replaced: the header's menu binds to this node, and render_logo
		// rewrites what is inside it rather than the node itself.
		this.$header = this.$dock.find(".shell-header");
		this.$header_logo = this.$header.find(".header-logo");
		this.$header_title = this.$header.find(".header-title");
		// The chevron is what opens the menu; the rest of the header is a way out to the apps
		// screen. They are siblings rather than one nested in the other because a <button> inside
		// an <a> is not valid markup -- the same reason frappe-ui keeps a row's trailing zone
		// outside its link.
		this.$header_menu = this.$header.find(".drop-icon");
		this.$header.find(".shell-header-main").on("click", (e) => {
			e.preventDefault();
			frappe.set_route("/desk");
		});
		this.$shortcuts = this.$dock.find(".dock-shortcuts");
		this.$items = this.$dock.find(".dock-items");
		this.$user = this.$dock.find(".dock-user");
		this.render_shortcuts();
		this.render_user();
	}

	// Icon shortcuts pinned directly under the app logo: search and notifications, replacing the
	// page header's buttons. They are declared as configuration so the set, the order and each
	// item's label live in one place, and render_shortcuts() turns each entry into a rail row.
	// Every item mirrors <RailItem variant="ghost">: transparent until hovered.
	//
	// Item shape:
	//   name      identifier
	//   icon      icon name passed to frappe.utils.icon
	//   label     the row's visible label, and its accessible label
	//   css_class extra classes on the button (external code hooks off these)
	//   condition () => bool, whether to render this shortcut at all
	//   badge     optional extra markup appended inside the button, such as a count dot
	//   on_click  optional click handler
	//   setup     optional ($item) => {} hook run after the button is built
	get_shortcuts() {
		return [
			{
				name: "search",
				icon: "search",
				label: __("Search"),
				// AwesomeBar's delegated click handler in page.js opens the shared search modal
				// from this class, so keep it or search stops working from the dock.
				css_class: "navbar-modal-search-mobile",
				condition: () => frappe.boot.desk_settings.search_bar,
			},
			{
				name: "notifications",
				icon: "bell",
				label: __("Notifications"),
				// The Notifications view keeps the unread count in sync from these classes (see
				// notifications.js) and opens the same SidebarPanel the sidebar's own bell does.
				css_class: "sidebar-notification",
				condition: () => frappe.boot.desk_settings.notifications,
				badge: `<span class="notification-count hidden" aria-live="polite"></span>`,
				on_click: () => this.toggle_notifications(),
				setup: ($item) => {
					// Seed the badge from boot; the Notifications view keeps it updated after
					// that.
					this.sync_notification_count(
						$item,
						frappe.boot.notification_unread_count || 0
					);
				},
			},
			{
				name: "background-tasks",
				icon: "server",
				label: __("Background Tasks"),
				// Same class as the sidebar's button. BackgroundTasks shows and hides every
				// trigger from it, and it is the panel's trigger_selector, so the rail's
				// button needs no wiring of its own.
				css_class: "sidebar-background-tasks hidden",
				on_click: () => frappe.ui.sidebar_panels.toggle("background-tasks"),
				setup: ($item) => {
					// Starts hidden, like the sidebar's. Seed it from what the view has
					// already fetched, since the rail may be built after that call returned.
					$item.toggleClass("hidden", !this.sidebar.background_tasks?.db_tasks?.length);
				},
			},
		];
	}

	// Render the configured shortcuts under the logo, each as one labelled row. This runs once, from
	// make(), so handlers are not re-bound.
	render_shortcuts() {
		if (frappe.session.user === "Guest") {
			return;
		}

		this.get_shortcuts().forEach((item) => {
			if (item.condition && !item.condition()) {
				return;
			}

			let $item = $(`<button
				class="dock-item ${item.css_class || ""}"
				aria-label="${frappe.utils.escape_html(item.label)}"
			>
				<span class="dock-item-icon">
					${frappe.utils.icon(item.icon, "md")}
					${item.badge || ""}
				</span>
				<span class="dock-item-label">${frappe.utils.escape_html(item.label)}</span>
			</button>`);

			if (item.on_click) {
				$item.on("click", item.on_click);
			}
			if (item.setup) {
				item.setup($item);
			}

			this.$shortcuts.append($item);
		});
	}

	// The rail shows unread as a small dot on the bell rather than a number, so toggle it on whether
	// any exist.
	sync_notification_count($bell, count) {
		$bell.find(".notification-count").toggleClass("hidden", count <= 0);
	}

	// Same panel the sidebar bell opens. The registry owns it, so the rail does not have
	// to know where it lives or what else might be open.
	toggle_notifications() {
		frappe.ui.sidebar_panels.toggle("notifications");
	}

	// User avatar pinned to the bottom of the rail, opening the same dropdown as the sidebar's user
	// button. This runs once, from make(), so the menu is not re-bound on every refresh().
	render_user() {
		// The same two lines the header carries, in the same classes: who you are over how you are
		// addressed, which is what the body sidebar's own user button has always shown.
		this.$user.html(
			`${frappe.avatar(frappe.session.user, "avatar-medium")}
			<div class="title-container">
				<div class="header-title">${frappe.utils.escape_html(frappe.session.user_fullname)}</div>
				<div class="header-subtitle">${frappe.utils.escape_html(frappe.session.user_email)}</div>
			</div>`
		);
		this.sidebar.create_user_menu({ parent: this.$user, button: this.$user });
	}

	refresh() {
		// While the rail is up the panel's header is hidden, so the menu that hung on it -- the
		// sidebar switcher, Edit Sidebar and the system items -- hangs on this header instead. Done
		// here rather than in make() because the rail can be built before the header it borrows the
		// menu from, and only ever once.
		if (!this.header_menu && this.sidebar.sidebar_header) {
			this.header_menu = this.sidebar.sidebar_header.attach_menu(this.$header_menu);
		}

		// The dock belongs to the app whose body sidebar is on screen.
		this.app = this.sidebar.get_sidebar_app();
		// It is drawn only if it has entries and the page on screen allows it. The desktop or apps
		// screen, and any page that has not rendered yet, do not.
		let enabled = this.sidebar.dock_enabled() && this.sidebar.page_allows_dock();
		// Drives the CSS that hides the sidebar's own user button while the rail is active, so
		// switching this off returns the user button to the sidebar.
		$("body").toggleClass("dock-active", enabled);

		if (!enabled) {
			this.$dock.addClass("hidden");
			return;
		}
		this.$dock.removeClass("hidden");

		// One navigation calls this up to three times: once from the router and twice from
		// Sidebar.refresh(), its own call plus the one inside apply_page_visibility. Each call
		// rebuilds every button, so rendering unconditionally did that two or three times for a
		// rail that had not changed.
		//
		// Everything the rail draws goes into this signature, labels and icons as well as the
		// entries, so renaming a module's sidebar still redraws its row. If the signature matches,
		// there is nothing to redraw.
		const entries = this.sidebar.collect_dock_entries(this.app);
		const signature = JSON.stringify([
			this.app ? this.app.app_name : null,
			this.sidebar.current_module,
			entries.map((entry) => [
				this.sidebar.dock_key(entry),
				entry.label,
				entry.icon,
				this.sidebar.is_active_entry(entry),
			]),
		]);
		if (signature === this.rendered) return;
		this.rendered = signature;

		this.render_logo();
		this.render_entries(entries);
	}

	// The rail's top slot: what you are inside, and the way out. It shows the app's icon when the
	// module on screen belongs to an app, and the module's own icon when it does not. Both link to
	// the desktop, so a module you entered always has a way out.
	//
	// There is no fallback to the first installed app's logo, so no rail shows unrelated branding.
	// Every rail now carries an icon of its own, resolved from data it already holds.
	render_logo() {
		const { icon, title } = this.app ? this.app_logo() : this.module_logo();

		// Only the mark and the name change here. The way out to the apps screen is the menu's
		// "All apps" row now, so the header is a menu trigger rather than the link it used to be.
		this.$header_logo.html(icon);
		this.$header_title.text(title);
	}

	// A module belonging to an app shows that app's logo. An app that declares none gets a letter
	// icon, matching the desktop apps screen.
	app_logo() {
		const title = this.app.app_title || this.app.app_name;
		const logo_url = Array.isArray(this.app.app_logo_url)
			? this.app.app_logo_url[0]
			: this.app.app_logo_url;

		const icon = logo_url
			? `<img src="${frappe.utils.escape_html(logo_url)}" alt="${frappe.utils.escape_html(
					title
			  )}" />`
			: frappe.utils.desktop_icon(title, "gray", "sm");

		return { icon, title };
	}

	// A module belonging to no app shows its own icon. No new boot payload is needed, because the
	// module sidebar the rail already reads carries both the header icon and the label.
	module_logo() {
		let sidebar = frappe.boot.module_sidebars[this.sidebar.current_module] || {};
		let label = sidebar.label || this.sidebar.current_module || __("Apps");
		return { icon: this.entry_icon(sidebar.header_icon, label), title: label };
	}

	// A dock entry's icon: the authored one, otherwise a letter icon from its label. The top slot
	// and the items below it share this, so a module looks the same wherever the rail shows it and
	// a pinned workspace gets its own icon on the same terms.
	entry_icon(icon, label) {
		return icon
			? frappe.utils.icon(icon, "md")
			: frappe.utils.desktop_icon(label, "gray", "sm");
	}

	// Inside a module no app claims, this renders nothing: collect_dock_entries returns no
	// entries, and an empty items region is better than a rail of one, since an item permanently
	// active with no alternatives is a switcher that cannot switch.
	render_entries(entries = this.sidebar.collect_dock_entries(this.app)) {
		this.$items.empty();

		entries.forEach((entry) => {
			let $item = this.make_dock_item(entry);
			if ($item) this.$items.append($item);
		});
	}

	// One rail button, for either kind of entry. A pinned workspace needs no markup of its own,
	// because `dock_entry` resolved its label and icon from the boot payload the same way a
	// module's come from its sidebar, so from here on the two are the same.
	make_dock_item(entry) {
		let label = entry.label;
		if (!label) return null;
		let icon = this.entry_icon(entry.icon, label);

		let is_active = this.sidebar.is_active_entry(entry);
		let $item = $(`<button
			class="dock-item ${is_active ? "active" : ""}"
			aria-label="${frappe.utils.escape_html(label)}"
			${is_active ? 'aria-current="page"' : ""}
		>
			<span class="dock-item-icon">${icon}</span>
			<span class="dock-item-label">${frappe.utils.escape_html(label)}</span>
		</button>`);

		$item.on("click", () => this.sidebar.open_dock_entry(entry));
		return $item;
	}
};
